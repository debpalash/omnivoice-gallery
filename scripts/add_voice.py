#!/usr/bin/env python3
"""Curate one recorded-voice submission into ``manifest.json``.

Submissions arrive as whatever GitHub accepts in an issue (usually MP3), but
VoiceStudio only clones from a WAV it has verified against ``audio.sha256``.
Doing the conversion, hashing and manifest edit by hand is where a curated
voice goes wrong — a hash of the MP3 instead of the WAV, a duration copied from
the form, a voice added to the manifest but not to its pack. This does all of
it in one step:

    python scripts/add_voice.py clip.mp3 --id community_pt_br_thalia \\
        --name "Thalia" --use-case conversational --language Portuguese \\
        --gender female --author iluucasz --license CC-BY-4.0 \\
        --ref-text "Olá! Hoje acordei animada, …"

It writes ``build/<id>.wav`` (mono 16-bit PCM, source rate capped at 48 kHz),
adds the item to ``manifest.json`` and the ``community-voices`` pack, bumps
``updated_at``, and prints the ``gh release upload`` command for the WAV.
Requires ``ffmpeg`` on PATH. Run ``scripts/validate_manifest.py`` afterwards;
CI's ``verify_voice_audio.py`` re-downloads the published asset and checks it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_REPO = "debpalash/omnivoice-gallery"
_DEFAULT_RELEASE = "voices-v1"
_COMMUNITY_PACK = {
    "id": "community-voices",
    "name": "Community Voices",
    "description": "Recorded reference voices shared by the community, ready to clone.",
    "icon": "Users",
    "item_ids": [],
}
MIN_SECONDS = 3.0
MAX_SECONDS = 15.0
_MAX_RATE = 48_000


def convert_to_wav(src: Path, dst: Path) -> None:
    """Decode anything ffmpeg reads into mono 16-bit PCM WAV."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True,
    )
    rate = min(int(probe.stdout.strip() or _MAX_RATE), _MAX_RATE)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map_metadata", "-1",
         "-ac", "1", "-ar", str(rate), "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_item(args: argparse.Namespace, sha256: str, duration: float) -> dict:
    item = {
        "id": args.id,
        "type": "voice",
        "name": args.name,
        "use_case": args.use_case,
        "facets": {
            "gender": args.gender,
            "age": args.age,
            "pitch": None,
            "accent": None,
            "whisper": False,
            "lang": args.language,
        },
        "language": args.language,
        "audio": {
            "url": f"https://github.com/{_REPO}/releases/download/{args.release}/{args.id}.wav",
            "ref_text": args.ref_text.strip(),
            "duration": round(duration, 2),
            "sha256": sha256,
        },
        "author": args.author,
        "license": args.license,
        "source": "community",
    }
    if args.icon:
        item["icon"] = args.icon
    if args.submission:
        item["submission"] = args.submission
    return item


def add_to_manifest(manifest: dict, item: dict, today: str) -> dict:
    """Insert or replace ``item`` and list it in the community pack."""
    items = [it for it in manifest.get("items", []) if it.get("id") != item["id"]]
    items.append(item)
    manifest["items"] = items
    packs = manifest.setdefault("packs", [])
    pack = next((p for p in packs if p.get("id") == _COMMUNITY_PACK["id"]), None)
    if pack is None:
        pack = json.loads(json.dumps(_COMMUNITY_PACK))
        packs.append(pack)
    if item["id"] not in pack["item_ids"]:
        pack["item_ids"].append(item["id"])
    manifest["updated_at"] = today
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", type=Path, help="the submitted clip (wav, mp3, …)")
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--use-case", required=True)
    p.add_argument("--language", required=True, help='e.g. "Portuguese" — the app passes it to the cloned profile')
    p.add_argument("--ref-text", required=True, help="exact words spoken in the clip")
    p.add_argument("--author", required=True, help="the submitter's GitHub handle")
    p.add_argument("--license", required=True)
    p.add_argument("--gender", choices=["male", "female"])
    p.add_argument("--age", choices=["child", "teenager", "young adult", "middle-aged", "elderly"])
    p.add_argument("--icon", help="lucide icon name (defaults to the use case's icon in the app)")
    p.add_argument("--submission", help="URL of the submission issue, kept for provenance")
    p.add_argument("--release", default=_DEFAULT_RELEASE)
    p.add_argument("--manifest", type=Path, default=_ROOT / "manifest.json")
    args = p.parse_args(argv)

    wav = _ROOT / "build" / f"{args.id}.wav"
    convert_to_wav(args.source, wav)
    duration = wav_duration(wav)
    if not MIN_SECONDS <= duration <= MAX_SECONDS:
        print(f"✗ clip is {duration:.2f}s — trim it to {MIN_SECONDS:g}–{MAX_SECONDS:g}s first")
        return 1
    digest = sha256_file(wav)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    add_to_manifest(manifest, build_item(args, digest, duration), _dt.date.today().isoformat())
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"✓ {args.id}: {duration:.2f}s, sha256 {digest}")
    print(f"  upload: gh release upload {args.release} {wav.relative_to(_ROOT)} --repo {_REPO} --clobber")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
