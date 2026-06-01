#!/usr/bin/env python3
"""Validate ``manifest.json`` before it ships to OmniVoice users.

This is the automated curation gate. Every pull request that touches the
manifest runs this in CI (``.github/workflows/validate-manifest.yml``), so a
malformed entry can never reach the app's gallery.

It mirrors the **runtime** validation in OmniVoice's backend
(``backend/api/routers/community.py`` :: ``validate_item`` / ``is_valid_instruct``
/ ``_safe_audio_url``) and layers the repo's JSON Schema
(``schema/manifest.schema.json``) on top. The guarantee:

    passes here  ==  loads, validates, and renders in the app

so a contributor gets the same verdict in seconds that the app would give at
runtime — instead of submitting a preset that the backend silently drops.

Run locally::

    python scripts/validate_manifest.py            # validates ./manifest.json
    python scripts/validate_manifest.py path.json  # validates a specific file

Exit code 0 = valid, 1 = problems (printed per item/pack). ``jsonschema`` is
optional: if it isn't installed the structural schema pass is skipped (with a
note) and the semantic checks below still run. CI installs it so the full gate
applies there.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _ROOT / "schema" / "manifest.schema.json"

# ── Taxonomy vocabulary ───────────────────────────────────────────────────────
# Keep in sync with ``omnivoice/utils/voice_design.py`` (``_INSTRUCT_CATEGORIES``)
# in the main OmniVoice repo. This is the model's *fixed* instruct vocabulary; an
# instruct token outside it crashes synthesis (the issue-#89 failure mode). It is
# mirrored here — rather than imported — so this gallery repo validates
# standalone, with no dependency on the OmniVoice backend being checked out.
_GENDER = {"male", "female"}
_AGE = {"child", "teenager", "young adult", "middle-aged", "elderly"}
_PITCH = {
    "very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch",
}
_STYLE = {"whisper"}
_ACCENTS = {
    "american accent", "british accent", "australian accent", "chinese accent",
    "canadian accent", "indian accent", "korean accent", "portuguese accent",
    "russian accent", "japanese accent",
}
_DIALECTS = {
    "河南话", "陕西话", "四川话", "贵州话", "云南话", "桂林话",
    "济南话", "石家庄话", "甘肃话", "宁夏话", "青岛话", "东北话",
}
# Mutually-exclusive categories: at most one token from each may appear.
_EXCLUSIVE = [_GENDER, _AGE, _PITCH, _STYLE]
_VALID_TOKENS = _GENDER | _AGE | _PITCH | _STYLE | _ACCENTS | _DIALECTS

# Mirror of backend ``community.py`` constants.
_USE_CASE_IDS = {
    "narration", "conversational", "characters", "social",
    "entertainment", "advertisement", "informative",
}
_ALLOWED_AUDIO_HOSTS = {
    "cdn.jsdelivr.net", "github.com", "raw.githubusercontent.com",
    "objects.githubusercontent.com", "release-assets.githubusercontent.com",
}
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _tokens(instruct: str) -> list[str]:
    return [t.strip() for t in (instruct or "").split(",") if t.strip()]


def _check_instruct(instruct: str) -> list[str]:
    """Return a list of problems with a preset's instruct string (empty = ok)."""
    toks = _tokens(instruct)
    if not toks:
        return ["preset has an empty `instruct` (required for type=preset)"]
    errs: list[str] = []
    for t in toks:
        if t not in _VALID_TOKENS:
            errs.append(f"invalid instruct token {t!r} — not in the voice-design taxonomy")
    tokset = set(toks)
    for cat in _EXCLUSIVE:
        picked = tokset & cat
        if len(picked) > 1:
            errs.append(f"more than one token from a mutually-exclusive category: {sorted(picked)}")
    if (tokset & _ACCENTS) and (tokset & _DIALECTS):
        errs.append("mixes an English accent with a Chinese dialect (never combine the two)")
    return errs


