# Contributing to the OmniVoice Gallery

Thanks for helping build the community voice library! There are two kinds of
contributions: **presets** (designed voices) and **voices** (recorded clips).

## The one hard rule

**Do not submit voices that clone an identifiable real person without their
explicit consent** — no celebrities, politicians, actors, or other named
individuals. This protects contributors, the project, and the people whose
voices would otherwise be cloned without permission. Submissions that do this
will be declined. Original characters, your own voice, consented voice actors,
and public-domain material are all welcome.

Every item must declare a `license` you have the right to grant.

## Option A — submit from inside the app (easiest)

In OmniVoice → **Gallery → Submit to gallery**. The app pre-fills an issue here
with the metadata (and, for designed voices, the validated `instruct`). Review
it and click submit. A maintainer curates it into `manifest.json`.

## Option B — open a Pull Request

### Submitting a preset (designed voice)

Add an object to the `items` array in `manifest.json`:

```json
{
  "id": "my-calm-narrator",
  "type": "preset",
  "name": "Calm Evening Narrator",
  "icon": "BookOpen",
  "use_case": "narration",
  "facets": { "gender": "female", "age": "middle-aged", "pitch": "low pitch",
              "accent": "british accent", "whisper": false, "lang": "English" },
  "instruct": "female, middle-aged, low pitch, british accent",
  "language": "English",
  "sample_script": "A short line the app can render as a preview.",
  "author": "your-github-handle",
  "license": "CC-BY-4.0",
  "source": "community"
}
```

- `instruct` must use **only valid taxonomy tokens** (gender, age, pitch,
  English accent or Chinese dialect, optional `whisper`). The app drops invalid
  presets rather than crashing, so double-check spelling.
- `icon` is a [lucide](https://lucide.dev) component name.

### Submitting a recorded voice

1. Open a PR uploading your clip, **or** attach it to a
   [voice submission issue](../../issues/new?template=voice-submission.yml).
2. A maintainer adds it to a GitHub **Release** and references it from the
   manifest:

```json
{
  "id": "my-recorded-voice",
  "type": "voice",
  "name": "Warm Studio Voice",
  "icon": "Mic",
  "use_case": "narration",
  "facets": { "gender": "male", "age": "young adult", "lang": "English" },
  "audio": {
    "url": "https://github.com/debpalash/omnivoice-gallery/releases/download/voices-v1/my-recorded-voice.wav",
    "ref_text": "The exact words spoken in the clip.",
    "duration": 6.0,
    "sha256": "<sha256 of the wav>"
  },
  "author": "your-github-handle",
  "license": "CC-BY-4.0",
  "source": "community"
}
```

- 3–15 seconds, clean mono WAV, 16 kHz+; the spoken text in `ref_text`.
- **Privacy:** a recorded clip contains a real person's voice. Only submit your
  own voice, or one you have explicit permission to share.

## Validation

Every PR runs **CI** (`.github/workflows/validate-manifest.yml`) that checks
`manifest.json` against `schema/manifest.schema.json` **and** the same semantic
rules the OmniVoice app applies at runtime — so "green CI" means "loads and
renders in the app". The gate verifies:

- every preset `instruct` uses only valid taxonomy tokens, at most one per
  category, and never mixes an English accent with a Chinese dialect;
- each `use_case` is one of the seven the app knows;
- recorded-voice `audio.url` points at an allow-listed host (jsDelivr / GitHub)
  over https and carries a 64-char `sha256` for the integrity check;
- item ids are unique and packs only reference real items.

Run it yourself before opening the PR:

```bash
python scripts/validate_manifest.py        # pip install jsonschema for the schema pass
```

Keep `manifest.json` valid JSON and bump `updated_at`.
