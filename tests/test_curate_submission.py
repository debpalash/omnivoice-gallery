"""The curation bot must act on what a real submission looks like.

Fixtures are gallery #9 and #10 verbatim — filed before the form asked for a
language, with the clip attached inside a text field in #10 — so the bot is
tested against the shapes people actually send, not an idealised form.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from curate_submission import (  # noqa: E402
    CurationError, latest_audio_url, parse_form, plan, slug, transcript_score,
)

_FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _body(n):
    with open(os.path.join(_FIX, f"issue_{n}.md"), encoding="utf-8") as fh:
        return fh.read()


def test_old_form_without_language_is_refused_with_a_fix():
    with pytest.raises(CurationError) as e:
        plan(10, "iluucasz", _body(10), [], set())
    assert "Language" in str(e.value)


def test_language_comment_completes_an_old_submission():
    p = plan(10, "iluucasz", _body(10), ["Language: Portuguese (Brazil)"], set())
    assert p.language == "Portuguese"  # region dropped: the app has no variants
    assert p.license == "CC-BY-4.0"
    assert p.use_case == "narration"
    assert p.audio_url.endswith("lucas.mp3")
    # The clip was attached inside the spoken-text field; the link must not
    # end up in ref_text, which the engine conditions on.
    assert "http" not in p.ref_text and p.ref_text.startswith("Voz masculina brasileira")
    assert p.id == "community_portuguese_lucas_voice"


def test_id_collision_gets_the_issue_number():
    p = plan(10, "u", _body(10), ["language: Portuguese"], {"community_portuguese_lucas_voice"})
    assert p.id == "community_portuguese_lucas_voice_10"


def test_new_form_submission_plans_cleanly():
    body = """### Voice name

Warm Studio Voice

### Use case

conversational

### Language

Dutch

### Voice gender

female

### Spoken text (exact words in the clip)

Hallo, dit is mijn stem.

### License

CC-BY-SA-4.0 (credit required, share-alike)

### Anything else

[clip.wav](https://github.com/user-attachments/files/1/clip.wav)
"""
    p = plan(42, "someone", body, [], set())
    assert (p.language, p.gender, p.license) == ("Dutch", "female", "CC-BY-SA-4.0")
    assert p.id == "community_dutch_warm_studio_voice"


def test_other_license_and_missing_clip_are_both_reported():
    body = "### Voice name\n\nX\n\n### Use case\n\nsocial\n\n### Language\n\nGerman\n\n" \
           "### Spoken text (exact words in the clip)\n\nHallo\n\n### License\n\nOther (name it below)\n"
    with pytest.raises(CurationError) as e:
        plan(1, "u", body, [], set())
    msg = str(e.value)
    assert "License" in msg and "attachment" in msg


def test_reupload_in_a_comment_wins():
    texts = ["[a.wav](https://github.com/user-attachments/files/1/a.wav)",
             "retry: [b.mp3](https://github.com/user-attachments/files/2/b.mp3)"]
    assert latest_audio_url(texts).endswith("b.mp3")


def test_zip_is_not_picked_as_audio():
    assert latest_audio_url(["[c.zip](https://github.com/user-attachments/files/3/c.zip)"]) is None


def test_transcript_score_ignores_case_and_punctuation():
    assert transcript_score("Olá! Que surpresa, vai ser um ótimo dia!",
                            "olá que surpresa vai ser um ótimo dia") == 1.0
    assert transcript_score("Voz masculina brasileira", "something else entirely") < 0.5


def test_parse_form_and_slug():
    assert parse_form("### A\n\nx\n\n### B\n\n_No response_")["b"] == "_No response_"
    assert slug("Thalia Voice — Brasil") == "thalia_voice_brasil"


def test_already_curated_issue_is_refused():
    with pytest.raises(CurationError) as e:
        plan(10, "iluucasz", _body(10), ["Language: Portuguese"], set(), {10})
    assert "already in the gallery" in str(e.value)
