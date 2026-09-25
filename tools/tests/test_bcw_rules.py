"""Tests of the documentation rules of tools/bcw.py that need the whole book, one class per rule.

Each test changes one thing in GOOD from test_bcw.py, and expects exactly the
findings of the rule that the change breaks.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from docutils import nodes

from test_bcw import GENERAL, GOOD, Book, bcw, findings, line, only

import linemap  # noqa: E402

ROTATION = ".. requirement:: core.rotation\n   :parent: core.timing\n"
IMPLEMENTS = "   :implements: core.rotation\n"
TURN = ".. definition:: core.turn\n   :parent: core.core\n"
CORE = ".. definition:: core.core\n   :parent: core.timing\n"
SENTENCE = "The core shall give the turn after\n   thread *t* to thread *t* + 1."
THREAD = "**Thread.** An unlabelled bold paragraph is prose."


def with_requirement(sentence):
    return GOOD.replace(SENTENCE, sentence)


def words(count):
    return " ".join(["word"] * (count - 1)) + " end."


class ImplementedTest(unittest.TestCase):
    """doc.implemented"""

    UNUSED = GOOD.replace(IMPLEMENTS, "")

    def test_a_requirement_that_nothing_implements_is_a_finding(self):
        self.assertEqual(findings(self.UNUSED), [(line(GOOD, ".. requirement::"), "implemented", "core.rotation")])

    def test_impl_none_is_an_exit(self):
        text = self.UNUSED.replace(ROTATION, ROTATION + "   :impl: none\n")
        self.assertEqual(findings(text), [])

    def test_a_tool_comment_implements_it(self):
        self.assertEqual(findings(self.UNUSED, tools={"tool.py": "# implements: core.rotation\n"}), [])

    def test_an_implements_list_can_name_several_anchors(self):
        text = GOOD.replace(IMPLEMENTS, "   :implements: core.core, core.rotation\n")
        self.assertEqual(findings(text), [])

    def test_a_citation_does_not_implement(self):
        text = self.UNUSED.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotation` says.")
        self.assertEqual(findings(text), [(line(text, ".. requirement::"), "implemented", "core.rotation")])

    def test_tool_implements_reads_whole_comment_lines_only(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "tool.py"
            path.write_text("# implements: doc.a\n    # implements: doc.b\nx = '# implements: doc.c'\n")
            self.assertEqual(bcw.tool_implements([path]), [(str(path), 1, "doc.a"), (str(path), 2, "doc.b")])


class ReferencesTest(unittest.TestCase):
    """doc.references"""

    def test_an_unknown_parent_is_a_finding_on_the_option_line(self):
        text = GOOD.replace(TURN, TURN.replace("core.core", "core.nothing"))
        self.assertEqual(findings(text), [(line(text, ":parent: core.nothing"), "references", "core.turn")])

    def test_a_parent_list_can_name_several_anchors(self):
        text = GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))
        self.assertEqual(findings(text), [])

    def test_an_empty_parent_entry_is_a_finding(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.timing,"))
        self.assertEqual(findings(text), [(line(text, ":parent: core.timing,"), "references", "core.core")])

    def test_an_implements_entry_that_names_no_anchor_is_a_finding(self):
        text = GOOD.replace(IMPLEMENTS, "   :implements: core.rotation, core.gone\n")
        self.assertEqual(findings(text), [(line(text, ".. source::"), "references", None)])

    def test_a_tool_comment_that_names_no_anchor_is_a_finding(self):
        book = Book({"core/core.rst": GOOD}, tools={"x.py": "\n\n# implements: doc.gone\n"})
        self.assertEqual(book.tuples(), [("tools/x.py", 3, "references", None)])

    def test_a_citation_must_name_an_anchor(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotate` says.")
        self.assertEqual(findings(text), [(line(text, "core.rotate`"), "references", None)])

    def test_citations_in_headings_and_lists_count(self):
        text = GOOD.replace("Rotation\n========", "Rotation :rule:`core.nothing`\n=============================")
        text += "\n- :rule:`core.gone`\n"
        self.assertEqual(findings(text), [(line(text, "core.nothing"), "references", None),
                                          (line(text, "core.gone"), "references", None)])

    def test_good_citations_and_other_quotations_pass(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotation` and ``check.py`` say.")
        self.assertEqual(findings(text), [])

    def test_a_citation_of_a_retired_anchor_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, unlike :rule:`core.turn`.")
        self.assertIn((line(text, "unlike"), "references", None), findings(text, retired={"core.turn"}))

    def test_a_citation_inside_a_code_block_is_not_a_reference(self):
        self.assertEqual(findings(GOOD + "\n.. check::\n\n   :rule:`core.nothing`\n"), [])


class ReachesGoalTest(unittest.TestCase):
    """doc.reaches-goal"""

    CYCLE = GOOD.replace(CORE, CORE.replace("core.timing", "core.turn"))

    def test_a_rule_without_a_parent_is_a_finding_on_its_directive(self):
        text = GOOD.replace(ROTATION, ".. requirement:: core.rotation\n")
        self.assertEqual(findings(text), [(line(text, ".. requirement::"), "reaches-goal", "core.rotation")])

    def test_a_cycle_is_a_finding_on_the_parent_line_of_each_chunk_in_it(self):
        self.assertEqual(findings(self.CYCLE), [(line(self.CYCLE, ":parent: core.core"), "reaches-goal", "core.turn"),
                                                (line(self.CYCLE, ":parent: core.turn"), "reaches-goal", "core.core")])

    def test_the_message_names_the_fault(self):
        self.assertEqual(self.messages(self.CYCLE), ["the chunk reaches itself through its parents"] * 2)
        short = GOOD.replace(CORE, ".. definition:: core.core\n")
        self.assertEqual(self.messages(short), ["the chunk reaches no GOAL through its parents",
                                                "the chunk has no parent"])

    def messages(self, text):
        return [f.message for f in Book({"core/core.rst": text}).findings if f.check == "reaches-goal"]

    def test_a_chain_that_stops_short_of_a_goal_is_a_finding(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.orphan")).replace(
            THREAD, ".. definition:: core.orphan\n\n   An :dfn:`orphan` has no parent.\n\n" + THREAD)
        self.assertEqual(findings(text), [(line(text, ":parent: core.core"), "reaches-goal", "core.turn"),
                                          (line(text, ":parent: core.orphan"), "reaches-goal", "core.core"),
                                          (line(text, ".. definition:: core.orphan"), "reaches-goal", "core.orphan")])

    def test_a_rationale_takes_no_anchor(self):
        text = GOOD.replace(".. rationale::", ".. rationale:: core.why")
        book = Book({"core/core.rst": text})
        self.assertIn("the rationale directive takes no argument.", book.warnings)
        self.assertNotIn("core.why", [chunk.anchor for chunk in book.documents[0].chunks])

    def test_a_goal_can_serve_another_goal(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.sub"))
        text += "\n.. goal:: core.sub\n   :parent: core.timing\n\n   Threads stay apart.\n"
        self.assertEqual(findings(text), [])

    def test_the_parents_are_the_entries_of_the_list_without_spaces(self):
        chunk = bcw.Chunk("book/core/core.rst", "core", 1, "REQUIREMENT", "core.x", {"parent": "core.a, core.b,"}, {}, [])
        self.assertEqual(bcw.parents(chunk), ["core.a", "core.b"])

    def test_a_chain_that_meets_an_unknown_anchor_is_left_to_references(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.nothing"))
        self.assertEqual(findings(text), [(line(text, ":parent: core.nothing"), "references", "core.core")])


class DefinitionParentTest(unittest.TestCase):
    """doc.definition-parent"""

    def test_a_definition_with_two_parents_is_a_finding_on_the_option_line(self):
        text = GOOD.replace(TURN, TURN.replace("core.core", "core.core, core.timing"))
        self.assertEqual(findings(text), [(line(text, ":parent: core.core, core.timing"), "definition-parent",
                                           "core.turn")])

    def test_a_requirement_can_have_two_parents(self):
        text = GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))
        self.assertEqual(findings(text), [])


class CrowdedTest(unittest.TestCase):
    """The count of rules with more than two parents, which is not a finding."""

    def test_a_rule_with_three_parents_is_counted_but_passes(self):
        book = Book({"core/core.rst": GOOD.replace(ROTATION, ROTATION.replace(
            "core.timing", "core.timing, core.core, core.turn"))})
        self.assertEqual((book.findings, bcw.crowded(book.documents)), ([], 1))

    def test_two_parents_are_not_counted(self):
        book = Book({"core/core.rst": GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))})
        self.assertEqual(bcw.crowded(book.documents), 0)


class EarsTest(unittest.TestCase):
    """doc.ears"""

    def test_every_clause_in_order_passes(self):
        for sentence in ["Where a trace exists, while the core runs, when a thread waits, the core shall wait.",
                         "While the core runs, the core shall give each turn in order.",
                         "If a thread faults, then the core shall not give it a turn.",
                         "Each core shall give ``a, b`` to thread *t*.",
                         "The Core shall give\n   the turn."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(only("ears", with_requirement(sentence)), [])

    def test_a_sentence_outside_the_pattern_is_a_finding_on_the_line_of_shall(self):
        for sentence in ["When a thread waits the core shall wait.",
                         "When a thread waits, where a trace exists, the core shall wait.",
                         "If a thread faults, the core shall wait.",
                         "The core Shall wait.",
                         "The core shall give these turns:"]:
            with self.subTest(sentence=sentence):
                text = with_requirement(sentence)
                self.assertEqual(only("ears", text), [(line(text, sentence), "ears", "core.rotation")])

    def test_a_clause_without_its_comma_is_a_form_finding_not_an_actor_finding(self):
        book = Book({"core/core.rst": with_requirement("When a thread waits the core shall wait.")})
        self.assertEqual([f.message for f in book.findings if f.check == "ears"],
                         ["the sentence does not have the EARS form"])

    def test_the_finding_is_on_the_line_of_shall(self):
        text = with_requirement("When a thread\n   waits the core shall wait.")
        self.assertEqual(only("ears", text), [(line(text, "shall wait"), "ears", "core.rotation")])

    def test_an_actor_that_no_definition_defines_is_a_finding(self):
        for sentence in ["Rotation shall be fixed.", "The cores shall wait.", "A core turn shall wait."]:
            with self.subTest(sentence=sentence):
                text = with_requirement(sentence)
                self.assertEqual(only("ears", text), [(line(text, sentence), "ears", "core.rotation")])

    def test_only_the_first_dfn_of_a_definition_defines_a_term(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The core runs the :dfn:`threads` in turn.")
        self.assertEqual(only("ears", text), [(line(text, "The core shall"), "ears", "core.rotation")])
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The :dfn:`core` runs the :dfn:`threads`.")
        self.assertEqual(only("ears", text), [])

    def test_a_dfn_outside_a_definition_defines_nothing(self):
        text = with_requirement("The zyx shall wait.").replace(
            "A thread's instructions are", "A :dfn:`zyx` has instructions")
        self.assertEqual(only("ears", text), [(line(text, "The zyx shall"), "ears", "core.rotation")])

    def test_a_definition_without_a_dfn_defines_nothing(self):
        text = GOOD.replace("The :dfn:`core` runs", "The ``core`` runs")
        self.assertEqual(only("ears", text), [(line(text, "The core shall"), "ears", "core.rotation")])


class LinterTest(unittest.TestCase):
    """doc.linter"""

    def test_a_semicolon_in_a_rule_is_a_finding_on_its_line(self):
        text = GOOD.replace("A :dfn:`turn` is a thread's cycle in the rotation.",
                            "A :dfn:`turn` is a thread's cycle; it is fixed.")
        self.assertEqual(findings(text), [(line(text, "cycle;"), "linter", "core.turn")])

    def test_a_long_sentence_in_a_rule_is_a_finding(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.",
                            "The :dfn:`core` runs the threads in turn" + " and waits" * 10 + ".")
        self.assertEqual(findings(text), [(line(text, "The :dfn:`core` runs"), "linter", "core.core")])

    def test_an_advisory_finding_passes(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The :dfn:`core` is built from threads.")
        self.assertEqual(findings(text), [])

    def test_a_semicolon_in_a_goal_is_a_finding_on_its_line(self):
        text = GOOD.replace("the timing of another thread.", "the timing of another thread; it is fixed.")
        self.assertEqual(findings(text), [(line(text, "thread; it"), "linter", "core.timing")])

    def test_a_chunk_that_is_not_a_rule_or_a_goal_is_not_linted(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart; so it is.")
        self.assertEqual(findings(text), [])

    def test_a_semicolon_in_a_quotation_passes(self):
        text = GOOD.replace("in the rotation.", "in the rotation, ``a; b``.")
        self.assertEqual(findings(text), [])


class VocabularyTest(unittest.TestCase):
    """doc.vocabulary and doc.never-on-definition"""

    NEVER = GOOD.replace(CORE, CORE + "   :never: cpu, slot\n")

    def test_a_definition_with_never_words_passes(self):
        self.assertEqual(findings(self.NEVER), [])

    def test_a_never_word_in_a_rule_is_a_finding_in_any_case(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's CPU cycle")
        self.assertEqual(findings(text), [(line(text, "CPU cycle"), "vocabulary", "core.turn")])

    def test_a_never_word_in_a_goal_is_a_finding(self):
        text = self.NEVER.replace("the timing of another", "the CPU timing of another")
        self.assertEqual(findings(text), [(line(text, "CPU timing"), "vocabulary", "core.timing")])

    def test_each_entry_of_the_never_list_counts_at_the_start_of_a_line_too(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's\n   slot cycle")
        self.assertEqual(findings(text), [(line(text, "slot cycle"), "vocabulary", "core.turn")])

    def test_only_whole_words_count(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's slotted cycle")
        self.assertEqual(findings(text), [])

    def test_a_never_word_outside_a_rule_or_in_a_quotation_passes(self):
        text = self.NEVER.replace("eight cycles apart.", "eight cycles apart, not a slot.").replace(
            "in the rotation.", "in the rotation, not a ``slot``.")
        self.assertEqual(findings(text), [])

    def test_never_on_a_chunk_that_is_not_a_definition_is_an_error(self):
        for old, new in [(ROTATION, ROTATION + "   :never: cpu\n"),
                         (".. goal:: core.timing\n", ".. goal:: core.timing\n   :never: cpu\n")]:
            with self.subTest(new=new):
                text = GOOD.replace(old, new)
                book = Book({"core/core.rst": text})
                # The chunk is lost, so the references to its anchor fail too.
                self.assertEqual([f for f in book.tuples() if f[2] == "sphinx"],
                                 [("book/core/core.rst", line(text, new.splitlines()[0]), "sphinx", None)])
                self.assertIn('unknown option: "never"', book.warnings)


class OverviewFirstTest(unittest.TestCase):
    """doc.overview-first"""

    def test_a_chunk_in_the_overview_is_a_finding(self):
        text = GOOD.replace("The core runs every thread through one pipeline.",
                            ".. rationale::\n\n   The core runs every thread through one pipeline.")
        self.assertEqual(findings(text), [(line(text, ".. rationale::"), "overview-first", None)])

    def test_a_chunk_before_the_first_section_is_a_finding(self):
        text = GOOD.replace("====\nCore\n====\n", "====\nCore\n====\n\n.. open:: The title is not settled.\n")
        self.assertEqual(findings(text), [(line(text, "The title is not settled"), "overview-first", None)])

    def test_a_third_level_section_does_not_end_the_overview(self):
        text = GOOD.replace("Rotation\n========", "Rotation\n--------")
        expected = [(line(text, needle), "overview-first", anchor) for needle, anchor in [
            (".. requirement::", "core.rotation"), (".. rationale::", None), (".. open::", None),
            (".. definition:: core.turn", "core.turn"), (".. definition:: core.core", "core.core")]]
        self.assertEqual(findings(text), expected)


class ArgumentBudgetTest(unittest.TestCase):
    """doc.argument-budget"""

    def test_a_second_argument_in_a_section_with_a_rule_is_a_finding(self):
        text = GOOD.replace(THREAD, THREAD + "\n\n.. discussion::\n\n   Another view.")
        self.assertEqual(findings(text), [(line(text, ".. discussion::"), "argument-budget", None)])

    def test_an_argument_of_41_words_is_a_finding(self):
        text = GOOD.replace("A thread's instructions are eight cycles apart.", words(41))
        self.assertEqual(findings(text), [(line(text, ".. rationale::"), "argument-budget", None)])

    def test_an_argument_of_40_words_passes(self):
        self.assertEqual(findings(GOOD.replace("A thread's instructions are eight cycles apart.", words(40))), [])

    def test_a_third_level_section_starts_a_new_section(self):
        text = GOOD.replace(THREAD, THREAD + "\n\nMore\n----\n\n.. discussion::\n\n   Another view.")
        self.assertEqual(findings(text), [])

    def test_a_fifth_level_section_does_not_start_a_section(self):
        text = GOOD.replace(THREAD, THREAD + "\n\nA\n-\n\nB\n~\n\n.. goal:: core.b\n\n   A goal.\n\n"
                                             ".. discussion::\n\n   One.\n\nC\n^\n\n.. discussion::\n\n   Two.")
        self.assertEqual(findings(text), [(line(text, "Two.") - 2, "argument-budget", None)])

    def test_a_second_argument_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n.. discussion::\n\n   One.\n\n.. discussion::\n\n   Two.\n"
        self.assertEqual(findings(text), [(line(text, "Two.") - 2, "argument-budget", None)])

    def test_an_argument_of_41_words_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n.. rationale::\n\n   " + words(41) + "\n"
        self.assertEqual(findings(text), [(line(text, "word word") - 2, "argument-budget", None)])

    def test_a_section_without_a_rule_or_a_goal_has_no_budget(self):
        text = GOOD + "\nNotes\n=====\n\n.. discussion::\n\n   One.\n\n.. discussion::\n\n   " + words(50) + "\n"
        self.assertEqual(findings(text), [])


class CodeKindsTest(unittest.TestCase):
    """doc.code-kinds"""

    def with_block(self, block):
        return GOOD.replace(THREAD, THREAD + "\n\n" + block)

    def test_a_literal_block_is_a_finding_on_the_line_that_docutils_gives(self):
        # docutils gives the first line of code for a literal block, and the
        # directive line for a code-block directive.
        for block, needle in [("Example::\n\n   x = 1\n", "x = 1"), (".. code-block:: python\n\n   x = 1\n", ".. code-block")]:
            with self.subTest(block=block):
                text = self.with_block(block)
                self.assertEqual(findings(text), [(line(text, needle),
                                                   "code-kinds", None)])

    def test_a_block_inside_a_list_item_is_a_finding(self):
        text = self.with_block("- An item::\n\n     x = 1\n")
        self.assertEqual(findings(text), [(line(text, "x = 1"), "code-kinds", None)])

    def test_a_check_passes(self):
        self.assertEqual(findings(self.with_block(".. check::\n\n   x = 1\n")), [])


class DottedWordsTest(unittest.TestCase):
    """doc.dotted-words"""

    def test_a_dotted_word_in_a_requirement_is_a_finding_on_its_line(self):
        for word in ["Q8.4", "9.09", "v1.2", "e.g.", "i.e.", "a.k.a.", "check.py",
                     "etc.", "Etc.", "vs.", "cf.", "approx.", "incl.", "esp.", "resp.", "ca.", "Ca."]:
            with self.subTest(word=word):
                text = with_requirement(f"The core shall give\n   the turn, {word} to each thread.")
                self.assertEqual(only("dotted-words", text), [(line(text, word), "dotted-words", "core.rotation")])

    def test_a_quoted_dotted_word_passes(self):
        for word in ["``Q8.4``", "``9.09``", "``e.g.``", "``etc.``"]:
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
    """doc.attribute-keys: docutils rejects an option that the label does not register."""

    def test_an_unknown_option_is_an_error_on_the_directive_line(self):
        text = GOOD.replace(TURN, TURN + "   :colour: red\n")
        book = Book({"core/core.rst": text})
        self.assertEqual(book.tuples(), [("book/core/core.rst", line(text, ".. definition:: core.turn"), "sphinx", None)])
        self.assertIn('unknown option: "colour"', book.warnings)

    def test_the_options_of_each_label_pass(self):
        text = GOOD.replace(TURN, TURN + "   :never: slot\n").replace(ROTATION, ROTATION + "   :impl: none\n")
        self.assertEqual(findings(text), [])

    # A RATIONALE, a DISCUSSION and an OPEN allow no option. Docutils reads an
    # option line under such a directive as text, so the extension rejects it.
    NO_OPTIONS = [(".. rationale::", ".. rationale::"), (".. rationale::", ".. discussion::"),
                  (".. open:: The thread count is not settled.", ".. open:: The thread count is not settled.")]

    def error(self, text, needle):
        """The chunks of text, after a check that text has one error, on the line of needle."""
        book = Book({"core/core.rst": text})
        self.assertEqual(book.tuples(), [("book/core/core.rst", line(text, needle), "sphinx", None)])
        return book

    def test_an_option_on_a_label_that_allows_none_is_an_error_on_the_directive_line(self):
        for old, new in self.NO_OPTIONS:
            with self.subTest(label=new):
                text = GOOD.replace(old, new + "\n   :parent: core.core")
                book = self.error(text, new)
                self.assertIn('unknown option: "parent"', book.warnings)
                self.assertNotIn("parent", " ".join(chunk.english for chunk in book.documents[0].chunks))

    def test_an_argument_on_a_label_that_takes_none_is_an_error_on_the_directive_line(self):
        for label in ["rationale", "discussion"]:
            with self.subTest(label=label):
                text = GOOD.replace(".. rationale::", f".. {label}:: core.why")
                book = self.error(text, f".. {label}:: core.why")
                self.assertIn("takes no argument", book.warnings)
                self.assertNotIn("core.why", " ".join(chunk.english for chunk in book.documents[0].chunks))

    CHECK = "\n.. check::\n\n   x = 1\n"

    def code(self, book):
        return "\n".join(block.text for block in book.documents[0].blocks)

    def test_an_option_on_a_check_is_an_error_on_the_directive_line(self):
        text = GOOD + self.CHECK.replace(".. check::\n", ".. check::\n   :kind: static\n")
        book = self.error(text, ".. check::")
        self.assertIn('unknown option: "kind"', book.warnings)
        self.assertNotIn("kind", self.code(book))

    def test_an_argument_on_a_twin_or_a_check_is_an_error_on_the_directive_line(self):
        for old, new in [("   .. twin::\n", "   .. twin:: extra\n"), (".. check::", ".. check:: extra")]:
            with self.subTest(directive=new.strip()):
                text = (GOOD + self.CHECK).replace(old, new)
                book = self.error(text, new.strip())
                self.assertIn(f"the {new.split()[1][:-2]} directive takes no argument.", book.warnings)
                self.assertNotIn("extra", self.code(book))

    def test_the_options_and_argument_of_a_code_directive_pass(self):
        self.assertEqual(findings(GOOD + self.CHECK), [])

    def test_text_under_the_directive_line_is_not_an_option(self):
        for first in ["A thread's instructions are eight cycles apart.", ":rule:`core.rotation` gives the order."]:
            with self.subTest(first=first):
                text = GOOD.replace(".. rationale::\n\n   A thread's instructions are eight cycles apart.",
                                    f".. rationale::\n   {first}")
                self.assertNotEqual(text, GOOD)
                self.assertEqual(findings(text), [])


class KnownWordsTest(unittest.TestCase):
    """doc.general-word, doc.known-word and doc.known-words"""

    SLOT = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time slot` is a turn of the core.\n"

    def known(self, text, general=GENERAL):
        return only("known-words", text, general=general)

    def test_a_chapter_of_general_words_and_defined_terms_passes(self):
        self.assertEqual(findings(GOOD, general=GENERAL), [])

    def test_an_unknown_word_in_a_goal_or_a_rule_is_a_finding_on_its_line(self):
        for word, needle, anchor in [("timing", "the timing of", "core.timing"),
                                     ("give", "shall give", "core.rotation"),
                                     ("cycle", "A :dfn:`turn`", "core.turn"),
                                     ("runs", "The :dfn:`core`", "core.core")]:
            with self.subTest(word=word):
                self.assertEqual(self.known(GOOD, GENERAL - {word}), [(line(GOOD, needle), "known-words", anchor)])

    def test_each_unknown_word_is_a_finding(self):
        text = GOOD.replace("the timing of", "the zyx timing wvu of")
        self.assertEqual(self.known(text), [(line(text, "zyx"), "known-words", "core.timing")] * 2)

    def test_the_finding_is_on_the_line_of_the_word(self):
        self.assertEqual(self.known(GOOD, GENERAL - {"t"}),
                         [(line(GOOD, "thread *t* to"), "known-words", "core.rotation")] * 2)

    def test_a_word_outside_a_goal_or_a_rule_passes(self):
        for old, new in [("eight cycles apart.", "eight zyx cycles apart."),
                         ("The thread count is", "The zyx thread count is"),
                         ("is prose.", "is zyx prose."),
                         ("Rotation\n========", "Zyx\n========")]:
            with self.subTest(new=new):
                self.assertEqual(self.known(GOOD.replace(old, new)), [])

    def test_a_word_in_a_quotation_passes(self):
        for quoted in ["``zyx``", ":rule:`core.core`"]:
            with self.subTest(quoted=quoted):
                self.assertEqual(self.known(GOOD.replace("the timing of", f"the {quoted} timing of")), [])

    def test_case_does_not_matter(self):
        self.assertEqual(self.known(GOOD.replace("the timing of", "the TIMING of")), [])

    def test_a_defined_term_needs_no_listing(self):
        self.assertEqual(self.known(GOOD, GENERAL | {"turn", "core"}), [])
        self.assertEqual(self.known(GOOD.replace("the timing of", "the core of")), [])

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        self.assertEqual(self.known(GOOD.replace("A :dfn:`turn` is", "A :dfn:`Turn` is")), [])

    def test_the_endings_s_es_and_apostrophe_s_keep_a_word_known(self):
        self.assertEqual(self.known(GOOD.replace("the timing of", "the timings, core's, turns, toes of")), [])

    def test_other_endings_do_not(self):
        for word in ["timingly", "cored", "turner", "thready"]:
            with self.subTest(word=word):
                text = GOOD.replace("the timing of", f"the {word} of")
                self.assertEqual(self.known(text), [(line(text, word), "known-words", "core.timing")])

    def test_a_word_of_a_defined_term_is_known_only_inside_the_whole_term(self):
        for sentence, unknown in [("The core shall give the time slot to thread ``t``.", []),
                                  ("The core shall give the time slots to thread ``t``.", []),
                                  ("The core shall give the time\n   slot to thread ``t``.", []),
                                  ("The core shall give the slot to thread ``t``.", ["slot"]),
                                  ("The core shall give the time to thread ``t``.", ["time"]),
                                  ("The core shall give the times slot to thread ``t``.", ["times", "slot"])]:
            with self.subTest(sentence=sentence):
                text = self.SLOT.replace(SENTENCE, sentence)
                self.assertEqual(self.known(text), [(line(text, "The core shall"), "known-words", "core.rotation")]
                                 * len(unknown))

    def test_the_longest_defined_term_wins(self):
        text = self.SLOT + "\n.. definition:: core.time\n   :parent: core.core\n\n   A :dfn:`time` is a zyx.\n"
        self.assertEqual(self.known(text, GENERAL | {"zyx"}), [])
        text = text.replace(SENTENCE, "The core shall give the time slot of the time to thread ``t``.")
        self.assertEqual(self.known(text, GENERAL | {"zyx"}), [])

    def test_the_list_is_read_in_lower_case_and_without_comments(self):
        self.assertEqual(self.known(GOOD, GENERAL - {"the"} | {"THE"}), [])
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "words.txt"
            path.write_text("# a comment\nthe\n\n  cycle  \n")
            self.assertEqual(bcw.listed(path), {"the", "cycle"})

    def test_a_missing_list_is_an_empty_list(self):
        self.assertEqual(bcw.listed("/nonexistent/general-words.txt"), set())


class GeneralWordsTest(unittest.TestCase):
    """doc.general-words"""

    SLOT = KnownWordsTest.SLOT

    def general(self, text, extra):
        return only("general-words", text, general=GENERAL | extra)

    def test_a_listed_defined_term_is_a_finding_on_its_definition(self):
        for word in ["turn", "turns", "turn's", "turnes"]:
            with self.subTest(word=word):
                self.assertEqual(self.general(GOOD, {word}),
                                 [(line(GOOD, ".. definition:: core.turn"), "general-words", "core.turn")])

    def test_each_listed_form_is_a_finding(self):
        self.assertEqual(self.general(GOOD, {"turn", "turns"}),
                         [(line(GOOD, ".. definition:: core.turn"), "general-words", "core.turn")] * 2)

    def test_a_listed_multi_word_term_is_a_finding(self):
        for word in ["time slot", "time slots"]:
            with self.subTest(word=word):
                self.assertEqual(self.general(self.SLOT, {word}),
                                 [(line(self.SLOT, ".. definition:: core.slot"), "general-words", "core.slot")])

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        text = GOOD.replace("A :dfn:`turn` is", "A :dfn:`Turn` is")
        self.assertEqual(self.general(text, {"turn"}),
                         [(line(text, ".. definition:: core.turn"), "general-words", "core.turn")])

    def test_one_word_of_a_multi_word_term_passes(self):
        self.assertEqual(self.general(self.SLOT, {"time", "slot"}), [])

    def test_a_word_that_only_starts_like_a_defined_term_passes(self):
        self.assertEqual(self.general(GOOD, {"turner", "cored", "turnstile"}), [])


class QuotationAcrossLinesTest(unittest.TestCase):
    """doc.quotation: a quotation that runs across a line break is still a quotation."""

    def test_known_words_skip_a_literal_across_a_line_break(self):
        text = GOOD.replace("in the rotation.", "in the ``zyx\n   wvu`` rotation.")
        self.assertEqual(only("known-words", text, general=GENERAL), [])

    def test_a_dfn_across_a_line_break_is_one_defined_term(self):
        text = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time\n   slot` is a turn of the core.\n"
        self.assertEqual(only("known-words", text, general=GENERAL), [])
        self.assertIn("time slot", [chunk.term for chunk in Book({"core/core.rst": text}).documents[0].chunks])

    def test_the_vocabulary_skips_a_literal_across_a_line_break(self):
        text = VocabularyTest.NEVER.replace("is a thread's cycle", "is a thread's ``cpu\n   slot`` cycle")
        self.assertEqual(only("vocabulary", text), [])

    def test_one_shall_skips_a_literal_across_a_line_break(self):
        text = with_requirement("The core shall give the turn, not ``the\n   shall``, to each thread.")
        self.assertEqual(only("one-shall", text), [])

    def test_dotted_words_skip_a_literal_across_a_line_break(self):
        text = with_requirement("The core shall give the turn, ``see\n   Q8.4``, to each thread.")
        self.assertEqual(only("dotted-words", text), [])

    def test_the_linter_skips_a_literal_across_a_line_break(self):
        text = GOOD.replace("in the rotation.", "in the rotation, ``a;\n   b``.")
        self.assertEqual(only("linter", text), [])

    def test_ears_skips_a_literal_across_a_line_break(self):
        text = with_requirement("Each core shall give ``a,\n   b`` to thread *t*.")
        self.assertEqual(only("ears", text), [])

    def test_a_word_after_the_literal_keeps_its_own_line(self):
        text = GOOD.replace("in the rotation.", "in the ``x\n   y`` qqq rotation.")
        self.assertEqual(only("known-words", text, general=GENERAL), [(line(text, "qqq"), "known-words", "core.turn")])


def chapter(title, kind="reference", body=""):
    rule = "=" * len(title)
    return f":kind: {kind}\n\n{rule}\n{title}\n{rule}\n\nOverview\n========\n\nText.\n{body}"


DESIGN = chapter("Design", body="\nGoals\n=====\n\n.. goal:: design.timing\n\n   No thread can change the timing.\n")
CORE_CHAPTER = GOOD.replace(":parent: core.timing", ":parent: design.timing")


class ChapterPathTest(unittest.TestCase):
    """doc.chapter and doc.chapter-path"""

    def test_a_chapter_at_book_name_name_rst_passes(self):
        self.assertEqual(Book({"core/core.rst": GOOD}).tuples(), [])

    def test_a_chapter_at_another_path_is_a_finding_on_line_1(self):
        for relative in ["core/x.rst", "x.rst", "core/sub/sub.rst"]:
            with self.subTest(relative=relative):
                self.assertEqual([f for f in Book({relative: GOOD}).tuples() if f[2] == "chapter-path"],
                                 [("book/" + relative, 1, "chapter-path", None)])


class ChapterTitleTest(unittest.TestCase):
    """doc.chapter-title"""

    def test_a_chapter_without_a_title_is_a_finding_on_line_1(self):
        text = ":kind: reference\n\nJust text.\n"
        self.assertEqual(only("chapter-title", text), [(1, "chapter-title", None), (3, "chapter-title", None)])

    def test_a_second_title_is_a_finding_on_its_line(self):
        text = GOOD + "\n====\nMore\n====\n\nText.\n"
        self.assertEqual(only("chapter-title", text), [(line(text, "More"), "chapter-title", None)])

    def test_text_before_the_title_is_a_finding_on_its_line(self):
        text = GOOD.replace(":kind: reference\n\n", ":kind: reference\n\nIntro.\n\n")
        self.assertEqual(only("chapter-title", text), [(line(text, "Intro."), "chapter-title", None)])


class ChapterKindTest(unittest.TestCase):
    """doc.chapter-kind"""

    def test_each_kind_passes(self):
        for kind in ["tutorial", "how-to", "reference", "explanation"]:
            with self.subTest(kind=kind):
                self.assertEqual(only("chapter-kind", GOOD.replace(":kind: reference", f":kind: {kind}")), [])

    def test_a_missing_or_unknown_kind_is_a_finding_on_line_1(self):
        for text in [GOOD.replace(":kind: reference\n\n", ""), GOOD.replace(":kind: reference", ":kind: guide")]:
            with self.subTest(start=text[:20]):
                self.assertEqual(only("chapter-kind", text), [(1, "chapter-kind", None)])


class HeadingNumbersTest(unittest.TestCase):
    """doc.heading-numbers"""

    def test_a_numbered_heading_is_a_finding_on_its_line(self):
        for old, new in [("Rotation\n========", "2. Rotation\n==========="),
                         ("Rotation\n========", "4.2 Legs\n========"),
                         ("====\nCore\n====", "======\n1 Core\n======"),
                         ("Goals\n=====", "3.\n====="), ("Goals\n=====", "12\n====="),
                         ("Rotation\n========", "2.1 rotation\n============")]:
            with self.subTest(new=new):
                text = GOOD.replace(old, new)
                title = [part for part in new.splitlines() if not set(part) <= {"="}][0]
                self.assertEqual(only("heading-numbers", text), [(line(text, title), "heading-numbers", None)])

    def test_a_heading_that_starts_with_a_word_a_compound_or_a_count_passes(self):
        for new in ["Rotation 2\n==========", "64-bit counters\n===============", "v2 rotation\n===========",
                    "8 threads\n=========", "2 cycles apart\n=============="]:
            with self.subTest(new=new):
                self.assertEqual(only("heading-numbers", GOOD.replace("Rotation\n========", new)), [])


class AnchorPrefixTest(unittest.TestCase):
    """doc.anchor-prefix"""

    def test_an_anchor_of_another_chapter_is_a_finding_on_the_directive_line(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition:: bank.turn")
        self.assertEqual(findings(text), [(line(text, "bank.turn"), "anchor-prefix", "bank.turn")])

    def test_a_goal_is_covered(self):
        text = GOOD.replace(".. goal:: core.timing", ".. goal:: design.timing")
        self.assertEqual(only("anchor-prefix", text), [(line(text, "design.timing"), "anchor-prefix", "design.timing")])

    def test_the_prefix_is_the_file_name(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition:: cor.turn")
        self.assertEqual([f for f in Book({"core/core.rst": text}).tuples() if f[2] == "anchor-prefix"],
                         [("book/core/core.rst", line(text, "cor.turn"), "anchor-prefix", "cor.turn")])
        self.assertEqual([f for f in Book({"x/core.rst": GOOD}).tuples() if f[2] == "anchor-prefix"], [])


def order(chapters):
    return bcw.chapter_order(Book(chapters).documents)


class ChapterOrderTest(unittest.TestCase):
    """doc.chapter-order and doc.chapters-ordered"""

    def test_a_chapter_comes_after_the_chapters_of_its_parents(self):
        chapters = {"core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN}
        self.assertEqual(order(chapters), (["design", "core"], []))
        self.assertEqual(Book(chapters).tuples(), [])

    def test_ties_go_in_alphabetical_order(self):
        self.assertEqual(order({"b/b.rst": chapter("B"), "a/a.rst": chapter("A")}), (["a", "b"], []))

    def test_the_first_free_name_goes_next(self):
        chapters = {"doc/doc.rst": chapter("Doc"), "core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN}
        self.assertEqual(order(chapters), (["design", "core", "doc"], []))

    def test_a_parent_in_the_same_chapter_adds_no_edge(self):
        self.assertEqual(order({"core/core.rst": GOOD}), (["core"], []))

    def test_a_cycle_of_chapters_is_a_finding_on_line_1_of_each(self):
        cycle = DESIGN + "\n.. definition:: design.zyx\n   :parent: core.core\n\n   A :dfn:`zyx` is a thing.\n"
        chapters = {"core/core.rst": CORE_CHAPTER, "design/design.rst": cycle, "a/a.rst": chapter("A")}
        self.assertEqual(order(chapters), (["a"], ["core", "design"]))
        self.assertEqual([f for f in Book(chapters).tuples() if f[2] == "chapters-ordered"],
                         [("book/core/core.rst", 1, "chapters-ordered", None),
                          ("book/design/design.rst", 1, "chapters-ordered", None)])

    def test_an_unknown_parent_adds_no_edge(self):
        text = CORE_CHAPTER.replace(TURN, TURN.replace("core.core", "gone.x"))
        self.assertEqual(order({"core/core.rst": text, "design/design.rst": DESIGN}), (["design", "core"], []))

    def test_the_kinds_come_in_order_before_the_trace(self):
        chapters = {"a/a.rst": chapter("A", "explanation"), "b/b.rst": chapter("B", "reference"),
                    "c/c.rst": chapter("C", "how-to"), "d/d.rst": chapter("D", "tutorial")}
        self.assertEqual(order(chapters), (["d", "c", "b", "a"], []))

    def test_a_parent_in_another_kind_adds_no_edge(self):
        chapters = {"core/core.rst": CORE_CHAPTER.replace(":kind: reference", ":kind: tutorial"),
                    "design/design.rst": DESIGN}
        self.assertEqual(order(chapters), (["core", "design"], []))


class CitationLinkTest(unittest.TestCase):
    """A citation links to the chunk that carries its anchor."""

    CITING = CORE_CHAPTER.replace("eight cycles apart.",
                                  "eight cycles apart, as :rule:`design.timing` and :rule:`core.turn` say.")

    def references(self, book, docname):
        return [(node.get("refuri"), node.get("refid"), node.astext())
                for node in book.resolved[docname].findall(nodes.reference)]

    def test_each_citation_resolves_to_its_anchor(self):
        book = Book({"core/core.rst": self.CITING, "design/design.rst": DESIGN})
        self.assertEqual(book.tuples(), [])
        self.assertEqual(self.references(book, "core/core"), [("#design.timing", None, "design.timing"),
                                                              (None, "core.turn", "core.turn")])

    def test_each_anchored_chunk_carries_its_anchor_as_its_id(self):
        book = Book({"core/core.rst": GOOD})
        ids = [node["ids"] for node in book.resolved["core/core"].findall(bcw.chunk)]
        self.assertEqual(ids, [["core.rotation"], [], [], ["core.turn"], ["core.core"], ["core.timing"]])

    def test_the_checks_still_read_the_citation_as_a_quotation(self):
        book = Book({"core/core.rst": self.CITING, "design/design.rst": DESIGN}, general=GENERAL | {"eight",
                    "cycles", "apart", "as", "and", "say"})
        self.assertEqual([f for f in book.tuples() if f[2] == "known-words"], [])


def parameter(anchor, value, parent="core.core", unit=None, text="The number of threads."):
    """A PARAMETER chunk to add at the end of GOOD. value None leaves out the value option."""
    lines = [f"\n.. parameter:: {anchor}", f"   :parent: {parent}"]
    lines += [f"   :value: {value}"] if value is not None else []
    lines += [f"   :unit: {unit}"] if unit else []
    return "\n".join(lines) + f"\n\n   {text}\n"


THREADS = parameter("core.threads", "8", unit="threads")
WIDTH = parameter("core.turn-width", "clog2(core.threads)", parent="core.threads", unit="bits",
                  text="The width of the index of a thread.")


class ParameterValuesTest(unittest.TestCase):
    """doc.parameter-value and doc.parameter-values"""

    def test_a_literal_and_a_derived_value_evaluate(self):
        book = Book({"core/core.rst": GOOD + THREADS + WIDTH})
        self.assertEqual(book.tuples(), [])
        self.assertEqual(book.values, {"core.threads": 8, "core.turn-width": 3})

    def test_each_operator_and_function(self):
        for value, result in [("core.threads // 3 + core.threads % 3 + 2 ** 2", 8),
                              ("min(core.threads, 4) * 2 - 1", 7), ("max(1, 2, core.threads)", 8),
                              ("(core.threads - 1) * -1", -7), ("clog2(1)", 0), ("clog2(5)", 3),
                              ("clog2(8)", 3), ("clog2(9)", 4)]:
            with self.subTest(value=value):
                book = Book({"core/core.rst": GOOD + THREADS + parameter("core.x", value)})
                self.assertEqual((book.tuples(), book.values["core.x"]), ([], result))

    def test_a_value_that_does_not_evaluate_is_a_finding_on_its_value_line(self):
        for value in ["8 +", "core.nothing", "core.core", "8 / 2", "8 << 1", "abs(8)", "x", "2 ** -1",
                      "core.threads.x", "'8'", "1 // 0", "min()", "2 ** 2000"]:
            with self.subTest(value=value):
                text = GOOD + THREADS + parameter("core.x", value)
                book = Book({"core/core.rst": text})
                self.assertEqual([f for f in book.tuples() if f[2] != "references"],
                                 [("book/core/core.rst", line(text, f":value: {value}"), "parameter-values", "core.x")])
                self.assertNotIn("core.x", book.values)

    def test_a_missing_value_is_a_finding_on_the_directive_line(self):
        text = GOOD + parameter("core.x", None)
        self.assertEqual(only("parameter-values", text), [(line(text, ".. parameter:: core.x"), "parameter-values",
                                                           "core.x")])

    def test_a_cycle_is_a_finding_on_each_value_in_it(self):
        text = GOOD + parameter("core.a", "core.b + 1") + parameter("core.b", "core.a")
        self.assertEqual(only("parameter-values", text),
                         [(line(text, ":value: core.b + 1"), "parameter-values", "core.a"),
                          (line(text, ":value: core.a"), "parameter-values", "core.b")])

    def test_a_value_that_names_a_value_that_fails_is_a_finding(self):
        text = GOOD + parameter("core.a", "8 +") + parameter("core.b", "core.a")
        self.assertEqual(only("parameter-values", text),
                         [(line(text, ":value: 8 +"), "parameter-values", "core.a"),
                          (line(text, ":value: core.a"), "parameter-values", "core.b")])
        self.assertIn("core.a", [f.message for f in Book({"core/core.rst": text}).findings
                                 if f.anchor == "core.b"][0])

    def test_a_value_can_name_a_parameter_of_another_chapter(self):
        design = DESIGN + "\n.. parameter:: design.threads\n   :parent: design.timing\n   :value: 8\n\n   Text.\n"
        core = CORE_CHAPTER + parameter("core.x", "design.threads * 2", parent="core.core")
        self.assertEqual(Book({"core/core.rst": core, "design/design.rst": design}).values["core.x"], 16)


class ConstantNamesTest(unittest.TestCase):
    """doc.constant-name and doc.constant-names"""

    def test_the_constant_name_is_the_anchor_in_upper_case_with_underscores(self):
        self.assertEqual(bcw.constant_name("core.turn-width"), "CORE_TURN_WIDTH")

    def test_two_parameters_with_one_constant_name_are_a_finding(self):
        text = GOOD + parameter("core.turn-width", "3") + parameter("core.turn.width", "3")
        self.assertEqual(only("constant-names", text),
                         [(line(text, ".. parameter:: core.turn.width"), "constant-names", "core.turn.width")])


class ParamCitationTest(unittest.TestCase):
    """doc.citation and doc.param-citations"""

    def test_a_param_citation_of_a_parameter_passes(self):
        text = (GOOD + THREADS).replace("eight cycles apart.", "eight cycles apart, of :param:`core.threads`.")
        self.assertEqual(findings(text), [])

    def test_a_param_citation_of_another_chunk_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :param:`core.core` says.")
        self.assertEqual(findings(text), [(line(text, ":param:"), "param-citations", None)])

    def test_a_param_citation_of_no_anchor_is_a_references_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :param:`core.gone` says.")
        self.assertEqual(findings(text), [(line(text, ":param:"), "references", None)])

    def test_the_word_checks_read_it_as_a_quotation(self):
        text = (GOOD + THREADS).replace("the timing of another", "the timing of :param:`core.threads` another")
        self.assertEqual(only("known-words", text, general=GENERAL | {"number", "threads"}), [])


class ParameterTangleTest(unittest.TestCase):
    """The tangle writes each PARAMETER as a constant in a SystemVerilog package and a Python module."""

    def test_each_constant_follows_a_marker_that_names_its_value_line(self):
        text = GOOD + THREADS + WIDTH
        files = Book({"core/core.rst": text}, tangle=True).files
        threads, width = line(text, ":value: 8"), line(text, ":value: clog2")
        self.assertEqual(files["build/rtl/bcw_params.sv"],
                         "// The PARAMETERs of the book, which tools/bcw.py writes.\n"
                         "package bcw_params;\n"
                         "/* verilator lint_off UNUSEDPARAM */\n"
                         f"// bcw: book/core/core.rst:{threads}\nlocalparam int CORE_THREADS = 8;\n"
                         f"// bcw: book/core/core.rst:{width}\nlocalparam int CORE_TURN_WIDTH = 3;\n"
                         "/* verilator lint_on UNUSEDPARAM */\n"
                         "endpackage\n")
        self.assertEqual(files["build/model/bcw_params.py"],
                         "# The PARAMETERs of the book, which tools/bcw.py writes.\n"
                         f"# bcw: book/core/core.rst:{threads}\nCORE_THREADS = 8\n"
                         f"# bcw: book/core/core.rst:{width}\nCORE_TURN_WIDTH = 3\n")

    def test_the_line_mapper_maps_a_constant_to_its_value_line(self):
        text = GOOD + THREADS
        files = Book({"core/core.rst": text}, tangle=True).files
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "bcw_params.sv"
            path.write_text(files["build/rtl/bcw_params.sv"])
            self.assertEqual(linemap.lookup(str(path), 5), ("book/core/core.rst", line(text, ":value: 8")))

    def lint(self, module):
        """The exit status and messages of Verilator -Wall on the package of GOOD + THREADS + WIDTH and module."""
        files = Book({"core/core.rst": GOOD + THREADS + WIDTH}, tangle=True).files
        with tempfile.TemporaryDirectory() as name:
            package, source = Path(name) / "bcw_params.sv", Path(name) / "count_threads.v"
            package.write_text(files["build/rtl/bcw_params.sv"])
            source.write_text(module)
            result = subprocess.run(["verilator", "--lint-only", "-Wall", str(package), str(source)],
                                    capture_output=True, text=True)
        return result.returncode, result.stderr

    COUNT = ("module count_threads\n    import bcw_params::*;\n    (output wire [7:0] n);\n{}"
             "    assign n = 8'(CORE_THREADS);\nendmodule\n")

    def test_a_module_that_reads_only_some_constants_lints_clean_with_the_package(self):
        self.assertEqual(self.lint(self.COUNT.format("")), (0, ""))

    def test_an_unused_parameter_of_a_module_still_fails_the_lint(self):
        status, messages = self.lint(self.COUNT.format("    localparam int SPARE = 1;\n"))
        self.assertNotEqual(status, 0)
        self.assertIn("Parameter is not used: 'SPARE'", messages)


def target(anchor, value, parent="core.core", unit=None, text="The number of threads."):
    """A TARGET chunk to add at the end of GOOD. value or parent None leaves out that option."""
    lines = [f"\n.. target:: {anchor}"]
    lines += [f"   :parent: {parent}"] if parent is not None else []
    lines += [f"   :value: {value}"] if value is not None else []
    lines += [f"   :unit: {unit}"] if unit else []
    return "\n".join(lines) + f"\n\n   {text}\n"


class TargetTest(unittest.TestCase):
    """doc.target-values, doc.target-parents, and the rules that a TARGET shares with the rules"""

    def test_a_target_with_its_options_passes_and_its_value_can_derive_from_a_parameter(self):
        book = Book({"core/core.rst": GOOD + THREADS + target("core.aim", "core.threads * 2", "core.threads",
                                                             "threads")})
        self.assertEqual(book.tuples(), [])
        self.assertEqual(book.values["core.aim"], 16)

    def test_a_target_without_an_anchor_is_an_error_on_its_line(self):
        text = GOOD + "\n.. target::\n\n   The number of threads.\n"
        book = Book({"core/core.rst": text})
        self.assertEqual([(path, number) for path, number, _ in book.others()],
                         [("book/core/core.rst", line(text, ".. target::"))])
        self.assertIn("1 argument(s) required, 0 supplied", book.warnings)

    def test_a_target_without_a_value_is_a_finding_on_the_directive_line(self):
        text = GOOD + target("core.aim", None)
        self.assertEqual(findings(text), [(line(text, ".. target:: core.aim"), "target-values", "core.aim")])

    def test_a_target_value_that_names_a_target_is_a_finding(self):
        text = GOOD + target("core.aim", "8") + target("core.other", "core.aim + 1")
        book = Book({"core/core.rst": text})
        self.assertEqual(book.tuples(), [("book/core/core.rst", line(text, ":value: core.aim + 1"), "target-values",
                                          "core.other")])
        self.assertIn("core.aim is a TARGET", book.findings[0].message)

    def test_a_parameter_value_that_names_a_target_is_a_finding(self):
        text = GOOD + target("core.aim", "8") + parameter("core.x", "core.aim")
        book = Book({"core/core.rst": text})
        self.assertEqual(book.tuples(), [("book/core/core.rst", line(text, ":value: core.aim"), "parameter-values",
                                          "core.x")])
        self.assertIn("core.aim is a TARGET", book.findings[0].message)
        self.assertNotIn("core.x", book.values)

    def test_a_parent_that_names_a_target_is_a_finding_on_the_parent_line(self):
        for parents in ["core.aim", "core.core, core.aim"]:
            with self.subTest(parents=parents):
                text = GOOD + target("core.aim", "8") + parameter("core.x", "1", parent=parents)
                self.assertEqual(findings(text), [(line(text, f":parent: {parents}"), "target-parents", "core.x")])

    def test_a_target_without_a_parent_does_not_reach_a_goal(self):
        text = GOOD + target("core.aim", "8", parent=None)
        self.assertEqual(findings(text), [(line(text, ".. target:: core.aim"), "reaches-goal", "core.aim")])

    def test_the_word_checks_read_a_target(self):
        text = GOOD + target("core.aim", "8", text="The aim of the threads.")
        self.assertEqual(only("known-words", text, general=GENERAL | {"the", "of"}),
                         [(line(text, "The aim of"), "known-words", "core.aim")])

    def test_a_param_citation_of_a_target_passes(self):
        text = (GOOD + target("core.aim", "8")).replace("eight cycles apart.", "eight cycles apart, of :param:`core.aim`.")
        self.assertEqual(findings(text), [])

    def test_the_tangle_writes_no_target(self):
        text = GOOD + THREADS + target("core.aim", "8") + target("core.threads-aim", "core.threads")
        book = Book({"core/core.rst": text}, tangle=True)
        self.assertEqual(book.tuples(), [])
        for path in ["build/rtl/bcw_params.sv", "build/model/bcw_params.py"]:
            with self.subTest(path=path):
                self.assertIn("CORE_THREADS", book.files[path])
                self.assertNotIn("AIM", book.files[path])

    def test_a_target_shares_no_constant_name_with_a_parameter(self):
        text = GOOD + parameter("core.turn-width", "3") + target("core.turn.width", "3")
        self.assertEqual(findings(text), [])


class TangleTest(unittest.TestCase):
    """The tangle writes each file of a twin or a source, with a marker before each block."""

    def test_each_file_holds_its_blocks_after_a_marker_that_names_the_first_line(self):
        files = Book({"core/core.rst": GOOD}, tangle=True).files
        # The constant files are always written, and here they hold no constant.
        self.assertEqual(files.pop("build/rtl/bcw_params.sv"),
                         "// The PARAMETERs of the book, which tools/bcw.py writes.\npackage bcw_params;\n"
                         "/* verilator lint_off UNUSEDPARAM */\n/* verilator lint_on UNUSEDPARAM */\nendpackage\n")
        self.assertEqual(files.pop("build/model/bcw_params.py"),
                         "# The PARAMETERs of the book, which tools/bcw.py writes.\n")
        self.assertEqual(files, {
            "build/model/core_rotate.py": f"# bcw: book/core/core.rst:{line(GOOD, 'def core_rotate')}\n"
                                          "def core_rotate(turn):\n    return {'next': turn + 1}\n",
            "build/rtl/core/core_rotate.v": f"// bcw: book/core/core.rst:{line(GOOD, 'module core_rotate')}\n"
                                            "module core_rotate (input wire [2:0] turn, output wire [2:0] next);\n"
                                            "    assign next = turn + 3'd1;\nendmodule\n"})

    def test_blocks_of_one_file_join_in_order(self):
        text = GOOD + "\n.. source:: build/rtl/core/core_rotate.v\n\n   // more\n"
        files = Book({"core/core.rst": text}, tangle=True).files
        self.assertTrue(files["build/rtl/core/core_rotate.v"].endswith(
            f"endmodule\n// bcw: book/core/core.rst:{line(text, '// more')}\n// more\n"))

    def test_without_a_root_nothing_is_tangled(self):
        self.assertEqual(Book({"core/core.rst": GOOD}).files, {})


if __name__ == "__main__":
    unittest.main()
