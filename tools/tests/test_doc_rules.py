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
        text = GOOD.replace("{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing,core.core}")
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


class DefinitionParentTest(unittest.TestCase):
    """doc.definition-parent"""

    def test_a_definition_with_two_parents_is_a_finding(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.core,design.timing}")
        self.assertEqual(findings(text), [(line(text, "{rule=core.turn"), "definition-parent", "core.turn")])

    def test_a_requirement_can_have_two_parents(self):
        text = GOOD.replace("{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing,core.core}")
        self.assertEqual(findings(text), [])


class CrowdedTest(unittest.TestCase):
    """The count of rules with more than two parents, which is not a finding."""

    def test_a_rule_with_three_parents_is_counted_but_passes(self):
        text = GOOD.replace("{rule=core.rotation parent=design.timing}",
                            "{rule=core.rotation parent=design.timing,core.core,core.turn}")
        result = run_book(text)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "check: 1 documents, 0 findings, 1 rules with more than 2 parents\n")

    def test_two_parents_are_not_counted(self):
        text = GOOD.replace("{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing,core.core}")
        self.assertIn(", 0 rules with more than 2 parents", run_book(text).stdout)


SENTENCE = "The core shall give the turn after\nthread *t* to thread *t* + 1."


def with_requirement(sentence):
    return GOOD.replace(SENTENCE, sentence)


def only(check_name, text):
    return [f for f in findings(text) if f[1] == check_name]


class EarsTest(unittest.TestCase):
    """doc.ears"""

    def test_every_clause_in_order_passes(self):
        for sentence in ["Where a trace exists, while the core runs, when a thread waits, the core shall wait.",
                         "While the core runs, the core shall give each turn in order.",
                         "If a thread faults, then the core shall not give it a turn.",
                         "Each core shall give `a, b` to thread *t*.",
                         "The Core shall give\nthe turn."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(only("ears", with_requirement(sentence)), [])

    def test_a_sentence_outside_the_pattern_is_a_finding(self):
        for sentence in ["When a thread waits the core shall wait.",
                         "When a thread waits, where a trace exists, the core shall wait.",
                         "If a thread faults, the core shall wait.",
                         "The core Shall wait.",
                         "The core shall give these turns:"]:
            with self.subTest(sentence=sentence):
                text = with_requirement(sentence)
                self.assertEqual(only("ears", text), [(line(text, "**REQUIREMENT.**"), "ears", "core.rotation")])

    def test_a_clause_without_its_comma_is_a_form_finding_not_an_actor_finding(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.md"
            path.write_text(with_requirement("When a thread waits the core shall wait."))
            messages = [f.message for f in check.check([str(path)], set()) if f.check == "ears"]
        self.assertEqual(messages, ["the sentence does not have the EARS form"])

    def test_the_finding_is_on_the_line_of_shall(self):
        text = with_requirement("When a thread\nwaits the core shall wait.")
        self.assertEqual(only("ears", text), [(line(text, "shall wait"), "ears", "core.rotation")])

    def test_an_actor_that_no_definition_defines_is_a_finding(self):
        for sentence in ["Rotation shall be fixed.", "The cores shall wait.", "A core turn shall wait."]:
            with self.subTest(sentence=sentence):
                text = with_requirement(sentence)
                self.assertEqual(only("ears", text), [(line(text, "**REQUIREMENT.**"), "ears", "core.rotation")])

    def test_only_the_first_bold_text_of_a_definition_defines_a_term(self):
        text = GOOD.replace("The **core** runs the threads in turn.", "The core runs the **threads** in turn.")
        self.assertEqual(only("ears", text), [(line(text, "**REQUIREMENT.**"), "ears", "core.rotation")])
        text = GOOD.replace("The **core** runs the threads in turn.", "The **core** runs the **threads**.")
        self.assertEqual(only("ears", text), [])

    def test_bold_text_inside_a_code_span_defines_nothing(self):
        text = GOOD.replace("The **core** runs the threads in turn.", "The `**core**` runs the threads in turn.")
        self.assertEqual(only("ears", text), [(line(text, "**REQUIREMENT.**"), "ears", "core.rotation")])


class LinterTest(unittest.TestCase):
    """doc.linter"""

    def test_a_semicolon_in_a_rule_is_a_finding_on_its_line(self):
        text = GOOD.replace("A **turn** is a thread's cycle in the rotation.",
                            "A **turn** is a thread's cycle; it is fixed.")
        self.assertEqual(findings(text), [(line(text, "cycle;"), "linter", "core.turn")])

    def test_a_long_sentence_in_a_rule_is_a_finding(self):
        text = GOOD.replace("The **core** runs the threads in turn.",
                            "The **core** runs the threads in turn" + " and waits" * 10 + ".")
        self.assertEqual(findings(text), [(line(text, "The **core** runs"), "linter", "core.core")])

    def test_an_advisory_finding_passes(self):
        text = GOOD.replace("The **core** runs the threads in turn.", "The **core** is built from threads.")
        self.assertEqual(findings(text), [])

    def test_a_chunk_that_is_not_a_rule_is_not_linted(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart; so it is.")
        self.assertEqual(findings(text), [])

    def test_a_semicolon_in_a_code_span_passes(self):
        text = GOOD.replace("in the rotation.", "in the rotation, `a; b`.")
        self.assertEqual(findings(text), [])


if __name__ == "__main__":
    unittest.main()
