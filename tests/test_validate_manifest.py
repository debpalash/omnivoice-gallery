"""The manifest gate has to reject what the app would drop or fail on.

Each case is a voice that would pass the old checks and break on a user's
machine: an MP3 the app refuses after download, a clip with no transcript to
condition on, a Portuguese clip that would be cloned as English.
"""
import copy
import hashlib
import io
import json
import os
import sys
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import add_voice  # noqa: E402
from validate_manifest import _check_item, validate  # noqa: E402
from verify_voice_audio import check_clip, verify  # noqa: E402

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

VOICE = {
    "id": "community_test_voice",
    "type": "voice",
    "name": "Test Voice",
    "use_case": "narration",
    "facets": {"gender": "female", "lang": "Portuguese"},
    "language": "Portuguese",
    "audio": {
        "url": "https://github.com/debpalash/omnivoice-gallery/releases/download/voices-v1/community_test_voice.wav",
        "ref_text": "Olá, tudo bem?",
        "duration": 5.0,
        "sha256": "0" * 64,
    },
    "author": "someone",
    "license": "CC-BY-4.0",
    "source": "community",
}


def _voice(**audio):
    v = copy.deepcopy(VOICE)
    v["audio"].update(audio)
    return v


def _wav(seconds: float, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def test_shipped_manifest_is_valid():
    path = os.path.join(_ROOT, "manifest.json")
    from pathlib import Path

    assert validate(Path(path)) == []


def test_well_formed_voice_passes():
    assert _check_item(VOICE, 0) == []


def test_mp3_url_is_rejected():
    errs = _check_item(_voice(url=VOICE["audio"]["url"].replace(".wav", ".mp3")), 0)
    assert any(".wav" in e for e in errs)


def test_missing_ref_text_is_rejected():
    assert any("ref_text" in e for e in _check_item(_voice(ref_text="  "), 0))


def test_out_of_range_duration_is_rejected():
    assert any("duration" in e for e in _check_item(_voice(duration=42), 0))
    assert any("duration" in e for e in _check_item(_voice(duration=True), 0))


def test_missing_language_is_rejected():
    v = copy.deepcopy(VOICE)
    del v["language"]
    assert any("language" in e for e in _check_item(v, 0))


def test_missing_license_is_rejected():
    v = copy.deepcopy(VOICE)
    v["license"] = ""
    assert any("license" in e for e in _check_item(v, 0))


def test_overlong_id_is_rejected():
    v = copy.deepcopy(VOICE)
    v["id"] = "x" * 129
    assert any("id must match" in e for e in _check_item(v, 0))


# ── verify_voice_audio ────────────────────────────────────────────────────────

def test_matching_clip_passes():
    data = _wav(5.0)
    audio = {"sha256": hashlib.sha256(data).hexdigest(), "duration": 5.0}
    assert check_clip(data, audio) == []


def test_changed_bytes_fail_the_hash():
    data = _wav(5.0)
    errs = check_clip(data, {"sha256": "0" * 64})
    assert any("sha256 mismatch" in e for e in errs)


def test_mp3_bytes_are_not_a_wav():
    data = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 100
    errs = check_clip(data, {"sha256": hashlib.sha256(data).hexdigest()})
    assert any("not a PCM WAV" in e for e in errs)


def test_wrong_length_and_stale_duration_fail():
    data = _wav(20.0)
    errs = check_clip(data, {"sha256": hashlib.sha256(data).hexdigest(), "duration": 6.0})
    assert any("clip runs 20.00s" in e for e in errs)
    assert any("audio.duration says" in e for e in errs)


def test_download_failure_is_reported_not_raised():
    def boom(url):
        raise OSError("404")

    problems = verify({"items": [VOICE]}, fetcher=boom)
    assert problems and "could not download" in problems[0]


# ── add_voice ─────────────────────────────────────────────────────────────────

def test_add_voice_creates_pack_and_replaces_in_place():
    manifest = {"schema_version": 1, "items": [{"id": "other"}], "packs": []}
    add_voice.add_to_manifest(manifest, dict(VOICE), "2026-10-26")
    add_voice.add_to_manifest(manifest, dict(VOICE, name="Renamed"), "2026-10-27")
    ids = [it["id"] for it in manifest["items"]]
    assert ids == ["other", VOICE["id"]]
    assert manifest["items"][-1]["name"] == "Renamed"
    pack = next(p for p in manifest["packs"] if p["id"] == "community-voices")
    assert pack["item_ids"] == [VOICE["id"]]
    assert manifest["updated_at"] == "2026-10-27"


def test_add_voice_output_validates():
    class Args:
        id = VOICE["id"]
        name = "Test Voice"
        use_case = "narration"
        language = "Portuguese"
        gender = "female"
        age = None
        ref_text = " Olá, tudo bem? "
        author = "someone"
        license = "CC-BY-4.0"
        icon = None
        submission = None
        release = "voices-v1"

    item = add_voice.build_item(Args, "a" * 64, 5.004)
    assert item["audio"]["ref_text"] == "Olá, tudo bem?"
    assert item["audio"]["duration"] == 5.0
    assert _check_item(json.loads(json.dumps(item)), 0) == []
