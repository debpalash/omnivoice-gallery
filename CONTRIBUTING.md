# Contributing to the VoiceStudio Gallery

Thanks for helping build the community voice library! There are two kinds of
contributions: **presets** (designed voices) and **voices** (recorded clips).

## The one hard rule

**Do not submit voices that clone an identifiable real person without their
explicit consent** — no celebrities, politicians, actors, or other named
individuals. This protects contributors, the project, and the people whose
voices would otherwise be cloned without permission. Submissions that do this
will be declined. Original characters, your own voice, consented voice actors,
and public-domain material are all welcome.

Every item must declare a `license` you have the right to grant. The submission
forms offer `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC0-1.0` and `OpenRAIL-M`, plus an
"Other" option you name in the notes box — pick from the list where you can, so
a maintainer does not have to interpret it.

## Option A — submit from inside the app (easiest)

In VoiceStudio → **Gallery → Submit to gallery**. The app pre-fills an issue here
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
- `language` is required: the app passes it to the cloned profile and would
  otherwise assume English.
- **Privacy:** a recorded clip contains a real person's voice. Only submit your
  own voice, or one you have explicit permission to share.

#### If the upload fails

GitHub accepts `.wav` and `.mp3` up to **10 MB** in an issue. When an upload
fails you get `Failed to upload …` left in the text box instead of a link, and
the file never reaches us — so the issue looks complete and is not. Usual
causes:

| Cause | Fix |
| --- | --- |
| Over 10 MB | An uncompressed WAV is roughly 10 MB per minute at 48 kHz stereo. A 3–15s clip should be well under that — trim it, or export mono at 16–24 kHz, which is what cloning uses anyway. |
| A type GitHub refuses | `.ogg`, `.flac`, `.m4a` and `.aac` are not accepted. Convert to WAV or MP3, or put the file in a `.zip`. |
| A flaky upload | Retry in a **comment** on the issue rather than inside the form. |

Adding the clip in a comment is always fine — there is no need to open a new
issue. A bot checks each `[voice]` issue for an attachment and labels it
`needs-audio` until one arrives, so nothing gets silently lost.

### Curating a voice (maintainers)

**Usual path: the bot.** Listen to the clip, check the consent rule, then add
the **`approved`** label to the issue. `.github/workflows/curate-voice.yml`
fetches the latest clip (from the submitter or a maintainer), converts, trims
and normalises it, uploads it to the `voices-v1` prerelease and opens a PR that
closes the issue. The PR shows how closely a Whisper transcript matches the
submitted text, and flags it below 75%. If a field can't be used (an "Other"
licence, no clip, no language), the bot comments with what's missing and
removes the label. A `Language: X` comment fills in the language on older
submissions. Closing the PR without merging deletes the uploaded clip.

**By hand:** `scripts/add_voice.py` turns a submitted clip into a manifest entry in one
step: it converts the file (MP3 is fine) to mono 16-bit WAV with `ffmpeg`,
trims leading and trailing silence, normalises loudness to -16 LUFS, checks
the length, hashes the WAV, adds the item and the `community-voices`
pack entry, bumps `updated_at`, and prints the upload command.

```bash
python scripts/add_voice.py clip.mp3 --id community_pt_br_name --name "Name" \
  --use-case narration --language Portuguese --gender female \
  --author their-handle --license CC-BY-4.0 \
  --submission https://github.com/debpalash/omnivoice-gallery/issues/N \
  --ref-text "The exact words in the clip."
gh release upload voices-v1 build/community_pt_br_name.wav --repo debpalash/omnivoice-gallery
python scripts/verify_voice_audio.py
```

Check `ref_text` against the recording (a speech-to-text pass is the quick
way) and listen for the consent rule before curating. Never replace a Release
asset in place: the app pins its SHA-256, so upload a new file instead. Voice
releases (`voices-*`) must be **prereleases**: VoiceStudio's signed preview
gallery downloads from this repo's `releases/latest`, and CI fails if a voice
release could take that slot.

Note for maintainers: a label an issue form declares but the repository does not
have is silently dropped by GitHub, with no warning anywhere — which is why the
submission automation triggers on the `[voice]` title prefix as well as the
label, and why `tests/test_issue_forms.py` pins the declared set.

## Validation

Every PR runs **CI** (`.github/workflows/validate-manifest.yml`) that checks
`manifest.json` against `schema/manifest.schema.json` **and** the same semantic
rules the VoiceStudio app applies at runtime — so "green CI" means "loads and
renders in the app". The gate verifies:

- every preset `instruct` uses only valid taxonomy tokens, at most one per
  category, and never mixes an English accent with a Chinese dialect;
- each `use_case` is one of the seven the app knows;
- recorded-voice `audio.url` points at a `.wav` on an allow-listed host
  (jsDelivr / GitHub) over https and carries a 64-char `sha256` for the
  integrity check, a non-empty `ref_text`, and a 3–15s `duration`;
- every item has a `language` and a `license`, and `updated_at` is a date;
- item ids are unique and packs only reference real items.

Run it yourself before opening the PR:

```bash
python scripts/validate_manifest.py        # pip install jsonschema for the schema pass
```

A second job, `scripts/verify_voice_audio.py`, downloads every recorded voice
the way the app does and checks its hash, WAV container and length. It runs on
manifest changes and weekly, so a deleted or altered Release asset fails CI
rather than a user's download.

Keep `manifest.json` valid JSON and bump `updated_at`. After a merge to `main`,
a workflow purges jsDelivr's cache so the app sees the change within minutes
rather than up to 12 hours.
