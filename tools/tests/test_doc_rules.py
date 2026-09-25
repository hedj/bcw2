"""Tests of the documentation rules that need the whole book, one class per rule.

Each test changes one thing in GOOD from test_check.py, and expects exactly the
findings of the rule that the change breaks.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from test_check import GENERAL, GOOD, ROOT, findings, line, run_book

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

    def test_bold_text_outside_a_definition_defines_nothing(self):
        text = with_requirement("The zyx shall wait.").replace(
            "A thread's instructions are", "A **zyx** has instructions")
        self.assertEqual(only("ears", text), [(line(text, "**REQUIREMENT.**"), "ears", "core.rotation")])

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

    def test_a_semicolon_in_a_goal_is_a_finding_on_its_line(self):
        text = GOOD.replace("the timing of another thread.", "the timing of another thread; it is fixed.")
        self.assertEqual(findings(text), [(line(text, "thread; it"), "linter", "design.timing")])

    def test_a_chunk_that_is_not_a_rule_or_a_goal_is_not_linted(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart; so it is.")
        self.assertEqual(findings(text), [])

    def test_a_semicolon_in_a_code_span_passes(self):
        text = GOOD.replace("in the rotation.", "in the rotation, `a; b`.")
        self.assertEqual(findings(text), [])


class VocabularyTest(unittest.TestCase):
    """doc.vocabulary"""

    NEVER = GOOD.replace("{rule=core.core parent=design.timing}", "{rule=core.core parent=design.timing never=cpu,slot}")

    def test_a_definition_with_never_words_passes(self):
        self.assertEqual(findings(self.NEVER), [])

    def test_a_never_word_in_a_rule_is_a_finding_in_any_case(self):
        text = self.NEVER.replace("A **turn** is a thread's cycle", "A **turn** is a thread's CPU cycle")
        self.assertEqual(findings(text), [(line(text, "CPU cycle"), "vocabulary", "core.turn")])

    def test_a_never_word_in_a_goal_is_a_finding(self):
        text = self.NEVER.replace("the timing of another", "the CPU timing of another")
        self.assertEqual(findings(text), [(line(text, "CPU timing"), "vocabulary", "design.timing")])

    def test_only_whole_words_count(self):
        text = self.NEVER.replace("A **turn** is a thread's cycle", "A **turn** is a thread's slotted cycle")
        self.assertEqual(findings(text), [])

    def test_a_never_word_outside_a_rule_or_in_a_code_span_passes(self):
        text = self.NEVER.replace("eight cycles apart.", "eight cycles apart, not a slot.").replace(
            "in the rotation.", "in the rotation, not a `slot`.")
        self.assertEqual(findings(text), [])

    def test_never_on_a_chunk_that_is_not_a_definition_is_a_finding(self):
        text = GOOD.replace("{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing never=cpu}")
        self.assertEqual(findings(text), [(line(text, "never=cpu"), "never-on-definition", "core.rotation")])

    def test_never_on_a_goal_is_a_finding(self):
        text = GOOD.replace("{rule=design.timing}", "{rule=design.timing never=cpu}")
        self.assertEqual(findings(text), [(line(text, "never=cpu"), "never-on-definition", "design.timing")])


class OverviewFirstTest(unittest.TestCase):
    """doc.overview-first"""

    def test_a_chunk_in_the_overview_is_a_finding(self):
        text = GOOD.replace("The core runs every thread through one pipeline.",
                            "**RATIONALE.** The core runs every thread through one pipeline.")
        self.assertEqual(findings(text), [(line(text, "**RATIONALE.** The core runs"), "overview-first", None)])

    def test_a_chunk_before_the_first_heading_is_a_finding(self):
        text = GOOD.replace("# Core\n", "# Core\n\n**OPEN — the title is not settled.**\n")
        self.assertEqual(findings(text), [(line(text, "the title is not settled"), "overview-first", None)])

    def test_a_level_three_heading_does_not_end_the_overview(self):
        text = GOOD.replace("## 2. Rotation", "### 2. Rotation")
        expected = [(line(text, needle), "overview-first", anchor) for needle, anchor in [
            ("**REQUIREMENT.**", "core.rotation"), ("**RATIONALE.**", None), ("**OPEN", None),
            ("A **turn**", "core.turn"), ("The **core**", "core.core")]]
        self.assertEqual(findings(text), expected)

    def test_a_heading_inside_a_fenced_block_is_not_a_heading(self):
        text = GOOD.replace("The core runs every thread through one pipeline.",
                            "The core runs every thread.\n\n``` {file=build/x.md}\n## 9. Not\n```\n\n"
                            "**RATIONALE.** Still the overview.")
        self.assertEqual(findings(text), [(line(text, "Still the overview"), "overview-first", None)])


def words(count):
    return " ".join(["word"] * (count - 1)) + " end."


class ArgumentBudgetTest(unittest.TestCase):
    """doc.argument-budget"""

    THREAD = "**Thread.** An unlabelled bold paragraph is prose."

    def test_a_second_argument_block_in_a_section_with_a_rule_is_a_finding(self):
        text = GOOD.replace(self.THREAD, self.THREAD + "\n\n**DISCUSSION.** Another view.")
        self.assertEqual(findings(text), [(line(text, "Another view"), "argument-budget", None)])

    def test_an_argument_block_of_41_words_is_a_finding(self):
        text = GOOD.replace("A thread's instructions are eight cycles apart.", words(41))
        self.assertEqual(findings(text), [(line(text, "word word"), "argument-budget", None)])

    def test_an_argument_block_of_40_words_passes(self):
        self.assertEqual(findings(GOOD.replace("A thread's instructions are eight cycles apart.", words(40))), [])

    def test_a_level_three_heading_starts_a_new_section(self):
        text = GOOD.replace(self.THREAD, self.THREAD + "\n\n### 2.1 More\n\n**DISCUSSION.** Another view.")
        self.assertEqual(findings(text), [])

    def test_a_level_five_heading_does_not_start_a_section(self):
        text = GOOD.replace(self.THREAD, self.THREAD + "\n\n##### More\n\n**DISCUSSION.** Another view.")
        self.assertEqual(findings(text), [(line(text, "Another view"), "argument-budget", None)])

    def test_a_second_argument_block_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n**DISCUSSION.** One.\n\n**DISCUSSION.** Two.\n"
        self.assertEqual(findings(text), [(line(text, "Two."), "argument-budget", None)])

    def test_an_argument_block_of_41_words_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n**RATIONALE.** " + words(41) + "\n"
        self.assertEqual(findings(text), [(line(text, "word word"), "argument-budget", None)])

    def test_a_section_without_a_rule_or_a_goal_has_no_budget(self):
        text = GOOD + "\n## 4. Notes\n\n**DISCUSSION.** One.\n\n**DISCUSSION.** " + words(50) + "\n"
        self.assertEqual(findings(text), [])


class CodeKindsTest(unittest.TestCase):
    """doc.code-kinds"""

    def with_block(self, block):
        return GOOD.replace("**Thread.** An unlabelled bold paragraph is prose.",
                            "**Thread.** An unlabelled bold paragraph is prose.\n\n" + block)

    def test_a_block_without_file_or_class_is_a_finding(self):
        for block in ["```python\nx = 1\n```", "``` {.python}\nx = 1\n```", "    x = 1"]:
            with self.subTest(block=block):
                text = self.with_block(block + "\n")
                self.assertEqual(findings(text), [(line(text, "x = 1") - (0 if block.startswith("    ") else 1),
                                                   "code-kinds", None)])

    def test_a_block_inside_a_list_item_is_a_finding(self):
        text = self.with_block("- An item:\n\n  ```\n  x = 1\n  ```\n")
        self.assertEqual(findings(text), [(line(text, "x = 1") - 1, "code-kinds", None)])

    def test_a_check_block_passes(self):
        self.assertEqual(findings(self.with_block("``` {.check}\nx = 1\n```\n")), [])


class DottedWordsTest(unittest.TestCase):
    """doc.dotted-words"""

    def test_a_dotted_word_in_a_requirement_is_a_finding_on_its_line(self):
        for word in ["Q8.4", "9.09", "v1.2", "e.g.", "i.e.", "a.k.a.", "check.py",
                     "etc.", "Etc.", "vs.", "cf.", "approx.", "incl.", "esp.", "resp.", "ca.", "Ca."]:
            with self.subTest(word=word):
                text = with_requirement(f"The core shall give\nthe turn, {word} to each thread.")
                self.assertEqual(only("dotted-words", text),
                                 [(line(text, word), "dotted-words", "core.rotation")])

    def test_a_quoted_dotted_word_passes(self):
        for word in ["`Q8.4`", "`9.09`", "`e.g.`", "`etc.`"]:
            with self.subTest(word=word):
                text = with_requirement(f"The core shall give the turn, {word} to each thread.")
                self.assertEqual(only("dotted-words", text), [])

    def test_a_full_stop_that_ends_a_sentence_passes(self):
        for sentence in ["The core shall give the turn to thread *t* + 1.",
                         "The core shall give the turn to each thread, the next one etch.",
                         "The core shall give the turn to the TVs.",
                         "The core shall give the turn to Africa."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(only("dotted-words", with_requirement(sentence)), [])

    def test_a_dotted_word_outside_a_requirement_passes(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, in Q8.4, e.g. thread 1.")
        self.assertEqual(only("dotted-words", text), [])

class AttributeKeysTest(unittest.TestCase):
    """doc.attribute-keys"""

    def test_an_unknown_key_is_a_finding_on_the_attribute_line(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.core colour=red}")
        self.assertEqual(findings(text), [(line(text, "colour=red"), "attribute-keys", "core.turn")])

    def test_each_unknown_key_is_a_finding(self):
        text = GOOD.replace("{rule=design.timing}", "{rule=design.timing parnet=core.core size=2}")
        self.assertEqual(findings(text), [(line(text, "parnet="), "attribute-keys", "design.timing")] * 2)

    def test_the_four_keys_pass(self):
        text = GOOD.replace("{rule=core.turn parent=core.core}", "{rule=core.turn parent=core.core never=slot}").replace(
            "{rule=core.rotation parent=design.timing}", "{rule=core.rotation parent=design.timing impl=none}")
        self.assertEqual(findings(text), [])


class KnownWordsTest(unittest.TestCase):
    """doc.general-word, doc.known-word and doc.known-words"""

    SLOT = GOOD + "\n**DEFINITION.** A **time slot** is a turn of the core.\n{rule=core.slot parent=core.core}\n"

    def known(self, text, general=GENERAL):
        return [f for f in findings(text, general=general) if f[1] == "known-words"]

    def test_a_chapter_of_general_words_and_defined_terms_passes(self):
        self.assertEqual(findings(GOOD, general=GENERAL), [])

    def test_an_unknown_word_in_a_goal_or_a_rule_is_a_finding_on_its_line(self):
        for word, needle, anchor in [("timing", "the timing of", "design.timing"),
                                     ("give", "shall give", "core.rotation"),
                                     ("cycle", "A **turn**", "core.turn"),
                                     ("runs", "The **core**", "core.core")]:
            with self.subTest(word=word):
                self.assertEqual(self.known(GOOD, GENERAL - {word}),
                                 [(line(GOOD, needle), "known-words", anchor)])

    def test_each_unknown_word_is_a_finding(self):
        text = GOOD.replace("the timing of", "the zyx timing wvu of")
        self.assertEqual(self.known(text), [(line(text, "zyx"), "known-words", "design.timing")] * 2)

    def test_the_finding_is_on_the_line_of_the_word(self):
        self.assertEqual(self.known(GOOD, GENERAL - {"t"}),
                         [(line(GOOD, "thread *t* to"), "known-words", "core.rotation")] * 2)

    def test_a_word_outside_a_goal_or_a_rule_passes(self):
        for old, new in [("eight cycles apart.", "eight zyx cycles apart."),
                         ("the thread count is", "the zyx thread count is"),
                         ("is prose.", "is zyx prose."),
                         ("## 2. Rotation", "## 2. Zyx")]:
            with self.subTest(new=new):
                self.assertEqual(self.known(GOOD.replace(old, new)), [])

    def test_a_word_in_a_quotation_passes(self):
        text = GOOD.replace("the timing of", "the `zyx` timing of")
        self.assertEqual(self.known(text), [])

    def test_case_does_not_matter(self):
        text = GOOD.replace("the timing of", "the TIMING of")
        self.assertEqual(self.known(text), [])

    def test_a_defined_term_needs_no_listing(self):
        self.assertEqual(self.known(GOOD, GENERAL | {"turn", "core"}), [])
        self.assertEqual(self.known(GOOD.replace("the timing of", "the core of")), [])

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        text = GOOD.replace("A **turn** is", "A **Turn** is")
        self.assertEqual(self.known(text), [])

    def test_the_endings_s_es_and_apostrophe_s_keep_a_word_known(self):
        text = GOOD.replace("the timing of", "the timings, core's, turns, toes of")
        self.assertEqual(self.known(text), [])

    def test_other_endings_do_not(self):
        for word in ["timingly", "cored", "turner", "thready"]:
            with self.subTest(word=word):
                text = GOOD.replace("the timing of", f"the {word} of")
                self.assertEqual(self.known(text), [(line(text, word), "known-words", "design.timing")])

    def test_a_word_of_a_defined_term_is_known_only_inside_the_whole_term(self):
        for sentence, unknown in [("The core shall give the time slot to thread `t`.", []),
                                  ("The core shall give the time slots to thread `t`.", []),
                                  ("The core shall give the time\nslot to thread `t`.", []),
                                  ("The core shall give the slot to thread `t`.", ["slot"]),
                                  ("The core shall give the time to thread `t`.", ["time"]),
                                  ("The core shall give the times slot to thread `t`.", ["times", "slot"])]:
            with self.subTest(sentence=sentence):
                text = self.SLOT.replace(SENTENCE, sentence)
                self.assertEqual(self.known(text), [(line(text, "**REQUIREMENT.**"), "known-words", "core.rotation")]
                                 * len(unknown))

    def test_the_longest_defined_term_wins(self):
        text = self.SLOT + "\n**DEFINITION.** A **time** is a zyx.\n{rule=core.time parent=core.core}\n"
        self.assertEqual(self.known(text, GENERAL | {"zyx"}), [])
        text = text.replace(SENTENCE, "The core shall give the time slot of the time to thread `t`.")
        self.assertEqual(self.known(text, GENERAL | {"zyx"}), [])


class GeneralWordsTest(unittest.TestCase):
    """doc.general-words"""

    SLOT = KnownWordsTest.SLOT

    def general(self, text, extra):
        return [f for f in findings(text, general=GENERAL | extra) if f[1] == "general-words"]

    def test_a_listed_defined_term_is_a_finding_on_its_definition(self):
        for word in ["turn", "turns", "turn's", "turnes"]:
            with self.subTest(word=word):
                self.assertEqual(self.general(GOOD, {word}), [(line(GOOD, "A **turn**"), "general-words", "core.turn")])

    def test_each_listed_form_is_a_finding(self):
        self.assertEqual(self.general(GOOD, {"turn", "turns"}),
                         [(line(GOOD, "A **turn**"), "general-words", "core.turn")] * 2)

    def test_a_listed_multi_word_term_is_a_finding(self):
        for word in ["time slot", "time slots"]:
            with self.subTest(word=word):
                self.assertEqual(self.general(self.SLOT, {word}),
                                 [(line(self.SLOT, "A **time slot**"), "general-words", "core.slot")])

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        text = GOOD.replace("A **turn** is", "A **Turn** is")
        self.assertEqual(self.general(text, {"turn"}), [(line(text, "A **Turn**"), "general-words", "core.turn")])

    def test_one_word_of_a_multi_word_term_passes(self):
        self.assertEqual(self.general(self.SLOT, {"time", "slot"}), [])

    def test_a_word_that_only_starts_like_a_defined_term_passes(self):
        self.assertEqual(self.general(GOOD, {"turner", "cored", "turnstile"}), [])


if __name__ == "__main__":
    unittest.main()
