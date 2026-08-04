"""Issue forms must ask only for labels that exist, and stay in lockstep.

Every label an issue form declares that the repository does not have is
silently DROPPED by GitHub — no warning on the issue, nothing in any log. This
gallery's forms had asked for `submission` and `voice` since they were written,
neither label existed, and both real submissions arrived with no labels at all.
Nothing surfaced that until a workflow was written to key off one of them.

The labels live in the repo, not in the tree, so this cannot verify they exist
from here. What it can do is keep the *declared* set to a known list that a
maintainer updates deliberately — turning "a label was invented in a form" from
an invisible no-op into a failing check.
"""
import glob
import os

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FORMS = sorted(glob.glob(os.path.join(_ROOT, ".github", "ISSUE_TEMPLATE", "*.yml")))

#: Labels that exist in the repository. Adding one here means creating it in
#: the repo too (Settings → Labels, or `gh label create`), in the same change.
KNOWN_LABELS = {
    "submission", "voice", "preset", "needs-audio",
    "bug", "documentation", "duplicate", "enhancement",
    "good first issue", "help wanted", "invalid", "question", "wontfix",
}


def _forms():
    for path in _FORMS:
        with open(path, encoding="utf-8") as fh:
            yield path, yaml.safe_load(fh)


def test_at_least_one_form_exists():
    """Guards the rest of this file from passing vacuously if the glob breaks."""
    assert _FORMS, "no issue forms found — did the directory move?"


def test_every_form_parses():
    """A form that does not parse silently reverts to a blank issue body, which
    is how a malformed submission arrives with nobody noticing the template
    broke."""
    for path, doc in _forms():
        assert isinstance(doc, dict), f"{path} is not a mapping"
        assert doc.get("body"), f"{path} has no body fields"


def test_declared_labels_exist():
    for path, doc in _forms():
        for label in doc.get("labels", []):
            assert label in KNOWN_LABELS, (
                f"{os.path.basename(path)} declares the label {label!r}, which "
                f"is not in KNOWN_LABELS. If the repository really has it, add "
                f"it here; if not, GitHub will silently drop it and every "
                f"submission will arrive unlabelled."
            )


def test_forms_carry_a_title_prefix():
    """Automation keys off the `[voice]` / `[preset]` prefix precisely because
    a label can be dropped and a title cannot."""
    for path, doc in _forms():
        title = doc.get("title", "")
        assert title.startswith("["), (
            f"{os.path.basename(path)} has no `[...]` title prefix; the "
            f"submission workflow uses it as the half of its trigger that "
            f"cannot be silently dropped"
        )


def test_license_is_a_dropdown_everywhere():
    """A free-text licence field collected "How are you" as a licence. Both
    forms moved to a dropdown; keeping them in lockstep is the point."""
    for path, doc in _forms():
        for field in doc["body"]:
            if field.get("id") == "license":
                assert field["type"] == "dropdown", (
                    f"{os.path.basename(path)} takes a free-text licence again "
                    f"— a maintainer cannot act on an arbitrary string"
                )
                options = field["attributes"]["options"]
                assert any("Other" in o for o in options), (
                    f"{os.path.basename(path)} has no escape hatch, so a "
                    f"legitimate licence outside the list cannot be submitted"
                )
                break
        else:
            raise AssertionError(f"{os.path.basename(path)} has no licence field")
