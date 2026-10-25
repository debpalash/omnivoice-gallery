"""The audio-present check has to be right about the cases that actually happened.

Both of this gallery's first two voice submissions ticked "I attached the audio
file" and carried no audio — one because GitHub's upload failed and left a
``Failed to upload …`` marker behind, one because no file was ever added. The
form cannot catch either; a self-certification cannot verify itself.

These fixtures are those two issues, plus the shapes a correct submission takes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from check_voice_submission import build_comment, inspect  # noqa: E402

# gallery#2, verbatim in the part that matters.
FAILED_UPLOAD = """### Voice name

adam tu

### Spoken text (exact words in the clip)

[

<!-- Failed to upload "giong_mau_chuan.wav" -->

](url)

### License

ccby40
"""

# gallery#3: nothing was ever attached, every box ticked.
NO_ATTACHMENT = """### Voice name

Normal

### Spoken text (exact words in the clip)

Hi how are you

### Confirmation

- [x] I attached the audio file (3–15s, clean WAV) to this issue.
"""

GOOD = """### Voice name

Calm Narrator

### Spoken text (exact words in the clip)

The quick brown fox jumps over the lazy dog.

[clip.wav](https://github.com/user-attachments/files/12345/clip.wav)
"""


def test_failed_upload_is_not_an_attachment():
    v = inspect([FAILED_UPLOAD])
    assert not v.has_audio
    assert v.failed_uploads == ["giong_mau_chuan.wav"]


def test_missing_attachment_is_detected():
    v = inspect([NO_ATTACHMENT])
    assert not v.has_audio
    assert v.failed_uploads == []


def test_real_attachment_passes():
    assert inspect([GOOD]).has_audio


def test_attachment_in_a_later_comment_counts():
    """The advice we give is "add it in a comment", so a comment has to count —
    otherwise the bot would nag someone who just did what it asked."""
    v = inspect([NO_ATTACHMENT, "here you go",
                 "https://github.com/user-attachments/assets/9/voice.wav"])
    assert v.has_audio


def test_a_zip_counts_as_an_attachment():
    """Zipping is the documented workaround for a type GitHub refuses, so it
    must not be reported as "no audio" — a human opens it from there."""
    v = inspect(["[clip.zip](https://github.com/user-attachments/files/7/clip.zip)"])
    assert v.has_audio


def test_prose_mentioning_a_filename_is_not_an_attachment():
    """The distinction the whole check turns on: naming a file is not sending
    one. Both broken submissions read as though a file were present."""
    v = inspect(["I recorded this as giong_mau_chuan.wav on my laptop"])
    assert not v.has_audio
    assert "giong_mau_chuan.wav" in v.mentioned


def test_an_unrelated_wav_url_is_not_an_attachment():
    """Only GitHub's own upload hosts count. A link to some other site is not a
    file we can move into a Release, and treating it as one would let a
    submission through that a maintainer then cannot action."""
    v = inspect(["my clip: https://example.com/files/clip.wav"])
    assert not v.has_audio


def test_unsupported_extensions_are_named_back():
    v = inspect(["attaching voice.ogg"])
    assert not v.has_audio
    assert v.unsupported_mentioned == ["voice.ogg"]
    assert ".ogg" in build_comment(v)


def test_supported_extension_is_not_called_unsupported():
    """A bare `.wav` mention means the upload didn't happen — but the advice
    must not tell someone their WAV is the wrong format."""
    v = inspect(["attaching voice.wav"])
    assert v.unsupported_mentioned == []


def test_comment_is_empty_when_the_audio_is_there():
    """The workflow posts whatever this returns, so a good submission must
    produce nothing at all rather than a cheerful no-op comment."""
    assert build_comment(inspect([GOOD])) == ""


def test_failed_upload_comment_explains_the_size_limit():
    """The #2 case: the submitter did try. Advice that says "please attach it"
    would be telling them to repeat what just failed."""
    body = build_comment(inspect([FAILED_UPLOAD]))
    assert "failed" in body.lower()
    assert "10 MB" in body
    assert "giong_mau_chuan.wav" in body


def test_missing_attachment_comment_does_not_invent_a_failure():
    """#3 never attempted an upload; telling them it failed would be wrong."""
    body = build_comment(inspect([NO_ATTACHMENT]))
    assert "failed" not in body.lower()
    assert "drag your clip into a comment" in body.lower()
