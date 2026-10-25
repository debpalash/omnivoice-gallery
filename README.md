# VoiceStudio Gallery

The community content repository for **[VoiceStudio](https://github.com/debpalash/VoiceStudio)** —
a marketplace of ready-to-use **designed voices** and **community-contributed
reference voices**, loaded by the app *after install* so the installer stays
small and content can ship without an app release.

## How the app loads this

VoiceStudio fetches `manifest.json` at runtime over the **jsDelivr CDN**
(no rate limits, global cache, works offline once cached):

```
https://cdn.jsdelivr.net/gh/debpalash/omnivoice-gallery@main/manifest.json
```

Recorded-voice audio is attached to **GitHub Releases** (CDN-backed) and
referenced by URL from the manifest. The app caches everything locally and
keeps working offline; its built-in generated archetypes need no network at
all, so the gallery is never empty.

## What's here

```
manifest.json                 # the index — packs + items (presets & voices)
schema/manifest.schema.json   # JSON Schema the app validates against
.github/ISSUE_TEMPLATE/       # one-click submission forms
CONTRIBUTING.md               # how to add your voice
```

### Item types

- **`preset`** — a *designed* voice: a validated `instruct` string
  (`"female, middle-aged, low pitch, british accent"`). Tiny, instant, no audio.
- **`voice`** — a *recorded* reference clip (audio) for cloning, hosted as a
  Release asset and referenced by URL + SHA-256.

## Contributing

Everyone is welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. The fastest
path is the in-app **"Submit to gallery"** button, which opens a pre-filled
issue here. One rule up front: **no cloning identifiable real people without
their consent.** This is a library of original, designed, and consented voices.

## License

Repository tooling/docs: MIT. Each gallery **item** carries its own `license`
field — respect it. Designed presets shipped by the VoiceStudio team are
OpenRAIL-M (same as the engine).
