"""Tests of the documentation rules that need the whole book, one class per rule.

Each test changes one thing in GOOD from test_check.py, and expects exactly the
findings of the rule that the change breaks.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from test_check import GOOD, ROOT, findings, line, run_book

sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402

REQUIREMENT = "**REQUIREMENT.**"


class ImplementedTest(unittest.TestCase):
    """doc.implemented"""

    def without_verilog(self):
        return GOOD.replace(" implements=core.rotation}", "}")

    def test_a_requirement_that_nothing_implements_is_a_finding(self):
        text = self.without_verilog()
        self.assertEqual(findings(text), [(line(text, REQUIREMENT), "implemented", "core.rotation")])

    def test_impl_none_is_an_exit(self):
        text = self.without_verilog().replace("parent=design.timing}", "parent=design.timing impl=none}", 1)
        self.assertEqual(findings(text), [])

    def test_a_tool_comment_implements_it(self):
        tool = {("tools/tool.py", 1, "core.rotation")}
        self.assertEqual(findings(self.without_verilog(), implemented=tool), [])

    def test_an_implements_list_can_name_several_anchors(self):
        text = GOOD.replace("implements=core.rotation}", "implements=core.core,core.rotation}")
        self.assertEqual(findings(text), [])

    def test_only_a_verilog_block_implements(self):
        text = GOOD.replace("{.verilog file=", "{.python file=")
        self.assertEqual(findings(text), [(line(text, REQUIREMENT), "implemented", "core.rotation")])

    def test_tool_implements_reads_whole_comment_lines_only(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "tool.py"
            path.write_text("# implements: doc.a\n    # implements: doc.b\nx = '# implements: doc.c'\n")
            self.assertEqual(check.tool_implements([path]), [(str(path), 1, "doc.a"), (str(path), 2, "doc.b")])

    def test_the_command_reads_the_comments_in_tools(self):
        result = run_book(self.without_verilog(), tool="# implements: core.rotation\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = run_book(self.without_verilog(), tool="")
        self.assertEqual(result.returncode, 1, result.stdout)


class ReferencesTest(unittest.TestCase):
    """doc.references"""

    def test_an_unknown_parent_is_a_finding_on_the_attribute_line(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.nothing}")
        self.assertEqual(findings(text), [(line(text, "parent=core.nothing"), "references", "core.turn")])

    def test_a_parent_list_can_name_several_anchors(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.core,design.timing}")
        self.assertEqual(findings(text), [])

    def test_an_empty_parent_entry_is_a_finding(self):
        text = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=design.timing,}")
        self.assertEqual(findings(text), [(line(text, "parent=design.timing,}"), "references", "core.core")])

    def test_an_implements_entry_that_names_no_anchor_is_a_finding(self):
        text = GOOD.replace("implements=core.rotation}", "implements=core.rotation,core.gone}")
        self.assertEqual(findings(text), [(line(text, "core.gone"), "references", None)])

    def test_a_tool_comment_that_names_no_anchor_is_a_finding(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.md"
            path.write_text(GOOD)
            result = check.check([str(path)], set(), [("tools/x.py", 3, "doc.gone")])
        self.assertEqual([(f.path, f.line, f.check) for f in result], [("tools/x.py", 3, "references")])

    def test_a_citation_must_name_an_anchor(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as `core.rotate` says.")
        self.assertEqual(findings(text), [(line(text, "core.rotate`"), "references", None)])

    def test_citations_in_headings_and_lists_count(self):
        text = GOOD.replace("## 2. Rotation", "## 2. Rotation, `core.nothing`") + "\n- `core.gone`\n"
        self.assertEqual(findings(text), [(line(text, "core.nothing"), "references", None),
                                          (line(text, "core.gone"), "references", None)])

    def test_good_citations_and_other_code_spans_pass(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as `core.rotation` and `check.py` say.")
        self.assertEqual(findings(text), [])

    def test_a_citation_of_a_retired_anchor_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, unlike `core.turn`.")
        self.assertIn((line(text, "unlike"), "references", None), findings(text, retired={"core.turn"}))

    def test_a_citation_inside_a_fenced_block_is_not_a_reference(self):
        self.assertEqual(findings(GOOD + "\n``` {file=build/x.v}\n`core.nothing`\n```\n"), [])


class ReachesGoalTest(unittest.TestCase):
    """doc.reaches-goal"""

    def test_a_rule_without_a_parent_is_a_finding(self):
        text = GOOD.replace("{rule=core.rotation parent=design.timing}", "{rule=core.rotation}")
        self.assertEqual(findings(text), [(line(text, "{rule=core.rotation}"), "reaches-goal", "core.rotation")])

    def test_a_cycle_is_a_finding_on_each_chunk_in_it(self):
        text = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=core.turn}")
        self.assertEqual(findings(text), [(line(text, "{rule=core.turn"), "reaches-goal", "core.turn"),
                                          (line(text, "{rule=core.core"), "reaches-goal", "core.core")])

    def test_the_message_names_the_fault(self):
        cycle = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=core.turn}")
        self.assertEqual(self.messages(cycle), ["the chunk reaches itself through its parents"] * 2)
        short = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core}")
        self.assertEqual(self.messages(short), ["the chunk reaches no GOAL through its parents",
                                                "the chunk has no parent"])

    def messages(self, text):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.md"
            path.write_text(text)
            return [f.message for f in check.check([str(path)], set()) if f.check == "reaches-goal"]

    def test_a_chain_that_stops_short_of_a_goal_is_a_finding(self):
        text = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=core.orphan}")
        text = text.replace("**Thread.**", "**DEFINITION.** An **orphan** has no parent.\n{rule=core.orphan}\n\n**Thread.**")
        self.assertEqual(findings(text), [(line(text, "{rule=core.turn"), "reaches-goal", "core.turn"),
                                          (line(text, "{rule=core.core"), "reaches-goal", "core.core"),
                                          (line(text, "{rule=core.orphan"), "reaches-goal", "core.orphan")])

    def test_an_anchored_rationale_needs_a_parent(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart.\n{rule=core.why}")
        self.assertEqual(findings(text), [(line(text, "{rule=core.why}"), "reaches-goal", "core.why")])

    def test_a_goal_can_serve_another_goal(self):
        text = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=design.sub}")
        text += "\n**GOAL.** Threads stay apart.\n{rule=design.sub parent=design.timing}\n"
        self.assertEqual(findings(text), [])

    def test_a_chain_that_meets_an_unknown_anchor_is_left_to_references(self):
        text = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=core.nothing}")
        self.assertEqual(findings(text), [(line(text, "{rule=core.core"), "references", "core.core")])


if __name__ == "__main__":
    unittest.main()