def _check_audio(item: dict) -> list[str]:
    """Return a list of problems with a recorded voice's audio block."""
    errs: list[str] = []
    audio = item.get("audio")
    if not isinstance(audio, dict):
        return ["type=voice requires an `audio` object with a `url`"]
    url = audio.get("url", "")
    try:
        u = urlparse(url or "")
    except Exception:
        u = None
    if u is None or u.scheme != "https":
        errs.append(f"audio.url must be an https URL, got {url!r}")
    elif u.hostname not in _ALLOWED_AUDIO_HOSTS:
        errs.append(
            f"audio.url host {u.hostname!r} is not allow-listed "
            f"(allowed: {sorted(_ALLOWED_AUDIO_HOSTS)})"
        )
    sha = audio.get("sha256", "")
    if not _SHA256_RE.match(sha or ""):
        errs.append("audio.sha256 must be a 64-char hex digest (integrity is enforced at download)")
    return errs


def _check_item(item: dict, index: int) -> list[str]:
    label = item.get("id") or f"items[{index}]"
    errs: list[str] = []
    if not isinstance(item, dict):
        return [f"{label}: not an object"]

    item_id = item.get("id", "")
    if not item_id:
        errs.append(f"{label}: missing `id`")
    elif not _ID_RE.match(item_id):
        errs.append(f"{label}: id must match ^[a-zA-Z0-9_-]+$")

    if not (item.get("name") or "").strip():
        errs.append(f"{label}: missing `name`")
    elif len(item["name"]) > 80:
        errs.append(f"{label}: name exceeds 80 characters")

    item_type = item.get("type")
    if item_type not in ("preset", "voice"):
        errs.append(f"{label}: type must be 'preset' or 'voice', got {item_type!r}")

    if item.get("use_case") not in _USE_CASE_IDS:
        errs.append(f"{label}: use_case must be one of {sorted(_USE_CASE_IDS)}, got {item.get('use_case')!r}")

    if not isinstance(item.get("facets"), dict):
        errs.append(f"{label}: missing `facets` object")

    if item_type == "preset":
        errs += [f"{label}: {e}" for e in _check_instruct(item.get("instruct", ""))]
    elif item_type == "voice":
        errs += [f"{label}: {e}" for e in _check_audio(item)]

    return errs


def _schema_validate(manifest: dict) -> list[str]:
    """Structural validation against schema/manifest.schema.json (best-effort)."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        print("  note: `jsonschema` not installed — skipping JSON Schema pass "
              "(semantic checks still run). `pip install jsonschema` for the full gate.")
        return []
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"could not read schema/manifest.schema.json: {e}"]
    validator = jsonschema.Draft7Validator(schema)
    out = []
    for err in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        out.append(f"schema: {loc}: {err.message}")
    return out


def validate(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path.name} is not valid JSON: {e}"]

    if not isinstance(manifest, dict):
        return [f"{path.name}: top level must be a JSON object"]

    problems += _schema_validate(manifest)

    if manifest.get("schema_version") != 1:
        problems.append(f"schema_version must be 1, got {manifest.get('schema_version')!r}")

    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        problems.append("`items` must be a non-empty array")
        return problems

    seen: set[str] = set()
    for i, item in enumerate(items):
        problems += _check_item(item, i)
        iid = item.get("id") if isinstance(item, dict) else None
        if iid:
            if iid in seen:
                problems.append(f"duplicate item id {iid!r}")
            seen.add(iid)

    # Packs must only reference real item ids.
    for pack in manifest.get("packs", []) or []:
        if not isinstance(pack, dict):
            problems.append("packs[]: each pack must be an object")
            continue
        pid = pack.get("id", "<pack>")
        for ref in pack.get("item_ids", []) or []:
            if ref not in seen:
                problems.append(f"pack {pid!r} references unknown item id {ref!r}")

    return problems


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else _ROOT / "manifest.json"
    if not target.exists():
        print(f"✗ manifest not found: {target}")
        return 1

    print(f"Validating {target.relative_to(_ROOT) if target.is_relative_to(_ROOT) else target} …")
    problems = validate(target)
    if problems:
        print(f"\n✗ {len(problems)} problem(s) found:\n")
        for p in problems:
            print(f"  - {p}")
        print("\nFix the above and push again — these are the same checks the app "
              "applies at runtime (a dropped entry never reaches users).")
        return 1

    try:
        count = len(json.loads(target.read_text(encoding="utf-8")).get("items", []))
    except Exception:
        count = "?"
    print(f"✓ manifest is valid — {count} item(s) will load in the gallery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
