"""The rule cases in tools/tests/cases: each case is a chapter and the findings that it gives.

Each file of cases holds the cases of one or more rules of book/doc/doc.rst. A case
is a table [[case]] with these keys:

    name            what the case shows
    replace         [[case.replace]] tables of old and new text: each edit of GOOD,
                    whose old text occurs once in the chapter
    append          text to add after the chapter
    text            the whole chapter, in place of GOOD and its edits
    only            the name of a check: the case lists only its findings
    general         true: the general words are GENERAL, as findings(general=GENERAL)
    general_add     the general words are GENERAL and these words
    general_remove  the general words are GENERAL without these words
    retired         the list of retired anchors
    tools           the files of tools/, by name, whose "# implements:" comments count
    tests           the files of tools/tests/, by name, whose "# verifies:" comments count
    findings        the findings, in order, as {check, anchor, at, occurrence}: at is
                    a text of the line, and occurrence counts the lines that hold it

Without a general key, the checks that need the general words do not run.
"""

import tomllib
from pathlib import Path

import pytest

from book import GENERAL, GOOD, findings, only

CASES = Path(__file__).resolve().parent / "cases"


def cases():
    for path in sorted(CASES.glob("*.toml")):
        for case in tomllib.loads(path.read_text())["case"]:
            yield pytest.param(case, id=f"{path.stem}: {case['name']}")


def chapter(case):
    """The text of the chapter of the case."""
    if "text" in case:
        return case["text"]
    text = GOOD
    for edit in case.get("replace", []):
        assert text.count(edit["old"]) == 1, edit["old"]
        text = text.replace(edit["old"], edit["new"])
    return text + case.get("append", "")


def general(case):
    """The general words of the case, or None."""
    if case.get("general"):
        return GENERAL
    if "general_add" in case:
        return GENERAL | set(case["general_add"])
    if "general_remove" in case:
        return GENERAL - set(case["general_remove"])
    return None


def expected(case, text):
    """(line, check, anchor) of each finding of the case."""
    lines = text.splitlines()
    result = []
    for finding in case["findings"]:
        holding = [number for number, content in enumerate(lines, 1) if finding["at"] in content]
        result.append((holding[finding.get("occurrence", 1) - 1], finding["check"], finding.get("anchor")))
    return result


@pytest.mark.parametrize("case", list(cases()))
def test_the_chapter_of_the_case_gives_its_findings(case):
    text = chapter(case)
    options = {"general": general(case), "retired": set(case["retired"]) if "retired" in case else None,
               "tools": case.get("tools"), "tests": case.get("tests")}
    found = only(case["only"], text, **options) if "only" in case else findings(text, **options)
    assert found == expected(case, text)
