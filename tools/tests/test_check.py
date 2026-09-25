"""Tests of tools/check.py: one good case and at least one bad case per check.

GOOD is a small chapter that obeys every documentation rule. A test changes
one thing in it and expects the findings of the rule that the change breaks.
The helper line() finds a line number by its text, so that the tests do not
depend on the layout of GOOD.
"""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402

ENGLISH = "The core shall give the turn after thread *t* to thread *t* + 1."
STAMP = hashlib.sha256(("REQUIREMENT " + ENGLISH).encode()).hexdigest()[:8]

GOOD = f"""\
# Core

## 1. Overview

The core runs every thread through one pipeline.

## 2. Rotation

**REQUIREMENT.** The core shall give the turn after
thread *t* to thread *t* + 1.
{{rule=core.rotation parent=design.timing}}

``` {{.python .formal file=build/model/core_rotate.py stamp={STAMP}}}
def core_rotate(turn):
    return {{'next': turn + 1}}
```

``` {{.verilog file=build/rtl/core/core_rotate.v implements=core.rotation}}
module core_rotate (input wire [2:0] turn, output wire [2:0] next);
    assign next = turn + 3'd1;
endmodule
```

**RATIONALE.** A thread's instructions are eight cycles apart.

**OPEN — the thread count is not settled.**

**DEFINITION.** A **turn** is a thread's cycle in the rotation.
{{rule=core.turn parent=core.core}}

**DEFINITION.** The **core** runs the threads in turn.
{{rule=core.core parent=design.timing}}

**Thread.** An unlabelled bold paragraph is prose.

## 3. Goals

**GOAL.** No thread can change the timing of another thread.
{{rule=design.timing}}
"""


def line(text, needle):
    """The 1-based number of the first line of text that holds needle."""
    return next(number for number, content in enumerate(text.splitlines(), 1)
                if needle in content)


def findings(text, retired=(), implemented=()):
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "core.md"
        path.write_text(text)
        return [(f.line, f.check, f.anchor)
                for f in check.check([str(path)], set(retired), set(implemented))]


class GoodTest(unittest.TestCase):
    def test_a_correct_chapter_has_no_findings(self):
        self.assertEqual(findings(GOOD), [])


class LabelsTest(unittest.TestCase):
    def test_an_unknown_label_is_a_finding(self):
        text = GOOD.replace("**RATIONALE.**", "**REASON.**")
        self.assertEqual(findings(text), [(line(text, "**REASON.**"), "labels", None)])

    def test_a_requirement_without_shall_is_a_finding(self):
        text = GOOD.replace("The core shall give", "The core gives")
        self.assertIn((line(text, "**REQUIREMENT.**"), "labels", "core.rotation"), findings(text))

    def test_shall_inside_a_code_span_does_not_count(self):
        text = GOOD.replace("The core shall give", "The core `shall` give")
        self.assertIn((line(text, "**REQUIREMENT.**"), "labels", "core.rotation"), findings(text))


class OneShallTest(unittest.TestCase):
    def test_a_second_shall_is_a_finding_on_its_line(self):
        text = GOOD.replace("*t* + 1.", "*t* + 1 and shall not stall.")
        self.assertIn((line(text, "shall not stall"), "one-shall", "core.rotation"), findings(text))

    def test_two_shalls_in_two_chunks_are_not_a_finding(self):
        text = GOOD.replace("A **turn** is", "A **turn** shall be")
        self.assertNotIn("one-shall", [f[1] for f in findings(text)])


class AnchorsTest(unittest.TestCase):
    def test_a_rule_without_an_anchor_is_a_finding(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}\n", "")
        self.assertEqual(findings(text), [(line(text, "A **turn**"), "anchors", None)])

    def test_an_anchor_outside_the_grammar_is_a_finding(self):
        text = GOOD.replace("rule=core.turn", "rule=Core_Turn")
        self.assertEqual(findings(text), [(line(text, "A **turn**"), "anchors", "Core_Turn")])

    def test_a_retired_anchor_is_a_finding(self):
        self.assertEqual(findings(GOOD, retired={"core.turn"}),
                         [(line(GOOD, "A **turn**"), "anchors", "core.turn")])

    def test_an_unknown_attribute_key_is_a_finding(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.core colour=red}")
        self.assertEqual(findings(text), [(line(text, "A **turn**"), "anchors", "core.turn")])

    def test_a_duplicate_anchor_in_another_document_is_a_finding(self):
        other = ("# Bank\n\n## 1. Overview\n\nText.\n\n## 2. Banks\n\n"
                 "**DEFINITION.** A **bank** is a register set.\n{rule=core.turn parent=core.core}\n")
        with tempfile.TemporaryDirectory() as name:
            first, second = Path(name) / "a.md", Path(name) / "b.md"
            first.write_text(GOOD)
            second.write_text(other)
            result = check.check([str(first), str(second)], set())
        self.assertEqual([(f.path, f.line, f.check) for f in result],
                         [(str(second), line(other, "A **bank**"), "anchors")])
        self.assertIn(f"{first}:{line(GOOD, 'A **turn**')}", result[0].message)


