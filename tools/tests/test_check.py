"""Tests of tools/check.py: one good case and at least one bad case per check."""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402

ENGLISH = "Rotation shall be fixed and unconditional."
STAMP = hashlib.sha256(("REQUIREMENT " + ENGLISH).encode()).hexdigest()[:8]

GOOD = f"""\
# Core

**REQUIREMENT.** Rotation shall be fixed
and unconditional.
{{rule=core.rotation parent=prop.x}}

``` {{.python .formal file=build/model/core_rotate.py stamp={STAMP}}}
def core_rotate(turn):
    return {{'next': turn + 1}}
```

**RATIONALE.** A thread's instructions are eight cycles apart.

**OPEN — the thread count is not settled.**

**DEFINITION.** A turn is a thread's cycle in the rotation.
{{rule=core.turn}}

**Thread.** An unlabelled bold paragraph is prose.

**GOAL.** Every rule has one meaning.
{{rule=doc.one-reading}}
"""


def findings(text, retired=()):
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "core.md"
        path.write_text(text)
        return [(f.line, f.check, f.anchor) for f in check.check([str(path)], set(retired))]


class GoodTest(unittest.TestCase):
    def test_a_correct_chapter_has_no_findings(self):
        self.assertEqual(findings(GOOD), [])


class LabelsTest(unittest.TestCase):
    def test_an_unknown_label_is_a_finding(self):
        text = GOOD.replace("**RATIONALE.**", "**REASON.**")
        self.assertEqual(findings(text), [(12, "labels", None)])

    def test_a_requirement_without_shall_is_a_finding(self):
        text = GOOD.replace("Rotation shall be fixed", "Rotation is fixed")
        self.assertIn((3, "labels", "core.rotation"), findings(text))

    def test_shall_inside_a_code_span_does_not_count(self):
        text = GOOD.replace("Rotation shall be fixed", "Rotation `shall` be fixed")
        self.assertIn((3, "labels", "core.rotation"), findings(text))


class OneShallTest(unittest.TestCase):
    def test_a_second_shall_is_a_finding_on_its_line(self):
        text = GOOD.replace("and unconditional.", "and shall be unconditional.")
        self.assertIn((4, "one-shall", "core.rotation"), findings(text))

    def test_two_shalls_in_two_chunks_are_not_a_finding(self):
        text = GOOD.replace("A turn is", "A turn shall be")
        self.assertNotIn("one-shall", [f[1] for f in findings(text)])


class AnchorsTest(unittest.TestCase):
    def test_a_rule_without_an_anchor_is_a_finding(self):
        text = GOOD.replace("{rule=core.turn}\n", "")
        self.assertEqual(findings(text), [(16, "anchors", None)])

    def test_an_anchor_outside_the_grammar_is_a_finding(self):
        text = GOOD.replace("rule=core.turn", "rule=Core_Turn")
        self.assertEqual(findings(text), [(16, "anchors", "Core_Turn")])

    def test_a_retired_anchor_is_a_finding(self):
        self.assertEqual(findings(GOOD, retired={"core.turn"}), [(16, "anchors", "core.turn")])

    def test_an_unknown_attribute_key_is_a_finding(self):
        text = GOOD.replace("{rule=core.turn}", "{rule=core.turn colour=red}")
        self.assertEqual(findings(text), [(16, "anchors", "core.turn")])

    def test_a_duplicate_anchor_in_another_document_is_a_finding(self):
        with tempfile.TemporaryDirectory() as name:
            first, second = Path(name) / "a.md", Path(name) / "b.md"
            first.write_text(GOOD)
            second.write_text("**DEFINITION.** A bank is a register set.\n{rule=core.turn}\n")
            result = check.check([str(first), str(second)], set())
        self.assertEqual([(f.path, f.line, f.check) for f in result], [(str(second), 1, "anchors")])
        self.assertIn(f"{first}:16", result[0].message)


class GoalTest(unittest.TestCase):
    def test_a_goal_needs_no_shall(self):
        self.assertNotIn((21, "labels", "doc.one-reading"), findings(GOOD))

    def test_a_goal_without_an_anchor_is_a_finding(self):
        text = GOOD.replace("{rule=doc.one-reading}\n", "")
        self.assertEqual(findings(text), [(21, "anchors", None)])

    def test_a_formal_block_after_a_goal_is_a_finding(self):
        text = GOOD + "\n``` {.python .formal}\nx\n```\n"
        self.assertEqual(findings(text), [(24, "stamps", "doc.one-reading")])


class StampsTest(unittest.TestCase):
    def test_a_stale_stamp_is_a_finding_that_gives_the_new_stamp(self):
        text = GOOD.replace("fixed\nand unconditional", "fixed\nand constant")
        result = [f for f in self._check(text) if f.check == "stamps"]
        new = hashlib.sha256(b"REQUIREMENT Rotation shall be fixed and constant.").hexdigest()[:8]
        self.assertEqual([(f.line, f.anchor) for f in result], [(7, "core.rotation")])
        self.assertIn(f"stamp={new}", result[0].fix)

    def test_a_missing_stamp_is_a_finding(self):
        text = GOOD.replace(f" stamp={STAMP}", "")
        self.assertEqual(findings(text), [(7, "stamps", "core.rotation")])

    def test_reflowed_english_and_changed_attributes_keep_the_stamp(self):
        text = GOOD.replace("fixed\nand", "fixed and").replace("parent=prop.x", "parent=prop.y")
        self.assertEqual(findings(text), [])

    def test_a_formal_block_after_a_non_rule_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.\n", "eight cycles apart.\n\n``` {.python .formal}\nx\n```\n")
        self.assertEqual(findings(text), [(14, "stamps", None)])

    def test_a_formal_block_outside_any_chunk_is_a_finding(self):
        text = GOOD + "\nSome prose.\n\n``` {.python .formal}\nx\n```\n"
        self.assertEqual(findings(text)[-1], (26, "stamps", None))

    def _check(self, text):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.md"
            path.write_text(text)
            return check.check([str(path)], set())


class CommandTest(unittest.TestCase):
    def run_in(self, text, retired=""):
        with tempfile.TemporaryDirectory() as name:
            book = Path(name) / "book" / "core"
            book.mkdir(parents=True)
            (book / "core.md").write_text(text)
            (Path(name) / "book" / "retired-anchors.txt").write_text(retired)
            return subprocess.run([sys.executable, str(ROOT / "tools" / "check.py")],
                                  cwd=name, capture_output=True, text=True)

    def test_a_clean_book_exits_0(self):
        result = self.run_in(GOOD)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "check: 1 documents, 0 findings\n")

    def test_a_finding_prints_location_check_anchor_and_fix_and_exits_1(self):
        result = self.run_in(GOOD, retired="# Retired anchors\ncore.turn\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines()[:2], [
            "book/core/core.md:16: [anchors] core.turn: the anchor is retired",
            "    fix: choose a new anchor",
        ])


if __name__ == "__main__":
    unittest.main()
