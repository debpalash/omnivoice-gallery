# Security Policy

## Supported versions

This repository is content, not a release line: `manifest.json` on `main` is
the only version [VoiceStudio](https://github.com/debpalash/VoiceStudio) loads,
so security fixes always land on `main`. The app that reads it is covered by
VoiceStudio's own [security policy](https://github.com/debpalash/VoiceStudio/security/policy).

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Report them
privately instead:

1. **GitHub Security Advisories** (preferred) —
   [report a vulnerability](https://github.com/debpalash/VoiceStudio/security/advisories/new)
   on the VoiceStudio repository, which owns the gallery loader.
2. **Email** — **security@voicestudio.sh**

Include what you found, how to reproduce it, and the impact you expect. We
acknowledge reports within **48 hours** and agree on disclosure with you once
a fix has shipped.

## What counts here

- A manifest entry, script or workflow that would make the app fetch from a
  host outside the allow-list, skip the SHA-256 audio integrity check, or load
  something other than data (the gallery is JSON and audio, never code).
- A workflow that leaks its token or can be steered by issue or PR text.
- A voice clip that impersonates an identifiable real person without consent —
  report that privately too, so the clip can be pulled before it spreads.

Flaws in the VoiceStudio app itself belong in the VoiceStudio repository.
