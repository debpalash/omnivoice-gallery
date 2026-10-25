#!/usr/bin/env python3
"""Turn an approved ``[voice]`` submission issue into a ready-to-merge PR.

Run by ``.github/workflows/curate-voice.yml`` when a maintainer adds the
``approved`` label. Curating by hand took ~10 steps per voice (download,
convert, hash, check the transcript, upload, edit the manifest, open a PR) and
every one of them is a place to slip. Approval stays a human decision — the
label is the yes, given after listening for the consent rule — and everything
after it is this script:

1. ``plan``: read the issue form, pick the latest attached clip, and refuse
   with a specific message if a field cannot be acted on.
2. download the clip (GitHub attachment hosts only, size-capped), then
   ``add_voice.py`` converts, trims, normalises and adds it to the manifest.
3. transcribe the WAV and compare it with the submitted text; a mismatch is
   reported in the PR for the maintainer, not silently accepted or refused.

The pure parts (form parsing, the plan, transcript scoring) are tested in
``tests/test_curate_submission.py``; the workflow does the GitHub calls.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_voice_submission import _ATTACHMENT_RE  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
USE_CASES = {
    "narration", "conversational", "characters", "social",
    "entertainment", "advertisement", "informative",
}
#: Dropdown text → manifest licence. "Other" needs a human to read the notes.
LICENSES = {
    "CC-BY-4.0": "CC-BY-4.0",
    "CC-BY-SA-4.0": "CC-BY-SA-4.0",
    "CC0-1.0": "CC0-1.0",
    "OpenRAIL-M": "OpenRAIL-M",
}
#: Hosts GitHub serves issue attachments from, including redirect targets.
_DOWNLOAD_HOSTS = {
    "github.com", "objects.githubusercontent.com",
    "private-user-images.githubusercontent.com", "user-images.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_MAX_DOWNLOAD = 10 << 20  # GitHub's own attachment limit
_NO_RESPONSE = {"", "_no response_", "none"}
#: Below this the PR flags the transcript as a likely mismatch. Whisper small
#: scores a word-perfect Portuguese clip (#10) at 0.84 — it splits and drops
#: accents — so the bar sits under that.
TRANSCRIPT_MATCH = 0.75


class CurationError(ValueError):
    """The submission cannot be curated as-is; the message says what to fix."""


@dataclass
class Plan:
    issue: int
    id: str
    name: str
    use_case: str
    language: str
    gender: str | None
    ref_text: str
    license: str
    author: str
    audio_url: str


def parse_form(body: str) -> dict[str, str]:
    """Issue-form body → {lowercased heading: answer}."""
    fields: dict[str, str] = {}
    current = None
    lines: list[str] = []
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                fields[current] = "\n".join(lines).strip()
            current, lines = m.group(1).strip().lower(), []
        elif current is not None:
            lines.append(line)
    if current is not None:
        fields[current] = "\n".join(lines).strip()
    return fields


def _answer(fields: dict[str, str], *prefixes: str) -> str:
    for key, value in fields.items():
        if key.startswith(prefixes):
            return "" if value.strip().lower() in _NO_RESPONSE else value.strip()
    return ""


def _strip_attachments(text: str) -> str:
    """Drop attachment links/markers someone typed into a text field."""
    text = _ATTACHMENT_RE.sub("", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", text)
    return " ".join(text.split())


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def latest_audio_url(texts: list[str]) -> str | None:
    """The last wav/mp3 attachment across body + comments (a re-upload wins)."""
    found = None
    for text in texts:
        for m in _ATTACHMENT_RE.finditer(text or ""):
            if m.group(1).lower() in ("wav", "mp3"):
                found = m.group(0)
    return found


def plan(issue: int, author: str, body: str, comments: list[str], existing_ids: set[str],
         curated_issues: set[int] = frozenset()) -> Plan:
    if issue in curated_issues:
        raise CurationError(f"- #{issue} is already in the gallery; edit its manifest entry instead.")
    fields = parse_form(body)
    problems: list[str] = []

    name = _strip_attachments(_answer(fields, "voice name"))
    if not name or len(name) > 80:
        problems.append("**Voice name** is missing or longer than 80 characters.")

    use_case = _answer(fields, "use case").lower()
    if use_case not in USE_CASES:
        problems.append(f"**Use case** must be one of: {', '.join(sorted(USE_CASES))}.")

    # "Portuguese (Brazil)" → "Portuguese": the app's language list has no
    # regional variants, and an unknown label would reach the engine verbatim.
    # A `Language: X` comment line fills the field for submissions made before
    # the form asked for it, and lets a maintainer correct it.
    language = _answer(fields, "language")
    for comment in comments:
        for m in re.finditer(r"^\s*language:\s*(.+?)\s*$", comment or "", re.I | re.M):
            language = m.group(1)
    language = re.sub(r"\s*\(.*?\)\s*", "", language).strip().strip("`*")
    if not language:
        problems.append("**Language** is missing — add it in a comment (e.g. `Language: Portuguese`).")

    gender = _answer(fields, "voice gender").lower() or None
    if gender not in (None, "male", "female"):
        gender = None

    ref_text = _strip_attachments(_answer(fields, "spoken text"))
    if not ref_text:
        problems.append("**Spoken text** is missing — it must match the recording word for word.")

    license_answer = _answer(fields, "license")
    license_id = next((v for k, v in LICENSES.items() if license_answer.startswith(k + " ") or license_answer == k), None)
    if license_id is None:
        problems.append(
            f"**License** `{license_answer or 'none'}` needs a maintainer to read it — "
            "curate this one by hand with `scripts/add_voice.py`."
        )

    audio_url = latest_audio_url([body, *comments])
    if audio_url is None:
        problems.append("No `.wav` or `.mp3` attachment found (a `.zip` has to be unpacked by hand).")

    if problems:
        raise CurationError("\n".join(f"- {p}" for p in problems))

    lang_slug = slug(language) or "xx"
    base = f"community_{lang_slug}_{slug(name) or 'voice'}"[:110]
    item_id = base if base not in existing_ids else f"{base}_{issue}"
    return Plan(issue, item_id, name, use_case, language, gender, ref_text, license_id, author, audio_url)


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"\w+", text)


def transcript_score(expected: str, heard: str) -> float:
    """Word-level similarity, 0–1, ignoring case and punctuation."""
    a, b = _words(expected), _words(heard)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def download(url: str, dest: Path) -> None:
    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _ in range(6):
        parsed = urlparse(current)
        if parsed.scheme != "https" or parsed.hostname not in _DOWNLOAD_HOSTS:
            raise CurationError(f"- The attachment points at a host I won't fetch: `{parsed.hostname}`.")
        try:
            resp = opener.open(urllib.request.Request(current, headers={"User-Agent": "voicestudio-gallery-bot"}), timeout=60)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                current = urljoin(current, e.headers["Location"])
                continue
            raise
        with resp:
            data = resp.read(_MAX_DOWNLOAD + 1)
        if len(data) > _MAX_DOWNLOAD:
            raise CurationError("- The attachment is larger than 10 MB.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return
    raise CurationError("- The attachment redirected too many times.")


def transcribe(wav: Path) -> str:
    from faster_whisper import WhisperModel  # CI-only dependency

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(wav), beam_size=5)
    return " ".join(s.text.strip() for s in segments)


def _cmd_plan(args) -> int:
    issue = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
    manifest = json.loads((_ROOT / "manifest.json").read_text(encoding="utf-8"))
    existing = {it.get("id") for it in manifest.get("items", [])}
    curated = {
        int(m.group(1)) for it in manifest.get("items", [])
        if (m := re.search(r"/issues/(\d+)$", str(it.get("submission", ""))))
    }
    try:
        p = plan(issue["number"], issue["author"], issue["body"], issue.get("comments", []), existing, curated)
    except CurationError as e:
        Path(args.out).write_text(json.dumps({"error": str(e)}), encoding="utf-8")
        print(str(e))
        return 0  # a refusal is a result, reported on the issue — not a crash
    Path(args.out).write_text(json.dumps(asdict(p), ensure_ascii=False), encoding="utf-8")
    print(f"plan: {p.id}")
    return 0


def _cmd_fetch(args) -> int:
    p = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    ext = Path(urlparse(p["audio_url"]).path).suffix.lower() or ".wav"
    download(p["audio_url"], Path(args.dest_dir) / f"submission{ext}")
    print(Path(args.dest_dir) / f"submission{ext}")
    return 0


def _cmd_score(args) -> int:
    p = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    heard = transcribe(Path(args.wav))
    score = transcript_score(p["ref_text"], heard)
    result = {"heard": heard, "score": round(score, 3), "ok": score >= TRANSCRIPT_MATCH}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"transcript match {score:.0%}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("issue_json")
    a.add_argument("out")
    a = sub.add_parser("fetch")
    a.add_argument("plan")
    a.add_argument("dest_dir")
    a = sub.add_parser("score")
    a.add_argument("plan")
    a.add_argument("wav")
    a.add_argument("out")
    args = ap.parse_args(argv)
    return {"plan": _cmd_plan, "fetch": _cmd_fetch, "score": _cmd_score}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
