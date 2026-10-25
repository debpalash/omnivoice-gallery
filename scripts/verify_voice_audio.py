#!/usr/bin/env python3
"""Download every recorded voice and check it is what the manifest promises.

``validate_manifest.py`` checks the manifest's *shape*; it cannot see that a
Release asset was deleted, re-uploaded with different bytes, or uploaded as an
MP3. VoiceStudio would catch each of those only on a user's machine — as a
failed integrity check, or "not a valid WAV" — after the user clicked the voice.
This fetches each clip exactly as the app does (https, allow-listed hosts on
every redirect, 32 MB cap) and applies the app's checks plus the gallery's:

- the bytes match ``audio.sha256``;
- the file is a PCM WAV the stdlib ``wave`` module can read;
- it runs 3–15 s and agrees with ``audio.duration`` when one is declared.

CI runs it on manifest changes and weekly, so a broken asset surfaces here.

    python scripts/verify_voice_audio.py [manifest.json]
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_manifest import _ALLOWED_AUDIO_HOSTS  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 32 << 20  # backend community.py _MAX_VOICE_AUDIO_BYTES
MIN_SECONDS = 3.0
MAX_SECONDS = 15.0
DURATION_TOLERANCE = 0.25


def _allowed(url: str) -> bool:
    u = urlparse(url or "")
    return u.scheme == "https" and u.hostname in _ALLOWED_AUDIO_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - urllib hook
        return None


def fetch(url: str) -> bytes:
    """GET ``url``, validating each redirect hop against the allow-list."""
    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _ in range(6):
        if not _allowed(current):
            raise ValueError(f"disallowed host in {current!r}")
        try:
            resp = opener.open(urllib.request.Request(current, headers={"User-Agent": "voicestudio-gallery-ci"}), timeout=60)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                current = urljoin(current, e.headers["Location"])
                continue
            raise
        with resp:
            data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("larger than the app's 32 MB download cap")
        return data
    raise ValueError("too many redirects")


def check_clip(data: bytes, audio: dict) -> list[str]:
    """Return problems with one downloaded clip (empty = ok)."""
    errs: list[str] = []
    if not data:
        return ["download was empty"]
    digest = hashlib.sha256(data).hexdigest()
    if digest != str(audio.get("sha256", "")).lower():
        errs.append(f"sha256 mismatch: manifest {audio.get('sha256')!r}, asset {digest}")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
    except (wave.Error, EOFError) as e:
        return errs + [f"not a PCM WAV the app can load ({e})"]
    if rate <= 0:
        return errs + ["WAV declares a zero sample rate"]
    seconds = frames / float(rate)
    if not MIN_SECONDS <= seconds <= MAX_SECONDS:
        errs.append(f"clip runs {seconds:.2f}s; the gallery takes {MIN_SECONDS:g}–{MAX_SECONDS:g}s")
    declared = audio.get("duration")
    if isinstance(declared, (int, float)) and abs(declared - seconds) > DURATION_TOLERANCE:
        errs.append(f"audio.duration says {declared}s but the clip runs {seconds:.2f}s")
    return errs


def verify(manifest: dict, fetcher=fetch) -> list[str]:
    problems: list[str] = []
    for item in manifest.get("items", []):
        if not isinstance(item, dict) or item.get("type") != "voice":
            continue
        audio = item.get("audio") or {}
        label = item.get("id", "<voice>")
        try:
            data = fetcher(audio.get("url", ""))
        except Exception as e:  # network, HTTP or policy failure — all fatal here
            problems.append(f"{label}: could not download {audio.get('url')!r}: {e}")
            continue
        problems += [f"{label}: {e}" for e in check_clip(data, audio)]
    return problems


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else _ROOT / "manifest.json"
    manifest = json.loads(target.read_text(encoding="utf-8"))
    voices = sum(1 for it in manifest.get("items", []) if isinstance(it, dict) and it.get("type") == "voice")
    problems = verify(manifest)
    if problems:
        print(f"✗ {len(problems)} problem(s) with recorded voices:\n")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"✓ {voices} recorded voice(s) download, match their sha256 and load as WAV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
