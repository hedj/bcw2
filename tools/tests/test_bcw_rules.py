"""Tests of the documentation rules of tools/bcw.py that need the whole book, one class per rule.

Each test changes one thing in GOOD from tools/tests/book.py, and expects exactly the
findings of the rule that the change breaks.
"""

import signal
import subprocess
import tempfile
from pathlib import Path

import pytest
from docutils import nodes

import bcw
import linemap
from book import (CORE_CHAPTER, DESIGN, GENERAL, GOOD, THREADS, WIDTH, Book, chapter, findings, line,
                  only, parameter, target)

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


class ImplementedTest:
    """doc.implemented"""

    UNUSED = GOOD.replace(IMPLEMENTS, "")

    def test_a_requirement_that_nothing_implements_is_a_finding(self):
        assert findings(self.UNUSED) == [(line(GOOD, ".. requirement::"), "implemented", "core.rotation")]

    def test_impl_none_is_an_exit(self):
        text = self.UNUSED.replace(ROTATION, ROTATION + "   :impl: none\n")
        assert findings(text) == []

    def test_a_tool_comment_implements_it(self):
        assert findings(self.UNUSED, tools={"tool.py": "# implements: core.rotation\n"}) == []

    def test_an_implements_list_can_name_several_anchors(self):
        text = GOOD.replace(IMPLEMENTS, "   :implements: core.core, core.rotation\n")
        assert findings(text) == []

    def test_a_citation_does_not_implement(self):
        text = self.UNUSED.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotation` says.")
        assert findings(text) == [(line(text, ".. requirement::"), "implemented", "core.rotation")]

    def test_tool_implements_reads_whole_comment_lines_only(self, tmp_path):
        path = tmp_path / "tool.py"
        path.write_text("# implements: doc.a\n    # implements: doc.b\nx = '# implements: doc.c'\n")
        assert bcw.tool_implements([path]) == [(str(path), 1, "doc.a"), (str(path), 2, "doc.b")]


class ReferencesTest:
    """doc.references"""

    def test_an_unknown_parent_is_a_finding_on_the_option_line(self):
        text = GOOD.replace(TURN, TURN.replace("core.core", "core.nothing"))
        assert findings(text) == [(line(text, ":parent: core.nothing"), "references", "core.turn")]

    def test_a_parent_list_can_name_several_anchors(self):
        text = GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))
        assert findings(text) == []

    def test_an_empty_parent_entry_is_a_finding(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.timing,"))
        assert findings(text) == [(line(text, ":parent: core.timing,"), "references", "core.core")]

    def test_an_implements_entry_that_names_no_anchor_is_a_finding(self):
        text = GOOD.replace(IMPLEMENTS, "   :implements: core.rotation, core.gone\n")
        assert findings(text) == [(line(text, ".. source::"), "references", None)]

    def test_a_tool_comment_that_names_no_anchor_is_a_finding(self):
        book = Book({"core/core.rst": GOOD}, tools={"x.py": "\n\n# implements: doc.gone\n"})
        assert book.tuples() == [("tools/x.py", 3, "references", None)]

    def test_a_citation_must_name_an_anchor(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotate` says.")
        assert findings(text) == [(line(text, "core.rotate`"), "references", None)]

    def test_citations_in_headings_and_lists_count(self):
        text = GOOD.replace("Rotation\n========", "Rotation :rule:`core.nothing`\n=============================")
        text += "\n- :rule:`core.gone`\n"
        assert findings(text) == [(line(text, "core.nothing"), "references", None),
                                  (line(text, "core.gone"), "references", None)]

    def test_good_citations_and_other_quotations_pass(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :rule:`core.rotation` and ``check.py`` say.")
        assert findings(text) == []

    def test_a_citation_of_a_retired_anchor_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, unlike :rule:`core.turn`.")
        assert (line(text, "unlike"), "references", None) in findings(text, retired={"core.turn"})

    def test_a_citation_inside_a_code_block_is_not_a_reference(self):
        assert findings(GOOD + "\n.. check::\n\n   :rule:`core.nothing`\n") == []


class ReachesGoalTest:
    """doc.reaches-goal"""

    CYCLE = GOOD.replace(CORE, CORE.replace("core.timing", "core.turn"))

    def test_a_rule_without_a_parent_is_a_finding_on_its_directive(self):
        text = GOOD.replace(ROTATION, ".. requirement:: core.rotation\n")
        assert findings(text) == [(line(text, ".. requirement::"), "reaches-goal", "core.rotation")]

    def test_a_cycle_is_a_finding_on_the_parent_line_of_each_chunk_in_it(self):
        assert findings(self.CYCLE) == [(line(self.CYCLE, ":parent: core.core"), "reaches-goal", "core.turn"),
                                        (line(self.CYCLE, ":parent: core.turn"), "reaches-goal", "core.core")]

    def test_the_message_names_the_fault(self):
        assert self.messages(self.CYCLE) == ["the chunk reaches itself through its parents"] * 2
        short = GOOD.replace(CORE, ".. definition:: core.core\n")
        assert self.messages(short) == ["the chunk reaches no GOAL through its parents",
                                        "the chunk has no parent"]

    def messages(self, text):
        return [f.message for f in Book({"core/core.rst": text}).findings if f.check == "reaches-goal"]

    def test_a_chain_that_stops_short_of_a_goal_is_a_finding(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.orphan")).replace(
            THREAD, ".. definition:: core.orphan\n\n   An :dfn:`orphan` has no parent.\n\n" + THREAD)
        assert findings(text) == [(line(text, ":parent: core.core"), "reaches-goal", "core.turn"),
                                  (line(text, ":parent: core.orphan"), "reaches-goal", "core.core"),
                                  (line(text, ".. definition:: core.orphan"), "reaches-goal", "core.orphan")]

    def test_a_rationale_takes_no_anchor(self):
        text = GOOD.replace(".. rationale::", ".. rationale:: core.why")
        book = Book({"core/core.rst": text})
        assert "the rationale directive takes no argument." in book.warnings
        assert "core.why" not in [chunk.anchor for chunk in book.documents[0].chunks]

    def test_a_goal_can_serve_another_goal(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.sub"))
        text += "\n.. goal:: core.sub\n   :parent: core.timing\n\n   Threads stay apart.\n"
        assert findings(text) == []

    def test_the_parents_are_the_entries_of_the_list_without_spaces(self):
        chunk = bcw.Chunk("book/core/core.rst", "core", 1, "REQUIREMENT", "core.x", {"parent": "core.a, core.b,"}, {}, [])
        assert bcw.parents(chunk) == ["core.a", "core.b"]

    def test_a_chain_that_meets_an_unknown_anchor_is_left_to_references(self):
        text = GOOD.replace(CORE, CORE.replace("core.timing", "core.nothing"))
        assert findings(text) == [(line(text, ":parent: core.nothing"), "references", "core.core")]


class DefinitionParentTest:
    """doc.definition-parent"""

    def test_a_definition_with_two_parents_is_a_finding_on_the_option_line(self):
        text = GOOD.replace(TURN, TURN.replace("core.core", "core.core, core.timing"))
        assert findings(text) == [(line(text, ":parent: core.core, core.timing"), "definition-parent",
                                   "core.turn")]

    def test_a_requirement_can_have_two_parents(self):
        text = GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))
        assert findings(text) == []