class GoalTest(unittest.TestCase):
    def test_a_goal_needs_no_shall(self):
        self.assertEqual(findings(GOOD), [])

    def test_a_goal_without_an_anchor_is_a_finding(self):
        text = GOOD + "\n**GOAL.** Another goal.\n"
        self.assertEqual(findings(text), [(line(text, "Another goal"), "anchors", None)])

    def test_a_formal_block_after_a_goal_is_a_finding(self):
        text = GOOD + "\n``` {.python .formal}\nx\n```\n"
        self.assertEqual(findings(text), [(line(text, "{.python .formal}"), "stamps", "design.timing")])


class StampsTest(unittest.TestCase):
    def test_a_stale_stamp_is_a_finding_that_gives_the_new_stamp(self):
        text = GOOD.replace("thread *t* + 1.", "thread *t* + 2.")
        result = [f for f in self._check(text) if f.check == "stamps"]
        new = hashlib.sha256(("REQUIREMENT " + ENGLISH.replace("+ 1.", "+ 2.")).encode()).hexdigest()[:8]
        self.assertEqual([(f.line, f.anchor) for f in result],
                         [(line(text, "stamp="), "core.rotation")])
        self.assertIn(f"stamp={new}", result[0].fix)

    def test_a_missing_stamp_is_a_finding(self):
        text = GOOD.replace(f" stamp={STAMP}", "")
        self.assertEqual(findings(text), [(line(text, ".formal"), "stamps", "core.rotation")])

    def test_reflowed_english_and_changed_attributes_keep_the_stamp(self):
        text = GOOD.replace("after\nthread", "after thread").replace(
            "{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing,core.core}")
        self.assertEqual(findings(text), [])

    def test_a_formal_block_after_a_non_rule_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.\n", "eight cycles apart.\n\n``` {.python .formal}\nx\n```\n")
        self.assertEqual(findings(text), [(line(text, "{.python .formal}"), "stamps", None)])

    def test_a_formal_block_outside_any_chunk_is_a_finding(self):
        text = GOOD + "\nSome prose.\n\n``` {.python .formal}\nx\n```\n"
        self.assertEqual(findings(text), [(line(text, "{.python .formal}"), "stamps", None)])

    def _check(self, text):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.md"
            path.write_text(text)
            return check.check([str(path)], set())


def run_book(text, retired="", tool=None):
    """Run tools/check.py on a book of one chapter, with an optional tools/tool.py."""
    with tempfile.TemporaryDirectory() as name:
        book = Path(name) / "book" / "core"
        book.mkdir(parents=True)
        (book / "core.md").write_text(text)
        (Path(name) / "book" / "retired-anchors.txt").write_text(retired)
        if tool is not None:
            (Path(name) / "tools").mkdir()
            (Path(name) / "tools" / "tool.py").write_text(tool)
        return subprocess.run([sys.executable, str(ROOT / "tools" / "check.py")],
                              cwd=name, capture_output=True, text=True)


class CommandTest(unittest.TestCase):
    def test_a_clean_book_exits_0(self):
        result = run_book(GOOD)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "check: 1 documents, 0 findings, 0 rules with more than 2 parents\n")

    def test_a_finding_prints_location_check_anchor_and_fix_and_exits_1(self):
        result = run_book(GOOD, retired="# Retired anchors\ncore.turn\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines()[:2], [
            f"book/core/core.md:{line(GOOD, 'A **turn**')}: [anchors] core.turn: the anchor is retired",
            "    fix: choose a new anchor",
        ])


if __name__ == "__main__":
    unittest.main()
