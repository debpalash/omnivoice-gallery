#!/usr/bin/env python3
"""Does a [voice] submission actually carry an audio clip?

The submission form asks contributors to attach a clip and to tick a box saying
they did. Both of the first two real submissions ticked the box and carried no
audio — one because GitHub's upload failed and left ``Failed to upload …`` in
the body, one because no file was ever added. A self-certification cannot
verify itself, so something has to look.

This is that something. It reads the issue body plus every comment, and reports
whether an audio attachment is present, so the workflow can tell the submitter
straight away instead of leaving the issue to go stale.

Pure text in, verdict out: no network, no GitHub client, so it is testable.
"""
from __future__ import annotations

import re

#: Extensions GitHub actually accepts for upload. `.ogg`, `.flac`, `.m4a` and
#: `.aac` are deliberately absent — GitHub rejects them, which is one of the
#: ways an upload "just fails" with no explanation the submitter can act on.
GITHUB_AUDIO_EXTS = ("wav", "mp3")
#: A zip is the documented workaround for anything else, so it counts as an
#: attachment for triage even though a human still has to open it.
ARCHIVE_EXTS = ("zip",)

#: GitHub rewrites uploads to these hosts. Matching the host as well as the
#: extension keeps a bare mention of "my clip.wav" in prose from counting.
_ATTACHMENT_HOSTS = (
    "github.com/user-attachments/",
    "githubusercontent.com/",
    "github.com/[^/]+/[^/]+/(?:files|assets)/",
)

_ATTACHMENT_RE = re.compile(
    r"https?://(?:[^\s)]*?(?:%s))[^\s)\"']*?\.(%s)\b"
    % ("|".join(_ATTACHMENT_HOSTS), "|".join(GITHUB_AUDIO_EXTS + ARCHIVE_EXTS)),
    re.IGNORECASE,
)

# GitHub leaves this literal marker in the text when an upload fails, which is
# the single most useful signal here: it distinguishes "never tried" from
# "tried and the platform said no", and those need different advice.
_FAILED_UPLOAD_RE = re.compile(r"Failed to upload\s+\"?([^\"\n>]+)", re.IGNORECASE)

#: An audio-looking filename that is NOT a link — someone typed or pasted the
#: name, or the upload failed. Used only to make the report specific.
#:
#: No spaces in the character class: allowing them made the match swallow the
#: words in front of it ("I recorded this as clip.wav"), and a filename echoed
#: back with a sentence fragment attached reads as a bug in the bot. Names that
#: really do contain spaces reach us through the quoted `Failed to upload "…"`
#: marker, which is handled above and keeps them intact.
_BARE_FILENAME_RE = re.compile(
    r"(?<![\w./\\-])([\w.\-]+\.(?:wav|mp3|ogg|flac|m4a|aac))\b", re.IGNORECASE
)


class Verdict:
    """Result of inspecting one submission."""

    def __init__(self, has_audio: bool, failed_uploads: list, mentioned: list):
        self.has_audio = has_audio
        self.failed_uploads = failed_uploads
        self.mentioned = mentioned

    @property
    def unsupported_mentioned(self) -> list:
        """Filenames whose extension GitHub will refuse, worth naming back."""
        bad = []
        for name in self.mentioned:
            ext = name.rsplit(".", 1)[-1].lower()
            if ext not in GITHUB_AUDIO_EXTS:
                bad.append(name)
        return bad


def inspect(texts) -> Verdict:
    """``texts`` = the issue body followed by every comment body."""
    blob = "\n\n".join(t for t in texts if t)
    has_audio = bool(_ATTACHMENT_RE.search(blob))
    failed = [m.group(1).strip() for m in _FAILED_UPLOAD_RE.finditer(blob)]
    # Only report bare filenames when there is no real attachment; otherwise
    # prose like "recorded in sample.wav" would produce noise on a good issue.
    mentioned = [] if has_audio else [
        m.group(1).strip() for m in _BARE_FILENAME_RE.finditer(blob)
    ]
    return Verdict(has_audio, failed, mentioned)


def build_comment(verdict: Verdict) -> str:
    """The message to post when audio is missing. None when nothing to say."""
    if verdict.has_audio:
        return ""
    lines = [
        "Thanks for the submission! One thing is missing before a maintainer "
        "can add this to the gallery: **the audio clip itself**.",
        "",
    ]
    if verdict.failed_uploads:
        names = ", ".join(f"`{n}`" for n in dict.fromkeys(verdict.failed_uploads))
        lines += [
            f"GitHub reported that the upload of {names} **failed**, so the file "
            "never reached the issue — that is why the box asking whether you "
            "attached it does not tell us anything. It is usually one of:",
            "",
            "- **over 10 MB.** An uncompressed WAV runs about 10 MB per minute at "
            "48 kHz stereo. A 3–15 second clip should be far under the limit, so "
            "if yours is not, trim it, or export mono at 16–24 kHz — which is "
            "what voice cloning uses anyway, so you lose nothing.",
            "- **a file type GitHub refuses.** Only `.wav` and `.mp3` are accepted "
            "for audio; `.ogg`, `.flac`, `.m4a` and `.aac` are not. Convert it, or "
            "put the file in a `.zip`.",
            "- **a flaky upload.** Retrying in a comment works more often than "
            "retrying inside the form.",
        ]
    elif verdict.unsupported_mentioned:
        names = ", ".join(f"`{n}`" for n in dict.fromkeys(verdict.unsupported_mentioned))
        lines += [
            f"{names} is mentioned, but GitHub only accepts `.wav` and `.mp3` for "
            "audio uploads — `.ogg`, `.flac`, `.m4a` and `.aac` are refused. "
            "Convert the clip, or put it in a `.zip`.",
        ]
    else:
        lines += [
            "No audio file arrived with this issue. Drag your clip into a comment "
            "below — GitHub accepts `.wav` and `.mp3` up to 10 MB.",
        ]
    lines += [
        "",
        "What we need: **3–15 seconds, clean mono WAV, 16 kHz or higher**, and the "
        "spoken text matching the recording word for word.",
        "",
        "Just add it as a comment here — no need to open a new issue.",
    ]
    return "\n".join(lines)