class CrowdedTest:
    """The count of rules with more than two parents, which is not a finding."""

    def test_a_rule_with_three_parents_is_counted_but_passes(self):
        book = Book({"core/core.rst": GOOD.replace(ROTATION, ROTATION.replace(
            "core.timing", "core.timing, core.core, core.turn"))})
        assert (book.findings, bcw.crowded(book.documents)) == ([], 1)

    def test_two_parents_are_not_counted(self):
        book = Book({"core/core.rst": GOOD.replace(ROTATION, ROTATION.replace("core.timing", "core.timing, core.core"))})
        assert bcw.crowded(book.documents) == 0


class EarsTest:
    """doc.ears"""

    @pytest.mark.parametrize("sentence", [
        "Where a trace exists, while the core runs, when a thread waits, the core shall wait.",
        "While the core runs, the core shall give each turn in order.",
        "If a thread faults, then the core shall not give it a turn.",
        "Each core shall give ``a, b`` to thread *t*.",
        "The Core shall give\n   the turn.",
    ])
    def test_every_clause_in_order_passes(self, sentence):
        assert only("ears", with_requirement(sentence)) == []

    @pytest.mark.parametrize("sentence", ["When a thread waits the core shall wait.",
                                          "When a thread waits, where a trace exists, the core shall wait.",
                                          "If a thread faults, the core shall wait.",
                                          "The core Shall wait.",
                                          "The core shall give these turns:"])
    def test_a_sentence_outside_the_pattern_is_a_finding_on_the_line_of_shall(self, sentence):
        text = with_requirement(sentence)
        assert only("ears", text) == [(line(text, sentence), "ears", "core.rotation")]

    def test_a_clause_without_its_comma_is_a_form_finding_not_an_actor_finding(self):
        book = Book({"core/core.rst": with_requirement("When a thread waits the core shall wait.")})
        assert ([f.message for f in book.findings if f.check == "ears"] ==
                ["the sentence does not have the EARS form"])

    def test_the_finding_is_on_the_line_of_shall(self):
        text = with_requirement("When a thread\n   waits the core shall wait.")
        assert only("ears", text) == [(line(text, "shall wait"), "ears", "core.rotation")]

    @pytest.mark.parametrize("sentence", [
        "Rotation shall be fixed.",
        "The cores shall wait.",
        "A core turn shall wait.",
    ])
    def test_an_actor_that_no_definition_defines_is_a_finding(self, sentence):
        text = with_requirement(sentence)
        assert only("ears", text) == [(line(text, sentence), "ears", "core.rotation")]

    def test_only_the_first_dfn_of_a_definition_defines_a_term(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The core runs the :dfn:`threads` in turn.")
        assert only("ears", text) == [(line(text, "The core shall"), "ears", "core.rotation")]
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The :dfn:`core` runs the :dfn:`threads`.")
        assert only("ears", text) == []

    def test_a_dfn_outside_a_definition_defines_nothing(self):
        text = with_requirement("The zyx shall wait.").replace(
            "A thread's instructions are", "A :dfn:`zyx` has instructions")
        assert only("ears", text) == [(line(text, "The zyx shall"), "ears", "core.rotation")]

    def test_a_definition_without_a_dfn_defines_nothing(self):
        text = GOOD.replace("The :dfn:`core` runs", "The ``core`` runs")
        assert only("ears", text) == [(line(text, "The core shall"), "ears", "core.rotation")]


class LinterTest:
    """doc.linter"""

    def test_a_semicolon_in_a_rule_is_a_finding_on_its_line(self):
        text = GOOD.replace("A :dfn:`turn` is a thread's cycle in the rotation.",
                            "A :dfn:`turn` is a thread's cycle; it is fixed.")
        assert findings(text) == [(line(text, "cycle;"), "linter", "core.turn")]

    def test_a_long_sentence_in_a_rule_is_a_finding(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.",
                            "The :dfn:`core` runs the threads in turn" + " and waits" * 10 + ".")
        assert findings(text) == [(line(text, "The :dfn:`core` runs"), "linter", "core.core")]

    def test_an_advisory_finding_passes(self):
        text = GOOD.replace("The :dfn:`core` runs the threads in turn.", "The :dfn:`core` is built from threads.")
        assert findings(text) == []

    def test_a_semicolon_in_a_goal_is_a_finding_on_its_line(self):
        text = GOOD.replace("the timing of another thread.", "the timing of another thread; it is fixed.")
        assert findings(text) == [(line(text, "thread; it"), "linter", "core.timing")]

    def test_a_chunk_that_is_not_a_rule_or_a_goal_is_not_linted(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart; so it is.")
        assert findings(text) == []

    def test_a_semicolon_in_a_quotation_passes(self):
        text = GOOD.replace("in the rotation.", "in the rotation, ``a; b``.")
        assert findings(text) == []


class VocabularyTest:
    """doc.vocabulary and doc.never-on-definition"""

    NEVER = GOOD.replace(CORE, CORE + "   :never: cpu, slot\n")

    def test_a_definition_with_never_words_passes(self):
        assert findings(self.NEVER) == []

    def test_a_never_word_in_a_rule_is_a_finding_in_any_case(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's CPU cycle")
        assert findings(text) == [(line(text, "CPU cycle"), "vocabulary", "core.turn")]

    def test_a_never_word_in_a_goal_is_a_finding(self):
        text = self.NEVER.replace("the timing of another", "the CPU timing of another")
        assert findings(text) == [(line(text, "CPU timing"), "vocabulary", "core.timing")]

    def test_each_entry_of_the_never_list_counts_at_the_start_of_a_line_too(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's\n   slot cycle")
        assert findings(text) == [(line(text, "slot cycle"), "vocabulary", "core.turn")]

    def test_only_whole_words_count(self):
        text = self.NEVER.replace("is a thread's cycle", "is a thread's slotted cycle")
        assert findings(text) == []

    def test_a_never_word_outside_a_rule_or_in_a_quotation_passes(self):
        text = self.NEVER.replace("eight cycles apart.", "eight cycles apart, not a slot.").replace(
            "in the rotation.", "in the rotation, not a ``slot``.")
        assert findings(text) == []

    @pytest.mark.parametrize("old, new", [(ROTATION, ROTATION + "   :never: cpu\n"),
                                          (".. goal:: core.timing\n", ".. goal:: core.timing\n   :never: cpu\n")])
    def test_never_on_a_chunk_that_is_not_a_definition_is_an_error(self, old, new):
        text = GOOD.replace(old, new)
        book = Book({"core/core.rst": text})
        # The chunk is lost, so the references to its anchor fail too.
        assert ([f for f in book.tuples() if f[2] == "sphinx"] ==
                [("book/core/core.rst", line(text, new.splitlines()[0]), "sphinx", None)])
        assert 'unknown option: "never"' in book.warnings


class OverviewFirstTest:
    """doc.overview-first"""

    def test_a_chunk_in_the_overview_is_a_finding(self):
        text = GOOD.replace("The core runs every thread through one pipeline.",
                            ".. rationale::\n\n   The core runs every thread through one pipeline.")
        assert findings(text) == [(line(text, ".. rationale::"), "overview-first", None)]

    def test_a_chunk_before_the_first_section_is_a_finding(self):
        text = GOOD.replace("====\nCore\n====\n", "====\nCore\n====\n\n.. open:: The title is not settled.\n")
        assert findings(text) == [(line(text, "The title is not settled"), "overview-first", None)]

    def test_a_third_level_section_does_not_end_the_overview(self):
        text = GOOD.replace("Rotation\n========", "Rotation\n--------")
        expected = [(line(text, needle), "overview-first", anchor) for needle, anchor in [
            (".. requirement::", "core.rotation"), (".. rationale::", None), (".. open::", None),
            (".. definition:: core.turn", "core.turn"), (".. definition:: core.core", "core.core")]]
        assert findings(text) == expected


class ArgumentBudgetTest:
    """doc.argument-budget"""

    def test_a_second_argument_in_a_section_with_a_rule_is_a_finding(self):
        text = GOOD.replace(THREAD, THREAD + "\n\n.. discussion::\n\n   Another view.")
        assert findings(text) == [(line(text, ".. discussion::"), "argument-budget", None)]

    def test_an_argument_of_41_words_is_a_finding(self):
        text = GOOD.replace("A thread's instructions are eight cycles apart.", words(41))
        assert findings(text) == [(line(text, ".. rationale::"), "argument-budget", None)]

    def test_an_argument_of_40_words_passes(self):
        assert findings(GOOD.replace("A thread's instructions are eight cycles apart.", words(40))) == []

    def test_a_third_level_section_starts_a_new_section(self):
        text = GOOD.replace(THREAD, THREAD + "\n\nMore\n----\n\n.. discussion::\n\n   Another view.")
        assert findings(text) == []

    def test_a_fifth_level_section_does_not_start_a_section(self):
        text = GOOD.replace(THREAD, THREAD + "\n\nA\n-\n\nB\n~\n\n.. goal:: core.b\n\n   A goal.\n\n"
                                             ".. discussion::\n\n   One.\n\nC\n^\n\n.. discussion::\n\n   Two.")
        assert findings(text) == [(line(text, "Two.") - 2, "argument-budget", None)]

    def test_a_second_argument_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n.. discussion::\n\n   One.\n\n.. discussion::\n\n   Two.\n"
        assert findings(text) == [(line(text, "Two.") - 2, "argument-budget", None)]

    def test_an_argument_of_41_words_in_a_section_with_a_goal_is_a_finding(self):
        text = GOOD + "\n.. rationale::\n\n   " + words(41) + "\n"
        assert findings(text) == [(line(text, "word word") - 2, "argument-budget", None)]

    def test_a_section_without_a_rule_or_a_goal_has_no_budget(self):
        text = GOOD + "\nNotes\n=====\n\n.. discussion::\n\n   One.\n\n.. discussion::\n\n   " + words(50) + "\n"
        assert findings(text) == []


class CodeKindsTest:
    """doc.code-kinds"""

    def with_block(self, block):
        return GOOD.replace(THREAD, THREAD + "\n\n" + block)

    @pytest.mark.parametrize("block, needle", [
        ("Example::\n\n   x = 1\n", "x = 1"),
        (".. code-block:: python\n\n   x = 1\n", ".. code-block"),
    ])
    def test_a_literal_block_is_a_finding_on_the_line_that_docutils_gives(self, block, needle):
        text = self.with_block(block)
        assert findings(text) == [(line(text, needle),
                                   "code-kinds", None)]

    def test_a_block_inside_a_list_item_is_a_finding(self):
        text = self.with_block("- An item::\n\n     x = 1\n")
        assert findings(text) == [(line(text, "x = 1"), "code-kinds", None)]

    def test_a_check_passes(self):
        assert findings(self.with_block(".. check::\n\n   x = 1\n")) == []


class DottedWordsTest:
    """doc.dotted-words"""

    @pytest.mark.parametrize("word", ["Q8.4", "9.09", "v1.2", "e.g.", "i.e.", "a.k.a.", "check.py",
                                      "etc.", "Etc.", "vs.", "cf.", "approx.", "incl.", "esp.", "resp.", "ca.", "Ca."])
    def test_a_dotted_word_in_a_requirement_is_a_finding_on_its_line(self, word):
        text = with_requirement(f"The core shall give\n   the turn, {word} to each thread.")
        assert only("dotted-words", text) == [(line(text, word), "dotted-words", "core.rotation")]

    @pytest.mark.parametrize("word", ["``Q8.4``", "``9.09``", "``e.g.``", "``etc.``"])
    def test_a_quoted_dotted_word_passes(self, word):
        text = with_requirement(f"The core shall give the turn, {word} to each thread.")
        assert only("dotted-words", text) == []

    @pytest.mark.parametrize("sentence", ["The core shall give the turn to thread *t* + 1.",
                                          "The core shall give the turn to each thread, the next one etch.",
                                          "The core shall give the turn to the TVs.",
                                          "The core shall give the turn to Africa."])
    def test_a_full_stop_that_ends_a_sentence_passes(self, sentence):
        assert only("dotted-words", with_requirement(sentence)) == []

    def test_a_dotted_word_outside_a_requirement_passes(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, in Q8.4, e.g. thread 1.")
        assert only("dotted-words", text) == []


class AttributeKeysTest:
    """doc.attribute-keys: docutils rejects an option that the label does not register."""

    def test_an_unknown_option_is_an_error_on_the_directive_line(self):
        text = GOOD.replace(TURN, TURN + "   :colour: red\n")
        book = Book({"core/core.rst": text})
        assert book.tuples() == [("book/core/core.rst", line(text, ".. definition:: core.turn"), "sphinx", None)]
        assert 'unknown option: "colour"' in book.warnings

    def test_the_options_of_each_label_pass(self):
        text = GOOD.replace(TURN, TURN + "   :never: slot\n").replace(ROTATION, ROTATION + "   :impl: none\n")
        assert findings(text) == []

    # A RATIONALE, a DISCUSSION and an OPEN allow no option. Docutils reads an
    # option line under such a directive as text, so the extension rejects it.
    NO_OPTIONS = [(".. rationale::", ".. rationale::"), (".. rationale::", ".. discussion::"),
                  (".. open:: The thread count is not settled.", ".. open:: The thread count is not settled.")]

    def error(self, text, needle):
        """The chunks of text, after a check that text has one error, on the line of needle."""
        book = Book({"core/core.rst": text})
        assert book.tuples() == [("book/core/core.rst", line(text, needle), "sphinx", None)]
        return book

    @pytest.mark.parametrize("old, new", NO_OPTIONS)
    def test_an_option_on_a_label_that_allows_none_is_an_error_on_the_directive_line(self, old, new):
        text = GOOD.replace(old, new + "\n   :parent: core.core")
        book = self.error(text, new)
        assert 'unknown option: "parent"' in book.warnings
        assert "parent" not in " ".join(chunk.english for chunk in book.documents[0].chunks)

    @pytest.mark.parametrize("label", ["rationale", "discussion"])
    def test_an_argument_on_a_label_that_takes_none_is_an_error_on_the_directive_line(self, label):
        text = GOOD.replace(".. rationale::", f".. {label}:: core.why")
        book = self.error(text, f".. {label}:: core.why")
        assert "takes no argument" in book.warnings
        assert "core.why" not in " ".join(chunk.english for chunk in book.documents[0].chunks)

    CHECK = "\n.. check::\n\n   x = 1\n"

    def code(self, book):
        return "\n".join(block.text for block in book.documents[0].blocks)

    def test_an_option_on_a_check_is_an_error_on_the_directive_line(self):
        text = GOOD + self.CHECK.replace(".. check::\n", ".. check::\n   :kind: static\n")
        book = self.error(text, ".. check::")
        assert 'unknown option: "kind"' in book.warnings
        assert "kind" not in self.code(book)

    @pytest.mark.parametrize("old, new", [
        ("   .. twin::\n", "   .. twin:: extra\n"),
        (".. check::", ".. check:: extra"),
    ])
    def test_an_argument_on_a_twin_or_a_check_is_an_error_on_the_directive_line(self, old, new):
        text = (GOOD + self.CHECK).replace(old, new)
        book = self.error(text, new.strip())
        assert f"the {new.split()[1][:-2]} directive takes no argument." in book.warnings
        assert "extra" not in self.code(book)

    def test_the_options_and_argument_of_a_code_directive_pass(self):
        assert findings(GOOD + self.CHECK) == []

    @pytest.mark.parametrize("first", [
        "A thread's instructions are eight cycles apart.",
        ":rule:`core.rotation` gives the order.",
    ])
    def test_text_under_the_directive_line_is_not_an_option(self, first):
        text = GOOD.replace(".. rationale::\n\n   A thread's instructions are eight cycles apart.",
                            f".. rationale::\n   {first}")
        assert text != GOOD
        assert findings(text) == []


class KnownWordsTest:
    """doc.general-word, doc.known-word and doc.known-words"""

    SLOT = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time slot` is a turn of the core.\n"

    def known(self, text, general=GENERAL):
        return only("known-words", text, general=general)

    def test_a_chapter_of_general_words_and_defined_terms_passes(self):
        assert findings(GOOD, general=GENERAL) == []

    @pytest.mark.parametrize("word, needle, anchor", [("timing", "the timing of", "core.timing"),
                                                      ("give", "shall give", "core.rotation"),
                                                      ("cycle", "A :dfn:`turn`", "core.turn"),
                                                      ("runs", "The :dfn:`core`", "core.core")])
    def test_an_unknown_word_in_a_goal_or_a_rule_is_a_finding_on_its_line(self, word, needle, anchor):
        assert self.known(GOOD, GENERAL - {word}) == [(line(GOOD, needle), "known-words", anchor)]

    def test_each_unknown_word_is_a_finding(self):
        text = GOOD.replace("the timing of", "the zyx timing wvu of")
        assert self.known(text) == [(line(text, "zyx"), "known-words", "core.timing")] * 2

    def test_the_finding_is_on_the_line_of_the_word(self):
        assert (self.known(GOOD, GENERAL - {"t"}) ==
                [(line(GOOD, "thread *t* to"), "known-words", "core.rotation")] * 2)

    @pytest.mark.parametrize("old, new", [("eight cycles apart.", "eight zyx cycles apart."),
                                          ("The thread count is", "The zyx thread count is"),
                                          ("is prose.", "is zyx prose."),
                                          ("Rotation\n========", "Zyx\n========")])
    def test_a_word_outside_a_goal_or_a_rule_passes(self, old, new):
        assert self.known(GOOD.replace(old, new)) == []

    @pytest.mark.parametrize("quoted", ["``zyx``", ":rule:`core.core`"])
    def test_a_word_in_a_quotation_passes(self, quoted):
        assert self.known(GOOD.replace("the timing of", f"the {quoted} timing of")) == []

    def test_case_does_not_matter(self):
        assert self.known(GOOD.replace("the timing of", "the TIMING of")) == []

    def test_a_defined_term_needs_no_listing(self):
        assert self.known(GOOD, GENERAL | {"turn", "core"}) == []
        assert self.known(GOOD.replace("the timing of", "the core of")) == []

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        assert self.known(GOOD.replace("A :dfn:`turn` is", "A :dfn:`Turn` is")) == []

    def test_the_endings_of_english_plurals_and_of_apostrophe_s_keep_a_word_known(self):
        text = GOOD.replace("the timing of", "the timings, core's, core’s, turns, boxes, matches, entries of")
        assert self.known(text, GENERAL | {"box", "match", "entry"}) == []

    @pytest.mark.parametrize("word", ["timingly", "cored", "turner", "thready", "toes", "turnes", "boxs", "timingies"])
    def test_other_endings_do_not(self, word):
        text = GOOD.replace("the timing of", f"the {word} of")
        # box is listed, so that boxs fails for its ending alone.
        assert (self.known(text, GENERAL | {"box"}) ==
                [(line(text, word), "known-words", "core.timing")])

    def test_the_list_needs_only_the_base_of_a_plural_in_ies(self):
        text = GOOD.replace("No thread can change the timing of another thread.",
                            "No thread satisfies the timing of another thread.")
        assert self.known(text, GENERAL | {"satisfy"}) == []

    @pytest.mark.parametrize("sentence, unknown", [
        ("The core shall give the time slot to thread ``t``.", []),
        ("The core shall give the time slots to thread ``t``.", []),
        ("The core shall give the time\n   slot to thread ``t``.", []),
        ("The core shall give the slot to thread ``t``.", ["slot"]),
        ("The core shall give the time to thread ``t``.", ["time"]),
        ("The core shall give the times slot to thread ``t``.", ["times", "slot"]),
    ])
    def test_a_word_of_a_defined_term_is_known_only_inside_the_whole_term(self, sentence, unknown):
        text = self.SLOT.replace(SENTENCE, sentence)
        assert self.known(text) == ([(line(text, "The core shall"), "known-words", "core.rotation")]
                  * len(unknown))

    def test_the_longest_defined_term_wins(self):
        text = self.SLOT + "\n.. definition:: core.time\n   :parent: core.core\n\n   A :dfn:`time` is a zyx.\n"
        assert self.known(text, GENERAL | {"zyx"}) == []
        text = text.replace(SENTENCE, "The core shall give the time slot of the time to thread ``t``.")
        assert self.known(text, GENERAL | {"zyx"}) == []

    def test_the_list_is_read_in_lower_case_and_without_comments(self, tmp_path):
        assert self.known(GOOD, GENERAL - {"the"} | {"THE"}) == []
        path = tmp_path / "words.txt"
        path.write_text("# a comment\nthe\n\n  cycle  \n")
        assert bcw.listed(path) == {"the", "cycle"}

    def test_a_missing_list_is_an_empty_list(self):
        assert bcw.listed("/nonexistent/general-words.txt") == set()


class GeneralWordsTest:
    """doc.general-words"""

    SLOT = KnownWordsTest.SLOT

    def general(self, text, extra):
        return only("general-words", text, general=GENERAL | extra)

    @pytest.mark.parametrize("word", ["turn", "turns", "turn's"])
    def test_a_listed_defined_term_is_a_finding_on_its_definition(self, word):
        assert (self.general(GOOD, {word}) ==
                [(line(GOOD, ".. definition:: core.turn"), "general-words", "core.turn")])

    def test_a_listed_word_that_is_no_form_of_a_defined_term_passes(self):
        assert self.general(GOOD, {"turnes"}) == []

    def test_each_listed_form_is_a_finding(self):
        assert (self.general(GOOD, {"turn", "turns"}) ==
                [(line(GOOD, ".. definition:: core.turn"), "general-words", "core.turn")] * 2)

    @pytest.mark.parametrize("word", ["time slot", "time slots"])
    def test_a_listed_multi_word_term_is_a_finding(self, word):
        assert (self.general(self.SLOT, {word}) ==
                [(line(self.SLOT, ".. definition:: core.slot"), "general-words", "core.slot")])

    def test_a_defined_term_in_upper_case_matches_in_any_case(self):
        text = GOOD.replace("A :dfn:`turn` is", "A :dfn:`Turn` is")
        assert (self.general(text, {"turn"}) ==
                [(line(text, ".. definition:: core.turn"), "general-words", "core.turn")])

    def test_one_word_of_a_multi_word_term_passes(self):
        assert self.general(self.SLOT, {"time", "slot"}) == []

    def test_a_word_that_only_starts_like_a_defined_term_passes(self):
        assert self.general(GOOD, {"turner", "cored", "turnstile"}) == []


class QuotationAcrossLinesTest:
    """doc.quotation: a quotation that runs across a line break is still a quotation."""

    def test_known_words_skip_a_literal_across_a_line_break(self):
        text = GOOD.replace("in the rotation.", "in the ``zyx\n   wvu`` rotation.")
        assert only("known-words", text, general=GENERAL) == []

    def test_a_dfn_across_a_line_break_is_one_defined_term(self):
        text = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time\n   slot` is a turn of the core.\n"
        assert only("known-words", text, general=GENERAL) == []
        assert "time slot" in [chunk.term for chunk in Book({"core/core.rst": text}).documents[0].chunks]

    def test_the_vocabulary_skips_a_literal_across_a_line_break(self):
        text = VocabularyTest.NEVER.replace("is a thread's cycle", "is a thread's ``cpu\n   slot`` cycle")
        assert only("vocabulary", text) == []

    def test_one_shall_skips_a_literal_across_a_line_break(self):
        text = with_requirement("The core shall give the turn, not ``the\n   shall``, to each thread.")
        assert only("one-shall", text) == []

    def test_dotted_words_skip_a_literal_across_a_line_break(self):
        text = with_requirement("The core shall give the turn, ``see\n   Q8.4``, to each thread.")
        assert only("dotted-words", text) == []

    def test_the_linter_skips_a_literal_across_a_line_break(self):
        text = GOOD.replace("in the rotation.", "in the rotation, ``a;\n   b``.")
        assert only("linter", text) == []

    def test_ears_skips_a_literal_across_a_line_break(self):
        text = with_requirement("Each core shall give ``a,\n   b`` to thread *t*.")
        assert only("ears", text) == []

    def test_a_word_after_the_literal_keeps_its_own_line(self):
        text = GOOD.replace("in the rotation.", "in the ``x\n   y`` qqq rotation.")
        assert only("known-words", text, general=GENERAL) == [(line(text, "qqq"), "known-words", "core.turn")]


class ChapterPathTest:
    """doc.chapter and doc.chapter-path"""

    def test_a_chapter_at_book_name_name_rst_passes(self):
        assert Book({"core/core.rst": GOOD}).tuples() == []

    @pytest.mark.parametrize("relative", ["core/x.rst", "x.rst", "core/sub/sub.rst"])
    def test_a_chapter_at_another_path_is_a_finding_on_line_1(self, relative):
        assert ([f for f in Book({relative: GOOD}).tuples() if f[2] == "chapter-path"] ==
                [("book/" + relative, 1, "chapter-path", None)])


class ChapterTitleTest:
    """doc.chapter-title"""

    def test_a_chapter_without_a_title_is_a_finding_on_line_1(self):
        text = ":kind: reference\n\nJust text.\n"
        assert only("chapter-title", text) == [(1, "chapter-title", None), (3, "chapter-title", None)]

    def test_a_second_title_is_a_finding_on_its_line(self):
        text = GOOD + "\n====\nMore\n====\n\nText.\n"
        assert only("chapter-title", text) == [(line(text, "More"), "chapter-title", None)]

    def test_text_before_the_title_is_a_finding_on_its_line(self):
        text = GOOD.replace(":kind: reference\n\n", ":kind: reference\n\nIntro.\n\n")
        assert only("chapter-title", text) == [(line(text, "Intro."), "chapter-title", None)]


class ChapterKindTest:
    """doc.chapter-kind"""

    @pytest.mark.parametrize("kind", ["tutorial", "how-to", "reference", "explanation"])
    def test_each_kind_passes(self, kind):
        assert only("chapter-kind", GOOD.replace(":kind: reference", f":kind: {kind}")) == []

    @pytest.mark.parametrize("text", [
        GOOD.replace(":kind: reference\n\n", ""),
        GOOD.replace(":kind: reference", ":kind: guide"),
    ])
    def test_a_missing_or_unknown_kind_is_a_finding_on_line_1(self, text):
        assert only("chapter-kind", text) == [(1, "chapter-kind", None)]


class HeadingNumbersTest:
    """doc.heading-numbers"""

    @pytest.mark.parametrize("old, new", [("Rotation\n========", "2. Rotation\n==========="),
                                          ("Rotation\n========", "4.2 Legs\n========"),
                                          ("====\nCore\n====", "======\n1 Core\n======"),
                                          ("Goals\n=====", "3.\n====="), ("Goals\n=====", "12\n====="),
                                          ("Rotation\n========", "2.1 rotation\n============")])
    def test_a_numbered_heading_is_a_finding_on_its_line(self, old, new):
        text = GOOD.replace(old, new)
        title = [part for part in new.splitlines() if not set(part) <= {"="}][0]
        assert only("heading-numbers", text) == [(line(text, title), "heading-numbers", None)]

    @pytest.mark.parametrize("new", [
        "Rotation 2\n==========",
        "64-bit counters\n===============",
        "v2 rotation\n===========",
        "8 threads\n=========",
        "2 cycles apart\n==============",
    ])
    def test_a_heading_that_starts_with_a_word_a_compound_or_a_count_passes(self, new):
        assert only("heading-numbers", GOOD.replace("Rotation\n========", new)) == []


class AnchorPrefixTest:
    """doc.anchor-prefix"""

    def test_an_anchor_of_another_chapter_is_a_finding_on_the_directive_line(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition:: bank.turn")
        assert findings(text) == [(line(text, "bank.turn"), "anchor-prefix", "bank.turn")]

    def test_a_goal_is_covered(self):
        text = GOOD.replace(".. goal:: core.timing", ".. goal:: design.timing")
        assert only("anchor-prefix", text) == [(line(text, "design.timing"), "anchor-prefix", "design.timing")]

    def test_the_prefix_is_the_file_name(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition:: cor.turn")
        assert ([f for f in Book({"core/core.rst": text}).tuples() if f[2] == "anchor-prefix"] ==
                [("book/core/core.rst", line(text, "cor.turn"), "anchor-prefix", "cor.turn")])
        assert [f for f in Book({"x/core.rst": GOOD}).tuples() if f[2] == "anchor-prefix"] == []


def order(chapters):
    return bcw.chapter_order(Book(chapters).documents)


class ChapterOrderTest:
    """doc.chapter-order and doc.chapters-ordered"""

    def test_a_chapter_comes_after_the_chapters_of_its_parents(self):
        chapters = {"core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN}
        assert order(chapters) == (["design", "core"], [])
        assert Book(chapters).tuples() == []

    def test_ties_go_in_alphabetical_order(self):
        assert order({"b/b.rst": chapter("B"), "a/a.rst": chapter("A")}) == (["a", "b"], [])

    def test_the_first_free_name_goes_next(self):
        chapters = {"doc/doc.rst": chapter("Doc"), "core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN}
        assert order(chapters) == (["design", "core", "doc"], [])

    def test_a_parent_in_the_same_chapter_adds_no_edge(self):
        assert order({"core/core.rst": GOOD}) == (["core"], [])

    def test_a_cycle_of_chapters_is_a_finding_on_line_1_of_each(self):
        cycle = DESIGN + "\n.. definition:: design.zyx\n   :parent: core.core\n\n   A :dfn:`zyx` is a thing.\n"
        chapters = {"core/core.rst": CORE_CHAPTER, "design/design.rst": cycle, "a/a.rst": chapter("A")}
        assert order(chapters) == (["a"], ["core", "design"])
        assert ([f for f in Book(chapters).tuples() if f[2] == "chapters-ordered"] ==
                [("book/core/core.rst", 1, "chapters-ordered", None),
                 ("book/design/design.rst", 1, "chapters-ordered", None)])

    def test_an_unknown_parent_adds_no_edge(self):
        text = CORE_CHAPTER.replace(TURN, TURN.replace("core.core", "gone.x"))
        assert order({"core/core.rst": text, "design/design.rst": DESIGN}) == (["design", "core"], [])

    def test_the_kinds_come_in_order_before_the_trace(self):
        chapters = {"a/a.rst": chapter("A", "explanation"), "b/b.rst": chapter("B", "reference"),
                    "c/c.rst": chapter("C", "how-to"), "d/d.rst": chapter("D", "tutorial")}
        assert order(chapters) == (["d", "c", "b", "a"], [])

    def test_a_parent_in_another_kind_adds_no_edge(self):
        chapters = {"core/core.rst": CORE_CHAPTER.replace(":kind: reference", ":kind: tutorial"),
                    "design/design.rst": DESIGN}
        assert order(chapters) == (["core", "design"], [])


class CitationLinkTest:
    """A citation links to the chunk that carries its anchor."""

    CITING = CORE_CHAPTER.replace("eight cycles apart.",
                                  "eight cycles apart, as :rule:`design.timing` and :rule:`core.turn` say.")

    def references(self, book, docname):
        return [(node.get("refuri"), node.get("refid"), node.astext())
                for node in book.resolved[docname].findall(nodes.reference)]

    def test_each_citation_resolves_to_its_anchor(self):
        book = Book({"core/core.rst": self.CITING, "design/design.rst": DESIGN})
        assert book.tuples() == []
        assert self.references(book, "core/core") == [("#design.timing", None, "design.timing"),
                                                      (None, "core.turn", "core.turn")]

    def test_each_anchored_chunk_carries_its_anchor_as_its_id(self):
        book = Book({"core/core.rst": GOOD})
        ids = [node["ids"] for node in book.resolved["core/core"].findall(bcw.chunk)]
        assert ids == [["core.rotation"], [], [], ["core.turn"], ["core.core"], ["core.timing"]]

    def test_the_checks_still_read_the_citation_as_a_quotation(self):
        book = Book({"core/core.rst": self.CITING, "design/design.rst": DESIGN}, general=GENERAL | {"eight",
                    "cycles", "apart", "as", "and", "say"})
        assert [f for f in book.tuples() if f[2] == "known-words"] == []


class ParameterValuesTest:
    """doc.parameter-value and doc.parameter-values"""

    def test_a_literal_and_a_derived_value_evaluate(self):
        book = Book({"core/core.rst": GOOD + THREADS + WIDTH})
        assert book.tuples() == []
        assert book.values == {"core.threads": 8, "core.turn-width": 3}

    @pytest.mark.parametrize("value, result", [("core.threads // 3 + core.threads % 3 + 2 ** 2", 8),
                                               ("min(core.threads, 4) * 2 - 1", 7), ("max(1, 2, core.threads)", 8),
                                               ("(core.threads - 1) * -1", -7), ("clog2(1)", 0), ("clog2(5)", 3),
                                               ("clog2(8)", 3), ("clog2(9)", 4)])
    def test_each_operator_and_function(self, value, result):
        book = Book({"core/core.rst": GOOD + THREADS + parameter("core.x", value)})
        assert (book.tuples(), book.values["core.x"]) == ([], result)

    @pytest.mark.parametrize("value", ["8 +", "core.nothing", "core.core", "8 / 2", "8 << 1", "abs(8)", "x", "2 ** -1",
                                       "core.threads.x", "'8'", "1 // 0", "min()", "2 ** 2000"])
    def test_a_value_that_does_not_evaluate_is_a_finding_on_its_value_line(self, value):
        text = GOOD + THREADS + parameter("core.x", value)
        book = Book({"core/core.rst": text})
        assert ([f for f in book.tuples() if f[2] != "references"] ==
                [("book/core/core.rst", line(text, f":value: {value}"), "parameter-values", "core.x")])
        assert "core.x" not in book.values

    def test_a_missing_value_is_a_finding_on_the_directive_line(self):
        text = GOOD + parameter("core.x", None)
        assert only("parameter-values", text) == [(line(text, ".. parameter:: core.x"), "parameter-values",
                                                   "core.x")]

    def test_a_cycle_is_a_finding_on_each_value_in_it(self):
        text = GOOD + parameter("core.a", "core.b + 1") + parameter("core.b", "core.a")
        assert (only("parameter-values", text) ==
                [(line(text, ":value: core.b + 1"), "parameter-values", "core.a"),
                 (line(text, ":value: core.a"), "parameter-values", "core.b")])

    def test_a_value_that_names_a_value_that_fails_is_a_finding(self):
        text = GOOD + parameter("core.a", "8 +") + parameter("core.b", "core.a")
        assert (only("parameter-values", text) ==
                [(line(text, ":value: 8 +"), "parameter-values", "core.a"),
                 (line(text, ":value: core.a"), "parameter-values", "core.b")])
        assert "core.a" in [f.message for f in Book({"core/core.rst": text}).findings
                            if f.anchor == "core.b"][0]

    def test_a_value_can_name_a_parameter_of_another_chapter(self):
        design = DESIGN + "\n.. parameter:: design.threads\n   :parent: design.timing\n   :value: 8\n\n   Text.\n"
        core = CORE_CHAPTER + parameter("core.x", "design.threads * 2", parent="core.core")
        assert Book({"core/core.rst": core, "design/design.rst": design}).values["core.x"] == 16


class ConstantNamesTest:
    """doc.constant-name and doc.constant-names"""

    def test_the_constant_name_is_the_anchor_in_upper_case_with_underscores(self):
        assert bcw.constant_name("core.turn-width") == "CORE_TURN_WIDTH"

    def test_two_parameters_with_one_constant_name_are_a_finding(self):
        text = GOOD + parameter("core.turn-width", "3") + parameter("core.turn.width", "3")
        assert (only("constant-names", text) ==
                [(line(text, ".. parameter:: core.turn.width"), "constant-names", "core.turn.width")])


class ParamCitationTest:
    """doc.citation and doc.param-citations"""

    def test_a_param_citation_of_a_parameter_passes(self):
        text = (GOOD + THREADS).replace("eight cycles apart.", "eight cycles apart, of :param:`core.threads`.")
        assert findings(text) == []

    def test_a_param_citation_of_another_chunk_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :param:`core.core` says.")
        assert findings(text) == [(line(text, ":param:"), "param-citations", None)]

    def test_a_param_citation_of_no_anchor_is_a_references_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, as :param:`core.gone` says.")
        assert findings(text) == [(line(text, ":param:"), "references", None)]

    def test_the_word_checks_read_it_as_a_quotation(self):
        text = (GOOD + THREADS).replace("the timing of another", "the timing of :param:`core.threads` another")
        assert only("known-words", text, general=GENERAL | {"number", "threads"}) == []


class ParameterTangleTest:
    """The tangle writes each PARAMETER as a constant in a SystemVerilog package and a Python module."""

    def test_each_constant_follows_a_marker_that_names_its_value_line(self):
        text = GOOD + THREADS + WIDTH
        files = Book({"core/core.rst": text}, tangle=True).files
        threads, width = line(text, ":value: 8"), line(text, ":value: clog2")
        assert (files["build/rtl/bcw_params.sv"] ==
                ("// The PARAMETERs of the book, which tools/bcw.py writes.\n"
                 "package bcw_params;\n"
                 "/* verilator lint_off UNUSEDPARAM */\n"
                 f"// bcw: book/core/core.rst:{threads}\nlocalparam int CORE_THREADS = 8;\n"
                 f"// bcw: book/core/core.rst:{width}\nlocalparam int CORE_TURN_WIDTH = 3;\n"
                 "/* verilator lint_on UNUSEDPARAM */\n"
                 "endpackage\n"))
        assert (files["build/model/bcw_params.py"] ==
                ("# The PARAMETERs of the book, which tools/bcw.py writes.\n"
                 f"# bcw: book/core/core.rst:{threads}\nCORE_THREADS = 8\n"
                 f"# bcw: book/core/core.rst:{width}\nCORE_TURN_WIDTH = 3\n"))

    def test_the_line_mapper_maps_a_constant_to_its_value_line(self, tmp_path):
        text = GOOD + THREADS
        files = Book({"core/core.rst": text}, tangle=True).files
        path = tmp_path / "bcw_params.sv"
        path.write_text(files["build/rtl/bcw_params.sv"])
        assert linemap.lookup(str(path), 5) == ("book/core/core.rst", line(text, ":value: 8"))

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
        assert self.lint(self.COUNT.format("")) == (0, "")

    def test_an_unused_parameter_of_a_module_still_fails_the_lint(self):
        status, messages = self.lint(self.COUNT.format("    localparam int SPARE = 1;\n"))
        assert status != 0
        assert "Parameter is not used: 'SPARE'" in messages


class TargetTest:
    """doc.target-values, doc.target-parents, and the rules that a TARGET shares with the rules"""

    def test_a_target_with_its_options_passes_and_its_value_can_derive_from_a_parameter(self):
        book = Book({"core/core.rst": GOOD + THREADS + target("core.aim", "core.threads * 2", "core.threads",
                                                             "threads")})
        assert book.tuples() == []
        assert book.values["core.aim"] == 16

    def test_a_target_without_an_anchor_is_an_error_on_its_line(self):
        text = GOOD + "\n.. target::\n\n   The number of threads.\n"
        book = Book({"core/core.rst": text})
        assert ([(path, number) for path, number, _ in book.others()] ==
                [("book/core/core.rst", line(text, ".. target::"))])
        assert "1 argument(s) required, 0 supplied" in book.warnings

    def test_a_target_without_a_value_is_a_finding_on_the_directive_line(self):
        text = GOOD + target("core.aim", None)
        assert findings(text) == [(line(text, ".. target:: core.aim"), "target-values", "core.aim")]

    def test_a_target_value_that_names_a_target_is_a_finding(self):
        text = GOOD + target("core.aim", "8") + target("core.other", "core.aim + 1")
        book = Book({"core/core.rst": text})
        assert book.tuples() == [("book/core/core.rst", line(text, ":value: core.aim + 1"), "target-values",
                                  "core.other")]
        assert "core.aim is a TARGET" in book.findings[0].message

    def test_a_parameter_value_that_names_a_target_is_a_finding(self):
        text = GOOD + target("core.aim", "8") + parameter("core.x", "core.aim")
        book = Book({"core/core.rst": text})
        assert book.tuples() == [("book/core/core.rst", line(text, ":value: core.aim"), "parameter-values",
                                  "core.x")]
        assert "core.aim is a TARGET" in book.findings[0].message
        assert "core.x" not in book.values

    @pytest.mark.parametrize("parents", ["core.aim", "core.core, core.aim"])
    def test_a_parent_that_names_a_target_is_a_finding_on_the_parent_line(self, parents):
        text = GOOD + target("core.aim", "8") + parameter("core.x", "1", parent=parents)
        assert findings(text) == [(line(text, f":parent: {parents}"), "target-parents", "core.x")]

    def test_a_target_without_a_parent_does_not_reach_a_goal(self):
        text = GOOD + target("core.aim", "8", parent=None)
        assert findings(text) == [(line(text, ".. target:: core.aim"), "reaches-goal", "core.aim")]

    def test_the_word_checks_read_a_target(self):
        text = GOOD + target("core.aim", "8", text="The aim of the threads.")
        assert (only("known-words", text, general=GENERAL | {"the", "of"}) ==
                [(line(text, "The aim of"), "known-words", "core.aim")])

    def test_a_param_citation_of_a_target_passes(self):
        text = (GOOD + target("core.aim", "8")).replace("eight cycles apart.", "eight cycles apart, of :param:`core.aim`.")
        assert findings(text) == []

    @pytest.mark.parametrize("path", ["build/rtl/bcw_params.sv", "build/model/bcw_params.py"])
    def test_the_tangle_writes_no_target(self, path):
        text = GOOD + THREADS + target("core.aim", "8") + target("core.threads-aim", "core.threads")
        book = Book({"core/core.rst": text}, tangle=True)
        assert book.tuples() == []
        assert "CORE_THREADS" in book.files[path]
        assert "AIM" not in book.files[path]

    def test_a_target_shares_no_constant_name_with_a_parameter(self):
        text = GOOD + parameter("core.turn-width", "3") + target("core.turn.width", "3")
        assert findings(text) == []


def source(target, *code):
    """A source directive to add at the end of GOOD, with each line of code indented under it."""
    return f"\n.. source:: {target}\n\n" + "".join(f"   {line}\n" for line in code)


SKELETON = source("build/rtl/core/pair.v", "module pair (input wire a, output wire b);", "    <<:core.pair-logic>>",
                  "endmodule")
FRAGMENT = source(":core.pair-logic", "assign b = a;")


class FragmentTest:
    """doc.source-targets, doc.fragment-uses, doc.fragments-used and doc.fragment-cycles"""

    def test_a_skeleton_and_its_fragment_pass(self):
        assert findings(GOOD + SKELETON + FRAGMENT) == []

    def test_a_fragment_can_come_before_its_use(self):
        assert findings(GOOD + FRAGMENT + SKELETON) == []

    def test_a_use_of_no_fragment_is_a_finding_on_its_line(self):
        text = GOOD + SKELETON
        assert findings(text) == [(line(text, "<<:core.pair-logic>>"), "fragment-uses", None)]

    def test_a_fragment_that_reaches_no_file_is_a_finding_on_its_directive_line(self):
        text = GOOD + FRAGMENT
        assert findings(text) == [(line(text, ".. source:: :core.pair-logic"), "fragments-used", None)]

    def test_a_fragment_that_only_a_fragment_that_reaches_no_file_uses_reaches_no_file(self):
        text = GOOD + source(":core.outer", "<<:core.pair-logic>>") + FRAGMENT
        assert findings(text) == [(line(text, ".. source:: :core.outer"), "fragments-used", None),
                                  (line(text, ".. source:: :core.pair-logic"), "fragments-used", None)]

    def test_a_fragment_used_through_another_fragment_passes(self):
        text = (GOOD + SKELETON.replace("<<:core.pair-logic>>", "<<:core.outer>>")
                + source(":core.outer", "<<:core.pair-logic>>") + FRAGMENT)
        assert findings(text) == []

    def test_a_cycle_is_a_finding_on_each_fragment_in_it(self):
        text = (GOOD + SKELETON + source(":core.pair-logic", "<<:core.other>>")
                + source(":core.other", "<<:core.pair-logic>>"))
        assert findings(text) == [(line(text, ".. source:: :core.pair-logic"), "fragment-cycles", None),
                                  (line(text, ".. source:: :core.other"), "fragment-cycles", None)]

    @pytest.mark.parametrize("target", ["rtl/core/pair.v", "src/pair.v", "Core_Pair", "core", "core.pair-logic",
                                        "pair.v", ":Core_Pair"])
    def test_a_target_outside_build_that_is_no_fragment_name_is_a_finding(self, target):
        text = GOOD + source(target, "assign b = a;")
        assert findings(text) == [(line(text, f".. source:: {target}"), "source-targets", None)]

    @pytest.mark.parametrize("code", ["assign b = a << 1;", "assign b = a<<:core.pair-logic>>1;",
                                      "<<:core.pair-logic>> // a comment", "<<Core_Pair>>",
                                      "<<core.pair-logic>>"])
    def test_a_line_that_holds_more_than_a_fragment_name_is_code(self, code):
        assert findings(GOOD + source("build/rtl/core/pair.v", code)) == []

    def test_a_line_in_a_twin_is_code(self):
        text = GOOD.replace("      def core_rotate(turn):\n", "      <<:core.none>>\n      def core_rotate(turn):\n")
        assert text != GOOD
        assert [f for f in findings(text) if f[1].startswith("fragment")] == []


class TangleTest:
    """The tangle writes each file of a twin or a source, with a marker before each block."""

    def test_each_file_holds_its_blocks_after_a_marker_that_names_the_first_line(self):
        files = Book({"core/core.rst": GOOD}, tangle=True).files
        # The constant files are always written, and here they hold no constant.
        assert (files.pop("build/rtl/bcw_params.sv") ==
                ("// The PARAMETERs of the book, which tools/bcw.py writes.\npackage bcw_params;\n"
                 "/* verilator lint_off UNUSEDPARAM */\n/* verilator lint_on UNUSEDPARAM */\nendpackage\n"))
        assert (files.pop("build/model/bcw_params.py") ==
                "# The PARAMETERs of the book, which tools/bcw.py writes.\n")
        assert files == {
    "build/model/core_rotate.py": f"# bcw: book/core/core.rst:{line(GOOD, 'def core_rotate')}\n"
                                  "def core_rotate(turn):\n    return {'next': turn + 1}\n",
    "build/rtl/core/core_rotate.v": f"// bcw: book/core/core.rst:{line(GOOD, 'module core_rotate')}\n"
                                    "module core_rotate (input wire [2:0] turn, output wire [2:0] next);\n"
                                    "    assign next = turn + 3'd1;\nendmodule\n"}

    def test_blocks_of_one_file_join_in_order(self):
        text = GOOD + "\n.. source:: build/rtl/core/core_rotate.v\n\n   // more\n"
        files = Book({"core/core.rst": text}, tangle=True).files
        assert files["build/rtl/core/core_rotate.v"].endswith(
   f"endmodule\n// bcw: book/core/core.rst:{line(text, '// more')}\n// more\n")

    def test_without_a_root_nothing_is_tangled(self):
        assert Book({"core/core.rst": GOOD}).files == {}


class FragmentTangleTest:
    """The tangle puts each fragment in place of its use, with the indentation of the use."""

    def test_a_file_from_a_skeleton_and_fragments_of_two_chapters(self):
        core = GOOD + source("build/rtl/core/pair.v", "module pair (input wire a, output wire b);",
                             "    <<:core.pair-logic>>", "    <<:zeta.more>>", "endmodule") + FRAGMENT
        zeta = chapter("Zeta", body="\nMore\n====\n" + source(":zeta.more", "// one", "// two"))
        files = Book({"core/core.rst": core, "zeta/zeta.rst": zeta}, tangle=True).files
        assert files["build/rtl/core/pair.v"] == (
            f"// bcw: book/core/core.rst:{line(core, 'module pair')}\n"
            "module pair (input wire a, output wire b);\n"
            f"    // bcw: book/core/core.rst:{line(core, 'assign b = a;')}\n"
            "    assign b = a;\n"
            f"    // bcw: book/zeta/zeta.rst:{line(zeta, '// one')}\n"
            "    // one\n"
            "    // two\n"
            f"// bcw: book/core/core.rst:{line(core, 'endmodule', after='<<:zeta.more>>')}\n"
            "endmodule\n")
        assert "core.pair-logic" not in files and "zeta.more" not in files

    def test_the_blocks_of_a_fragment_join_in_order(self):
        text = GOOD + SKELETON + FRAGMENT + source(":core.pair-logic", "assign c = a;")
        tangled = Book({"core/core.rst": text}, tangle=True).files["build/rtl/core/pair.v"]
        assert (f"    // bcw: book/core/core.rst:{line(text, 'assign b = a;')}\n    assign b = a;\n"
                f"    // bcw: book/core/core.rst:{line(text, 'assign c = a;')}\n    assign c = a;\n") in tangled

    def test_a_fragment_inside_a_fragment_adds_its_indentation(self):
        text = (GOOD + SKELETON.replace("<<:core.pair-logic>>", "<<:core.outer>>")
                + source(":core.outer", "begin", "    <<:core.pair-logic>>", "end") + FRAGMENT)
        tangled = Book({"core/core.rst": text}, tangle=True).files["build/rtl/core/pair.v"]
        end = line(text, "end", after="<<:core.pair-logic>>")
        assert (f"    begin\n        // bcw: book/core/core.rst:{line(text, 'assign b = a;')}\n"
                f"        assign b = a;\n    // bcw: book/core/core.rst:{end}\n    end\n") in tangled

    def test_the_indentation_makes_working_python(self):
        text = GOOD + source("build/model/body.py", "def f(x):", "    <<:core.body>>", "", "RESULT = f(1)") + source(
            ":core.body", "y = x + 1", "return y")
        tangled = Book({"core/core.rst": text}, tangle=True).files["build/model/body.py"]
        names = {}
        exec(tangled, names)
        assert names["RESULT"] == 2
        assert f"    # bcw: book/core/core.rst:{line(text, 'y = x + 1')}\n    y = x + 1\n    return y\n" in tangled

    # A line that ends in a backslash goes on in the next line, in Python and in a
    # Verilog macro, so no marker can stand between the two.
    BACKSLASH = {
        "a fragment ends in a backslash": (
            source("build/model/b.py", "def f(x):", "    <<:core.sum>>", "        1", "    return total", "",
                   "RESULT = f(1)") + source(":core.sum", "total = x + \\"), "return total"),
        "an outer line ends in a backslash": (
            source("build/model/b.py", "def f(x):", "    total = x + \\", "    <<:core.one>>", "    return total", "",
                   "RESULT = f(1)") + source(":core.one", "1"), "return total"),
        "a block ends in a backslash": (
            source("build/model/b.py", "RESULT = 1 + \\") + source("build/model/b.py", "    1", "", "SECOND = 2"),
            "SECOND = 2"),
    }

    @pytest.mark.parametrize("case", BACKSLASH)
    def test_no_marker_follows_a_line_that_ends_in_a_backslash(self, case, tmp_path):
        extra, later = self.BACKSLASH[case]
        text = GOOD + extra
        tangled = Book({"core/core.rst": text}, tangle=True).files["build/model/b.py"]
        names = {}
        exec(tangled, names)
        assert names["RESULT"] == 2
        lines = tangled.splitlines()
        assert not any(first.endswith("\\") and "bcw:" in second for first, second in zip(lines, lines[1:])), tangled
        # The first line after the continuation maps to its chapter line again.
        path = tmp_path / "b.py"
        path.write_text(tangled)
        number = next(n for n, content in enumerate(lines, 1) if later in content)
        assert linemap.lookup(str(path), number) == ("book/core/core.rst", line(text, later))

    def test_a_use_of_no_fragment_stays_as_it_is(self):
        tangled = Book({"core/core.rst": GOOD + SKELETON}, tangle=True).files["build/rtl/core/pair.v"]
        assert "    <<:core.pair-logic>>\n" in tangled

    def test_a_cycle_ends_and_leaves_the_repeated_use_as_it_is(self):
        text = (GOOD + SKELETON + source(":core.pair-logic", "<<:core.other>>")
                + source(":core.other", "<<:core.pair-logic>>"))

        def stop(signum, frame):
            raise TimeoutError("the tangle did not end")

        previous = signal.signal(signal.SIGALRM, stop)
        signal.alarm(30)
        try:
            tangled = Book({"core/core.rst": text}, tangle=True).files["build/rtl/core/pair.v"]
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        assert tangled.count("<<:core.pair-logic>>") == 1

