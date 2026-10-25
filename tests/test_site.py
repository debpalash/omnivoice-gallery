"""The public page renders community text, so it must never render it as markup."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"))

from build import build  # noqa: E402

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _manifest():
    with open(os.path.join(_ROOT, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_every_item_gets_a_card():
    m = _manifest()
    assert build(m).count('<article class="card"') == len(m["items"])


def test_community_text_is_escaped():
    m = copy.deepcopy(_manifest())
    voice = next(i for i in m["items"] if i["type"] == "voice")
    voice["name"] = '<img src=x onerror=alert(1)>'
    voice["audio"]["ref_text"] = '"><script>alert(1)</script>'
    voice["author"] = 'evil"><script>'
    html = build(m)
    assert "<img src=x" not in html and "<script>alert" not in html
    assert 'href="https://github.com/evil' not in html  # not a valid handle → no link


def test_handles_link_and_team_does_not():
    html = build(_manifest())
    assert 'href="https://github.com/iluucasz"' in html
    assert 'href="https://github.com/VoiceStudio"' not in html
