"""Tests of tools/bcw.py that need more than the findings of one chapter.

The cases in tools/tests/cases hold the tests that only compare the findings of a
chapter. The tests here read messages, values, the model, several chapters or the
tangled files, or run a tool.
"""

import hashlib
import json
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from docutils import nodes

import bcw
import linemap
from book import (CORE_CHAPTER, DESIGN, GENERAL, GOOD, STAMP, THREADS, WIDTH, Book, chapter, findings, line,
                  only, parameter, tangled, target)

ROTATION = ".. requirement:: core.rotation\n   :parent: core.timing\n"
IMPLEMENTS = "   :implements: core.rotation\n"
TURN = ".. definition:: core.turn\n   :parent: core.core\n"
CORE = ".. definition:: core.core\n   :parent: core.timing\n"
SENTENCE = "The core shall give the turn after\n   thread *t* to thread *t* + 1."


def with_requirement(sentence):
    return GOOD.replace(SENTENCE, sentence)


def words(count):
    return " ".join(["word"] * (count - 1)) + " end."


class ImplementedTest:
    """doc.implemented"""

    def test_tool_implements_reads_whole_comment_lines_only(self, tmp_path):
        path = tmp_path / "tool.py"
        path.write_text("# implements: doc.a\n    # implements: doc.b\nx = '# implements: doc.c'\n")
        assert bcw.tool_implements([path]) == [(str(path), 1, "doc.a"), (str(path), 2, "doc.b")]


class ReferencesTest:
    """doc.references"""

    def test_a_tool_comment_that_names_no_anchor_is_a_finding(self):
        book = Book({"core/core.rst": GOOD}, tools={"x.py": "\n\n# implements: doc.gone\n"})
        assert book.tuples() == [("tools/x.py", 3, "references", None)]


class ReachesGoalTest:
    """doc.reaches-goal"""

    CYCLE = GOOD.replace(CORE, CORE.replace("core.timing", "core.turn"))

    def test_the_message_names_the_fault(self):
        assert self.messages(self.CYCLE) == ["the chunk reaches itself through its parents"] * 2
        short = GOOD.replace(CORE, ".. definition:: core.core\n")
        assert self.messages(short) == ["the chunk reaches no GOAL through its parents",
                                        "the chunk has no parent"]

    def messages(self, text):
        return [f.message for f in Book({"core/core.rst": text}).findings if f.check == "reaches-goal"]

    def test_the_parents_are_the_entries_of_the_list_without_spaces(self):
        chunk = bcw.Chunk("book/core/core.rst", "core", 1, "REQUIREMENT", "core.x", {"parent": "core.a, core.b,"}, {}, [])
        assert bcw.parents(chunk) == ["core.a", "core.b"]


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

    def test_a_clause_without_its_comma_is_a_form_finding_not_an_actor_finding(self):
        book = Book({"core/core.rst": with_requirement("When a thread waits the core shall wait.")})
        assert ([f.message for f in book.findings if f.check == "ears"] ==
                ["the sentence does not have the EARS form"])


class KnownWordsTest:
    """doc.general-word, doc.known-word and doc.known-words"""

    SLOT = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time slot` is a turn of the core.\n"

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

    def test_a_dfn_across_a_line_break_is_one_defined_term(self):
        text = GOOD + "\n.. definition:: core.slot\n   :parent: core.core\n\n   A :dfn:`time\n   slot` is a turn of the core.\n"
        assert only("known-words", text, general=GENERAL) == []
        assert "time slot" in [chunk.term for chunk in Book({"core/core.rst": text}).documents[0].chunks]


class ChapterPathTest:
    """doc.chapter and doc.chapter-path"""

    def test_a_chapter_at_book_name_name_rst_passes(self):
        assert Book({"core/core.rst": GOOD}).tuples() == []

    @pytest.mark.parametrize("relative", ["core/x.rst", "x.rst", "core/sub/sub.rst"])
    def test_a_chapter_at_another_path_is_a_finding_on_line_1(self, relative):
        assert ([f for f in Book({relative: GOOD}).tuples() if f[2] == "chapter-path"] ==
                [("book/" + relative, 1, "chapter-path", None)])


class AnchorPrefixTest:
    """doc.anchor-prefix"""

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


class ParameterTangleTest:
    """The tangle writes each PARAMETER as a constant in a SystemVerilog package and a Python module."""

    def test_each_constant_maps_to_its_value_line(self):
        text = GOOD + THREADS + WIDTH
        files = Book({"core/core.rst": text}, tangle=True).files
        threads, width = line(text, ":value: 8"), line(text, ":value: clog2")
        assert tangled(files, "build/rtl/bcw_params.sv") == [
            ("// The PARAMETERs of the book, which tools/bcw.py writes.", None, None),
            ("package bcw_params;", None, None),
            ("/* verilator lint_off UNUSEDPARAM */", None, None),
            ("localparam int CORE_THREADS = 8;", CHAPTER, threads),
            ("localparam int CORE_TURN_WIDTH = 3;", CHAPTER, width),
            ("/* verilator lint_on UNUSEDPARAM */", None, None),
            ("endpackage", None, None)]
        # Twins read the constants through tools/twin.py, so no Python file of constants exists.
        assert "build/model/bcw_params.py" not in files

    def test_the_line_mapper_maps_a_constant_to_its_value_line(self, tmp_path):
        text = GOOD + THREADS
        for name, content in Book({"core/core.rst": text}, tangle=True).files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        assert linemap.lookup(str(tmp_path / "build/rtl/bcw_params.sv"), 4) == (CHAPTER, line(text, ":value: 8"))

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

    def test_the_tangle_writes_no_target(self):
        text = GOOD + THREADS + target("core.aim", "8") + target("core.threads-aim", "core.threads")
        book = Book({"core/core.rst": text}, tangle=True)
        assert book.tuples() == []
        assert "CORE_THREADS" in book.files["build/rtl/bcw_params.sv"]
        assert "AIM" not in book.files["build/rtl/bcw_params.sv"]


def source(target, *code):
    """A source directive to add at the end of GOOD, with each line of code indented under it."""
    return f"\n.. source:: {target}\n\n" + "".join(f"   {line}\n" for line in code)


SKELETON = source("build/rtl/core/pair.v", "module pair (input wire a, output wire b);", "    <<:core.pair-logic>>",
                  "endmodule")
FRAGMENT = source(":core.pair-logic", "assign b = a;")
CHAPTER = "book/core/core.rst"


class FragmentTest:
    """doc.source-targets, doc.fragment-uses, doc.fragments-used and doc.fragment-cycles"""

    def test_the_first_block_of_a_fragment_in_the_chapter_order_is_the_fragment(self):
        # A tutorial comes before a reference in the chapter order, so zeta comes before alpha.
        zeta = chapter("Zeta", kind="tutorial", body=source(":core.pair-logic", "// zeta"))
        alpha = chapter("Alpha", body=source(":core.pair-logic", "// alpha"))
        book = Book({"alpha/alpha.rst": alpha, "zeta/zeta.rst": zeta})
        assert book.tuples() == [("book/alpha/alpha.rst", line(alpha, ".. source::"), "one-block", None),
                                 ("book/zeta/zeta.rst", line(zeta, ".. source::"), "fragments-used", None)]
        [finding] = [finding for finding in book.findings if finding.check == "one-block"]
        assert f"book/zeta/zeta.rst:{line(zeta, '.. source::')}" in finding.message

    @pytest.mark.parametrize("use", ["<<:core.none>>", "    <<:core.pair-logic>>"])
    def test_a_fragment_use_in_a_twin_is_a_finding_on_its_line(self, use):
        text = GOOD.replace("      def core_rotate(turn):\n", f"      {use}\n      def core_rotate(turn):\n") + FRAGMENT
        assert text != GOOD + FRAGMENT
        book = Book({"core/core.rst": text})
        # A fragment use is not Python, so it is not in the twin language (doc.twin-forms).
        assert ([f[1:] for f in book.tuples() if f[2] != "fragments-used"] ==
                [(line(text, use), "twin-forms", "core.rotation")])


class OneBlockTest:
    """doc.one-block"""

    def test_the_finding_names_the_first_block(self):
        text = GOOD + SKELETON + FRAGMENT + source(":core.pair-logic", "assign c = a;")
        [finding] = Book({"core/core.rst": text}).findings
        first = line(text, ".. source:: :core.pair-logic")
        assert finding.message == f":core.pair-logic already has a code block, at book/core/core.rst:{first}"

    @pytest.mark.parametrize("extra, path, code", [
        (SKELETON + FRAGMENT + source(":core.pair-logic", "assign c = a;"), "build/rtl/core/pair.v",
         ["module pair (input wire a, output wire b);", "    assign b = a;", "endmodule"]),
        (source("build/rtl/core/core_rotate.v", "// more"), "build/rtl/core/core_rotate.v",
         ["module core_rotate (input wire [2:0] turn, output wire [2:0] next);", "    assign next = turn + 3'd1;",
          "endmodule"]),
    ], ids=["a fragment", "a file"])
    def test_the_tangle_writes_the_first_block_only(self, extra, path, code):
        lines = tangled(Book({"core/core.rst": GOOD + extra}, tangle=True).files, path)
        assert [text for text, _, _ in lines] == code


class ParseErrorTest:
    """doc.labels and doc.attribute-keys: if docutils cannot read a directive, the error is its only finding.

    No check runs on a book with such an error, and the tangle writes nothing, so no
    finding can follow from a directive that docutils left out.
    """

    CHECK = "\n.. check:: test\n   :verifies: core.rotation\n\n   x = 1\n"
    # (old text, new text, the line of the error, a part of its message). Without old text,
    # the new text goes after GOOD.
    CASES = {
        "an unknown label": (".. rationale::", ".. reason::", ".. reason::", 'Unknown directive type "reason".'),
        "a rule without its anchor": (".. definition:: core.turn", ".. definition::", ".. definition::",
                                      "1 argument(s) required, 0 supplied"),
        "a goal without its anchor": (".. goal:: core.timing", ".. goal::", ".. goal::", "1 argument(s) required"),
        "a target without its anchor": (None, "\n.. target::\n\n   The number of threads.\n", ".. target::",
                                        "1 argument(s) required"),
        "an extra word in an anchor": (".. goal:: core.timing\n", ".. goal:: core.timing extra\n", ".. goal::",
                                       "maximum 1 argument(s) allowed"),
        "an unknown option on a goal": (".. goal:: core.timing\n", ".. goal:: core.timing\n   :never: cpu\n",
                                        ".. goal::", 'unknown option: "never"'),
        "an unknown option on a requirement": (ROTATION, ROTATION + "   :never: cpu\n", ".. requirement::",
                                               'unknown option: "never"'),
        "an unknown option on a definition": (TURN, TURN + "   :colour: red\n", ".. definition:: core.turn",
                                              'unknown option: "colour"'),
        "a repeated option": (ROTATION, ROTATION + "   :parent: core.core\n", ".. requirement::", "duplicate option"),
        "text right under the options": (CORE + "\n   The :dfn:`core`", CORE + "   The :dfn:`core`",
                                         ".. definition:: core.core", "invalid option block"),
        "an option on a rationale": (".. rationale::", ".. rationale::\n   :parent: core.core", ".. rationale::",
                                     'unknown option: "parent"'),
        "an option on a discussion": (".. rationale::", ".. discussion::\n   :parent: core.core", ".. discussion::",
                                      'unknown option: "parent"'),
        "an option on an open": (".. open:: The thread count is not settled.",
                                 ".. open:: The thread count is not settled.\n   :parent: core.core", ".. open::",
                                 'unknown option: "parent"'),
        "an argument on a rationale": (".. rationale::", ".. rationale:: core.why", ".. rationale::",
                                       "the rationale directive takes no argument."),
        "an argument on a discussion": (".. rationale::", ".. discussion:: core.why", ".. discussion::",
                                        "the discussion directive takes no argument."),
        "an option on a check": (None, CHECK.replace("   :verifies:", "   :kind: static\n   :verifies:"),
                                 ".. check:: test", 'unknown option: "kind"'),
        "a check without its kind": (".. check:: equiv\n", ".. check::\n", ".. check::",
                                     "1 argument(s) required, 0 supplied"),
        "an argument on a twin": ("   .. twin::\n", "   .. twin:: extra\n", ".. twin::",
                                  "the twin directive takes no argument."),
        "an unknown option on a twin": (f"      :stamp: {STAMP}\n", f"      :stamp: {STAMP}\n      :colour: red\n",
                                        ".. twin::", 'unknown option: "colour"'),
        "an unknown option on a source": (IMPLEMENTS, IMPLEMENTS + "   :colour: red\n", ".. source::",
                                          'unknown option: "colour"'),
        "an extra word on a source": (".. source:: build/rtl/core/core_rotate.v\n",
                                      ".. source:: build/rtl/core/core_rotate.v extra\n", ".. source::",
                                      "maximum 1 argument(s) allowed"),
        "an extra word on a fragment": (None, SKELETON + source(":core.pair-logic extra", "assign b = a;"),
                                        ".. source:: :core.pair-logic", "maximum 1 argument(s) allowed"),
        "a repeated option on a parameter": (None, THREADS.replace("   :unit: threads", "   :unit: threads\n"
                                                                   "   :unit: threads") + WIDTH,
                                             ".. parameter:: core.threads", "duplicate option"),
        "a fragment inside a failed goal": (None, SKELETON + "\n.. goal:: core.aim extra\n\n   No aim.\n\n"
                                            "   .. source:: :core.pair-logic\n\n      assign b = a;\n",
                                            ".. goal:: core.aim", "maximum 1 argument(s) allowed"),
    }

    @pytest.mark.parametrize("case", CASES)
    def test_the_error_is_the_only_finding_and_the_tangle_writes_nothing(self, case):
        old, new, error, message = self.CASES[case]
        text = GOOD + new if old is None else GOOD.replace(old, new)
        assert text != GOOD
        book = Book({"core/core.rst": text}, GENERAL, tangle=True)
        assert book.tuples() == [("", None, "sphinx", None), ("book/core/core.rst", line(text, error), "sphinx", None)]
        assert message in book.warnings
        assert "bcw: 1 error in the chapters, so no check ran: correct the errors first" in book.warnings
        assert book.files == {}

    def test_the_stop_counts_every_error(self):
        text = GOOD.replace(".. rationale::", ".. reason::").replace(TURN, TURN + "   :colour: red\n")
        book = Book({"core/core.rst": text})
        assert "bcw: 2 errors in the chapters, so no check ran" in book.warnings
        assert book.tuples() == [("", None, "sphinx", None), ("book/core/core.rst", line(text, ".. reason::"), "sphinx", None),
                                 ("book/core/core.rst", line(text, ".. definition:: core.turn"), "sphinx", None)]


class TangleTest:
    """The tangle writes each file of a twin or a source, and the chapter line of each of its lines."""

    def test_each_file_holds_its_code_and_each_line_maps_to_its_chapter_line(self):
        files = Book({"core/core.rst": GOOD}, tangle=True).files
        # The constant file is always written, and here it holds no constant.
        assert (files["build/rtl/bcw_params.sv"] ==
                ("// The PARAMETERs of the book, which tools/bcw.py writes.\npackage bcw_params;\n"
                 "/* verilator lint_off UNUSEDPARAM */\n/* verilator lint_on UNUSEDPARAM */\nendpackage\n"))
        assert sorted(files) == ["build/checks.json", "build/model/core_rotate.py", "build/rtl/bcw_params.sv",
                                 "build/rtl/core/core_rotate.v", "build/tangle.json"]
        first = line(GOOD, "def core_rotate")
        assert tangled(files, "build/model/core_rotate.py") == [
            ("def core_rotate(turn):", CHAPTER, first), ("    return {'next': (turn + 1) % 8}", CHAPTER, first + 1)]
        first = line(GOOD, "module core_rotate")
        assert tangled(files, "build/rtl/core/core_rotate.v") == [
            ("module core_rotate (input wire [2:0] turn, output wire [2:0] next);", CHAPTER, first),
            ("    assign next = turn + 3'd1;", CHAPTER, first + 1), ("endmodule", CHAPTER, first + 2)]

    CHECKS = ("\n.. check:: test\n   :verifies: core.rotation\n\n   module tb;\n   endmodule\n"
              "\n.. check:: prove\n   :verifies: core.rotation\n   :depth: 10\n\n   module props;\n   endmodule\n"
              "\n.. check:: test\n   :verifies: core.rotation\n\n   module tb2;\n   endmodule\n")

    def test_each_check_with_code_is_a_file_whose_lines_map_to_the_chapter(self):
        text = GOOD + self.CHECKS
        files = Book({"core/core.rst": text}, tangle=True).files
        assert sorted(name for name in files if name.startswith("build/checks/")) == [
            "build/checks/core.rotation.prove.sv", "build/checks/core.rotation.test-2.sv",
            "build/checks/core.rotation.test.sv"]
        assert tangled(files, "build/checks/core.rotation.test.sv") == [
            ("module tb;", CHAPTER, line(text, "module tb;")), ("endmodule", CHAPTER, line(text, "module tb;") + 1)]

    def test_the_manifest_lists_each_check_in_the_chapter_order(self):
        text = GOOD + self.CHECKS
        checks = json.loads(Book({"core/core.rst": text}, tangle=True).files["build/checks.json"])["checks"]
        assert checks == [
            {"name": "core.rotation.equiv", "kind": "equiv", "verifies": ["core.rotation"], "path": CHAPTER,
             "line": line(text, ".. check:: equiv"), "file": None, "module": "core_rotate", "twin": "core_rotate",
             "twin_file": "build/model/core_rotate.py", "depth": None},
            {"name": "core.rotation.test", "kind": "test", "verifies": ["core.rotation"], "path": CHAPTER,
             "line": line(text, ".. check:: test"), "file": "build/checks/core.rotation.test.sv", "module": None,
             "twin": None, "twin_file": None, "depth": None},
            {"name": "core.rotation.prove", "kind": "prove", "verifies": ["core.rotation"], "path": CHAPTER,
             "line": line(text, ".. check:: prove"), "file": "build/checks/core.rotation.prove.sv", "module": None,
             "twin": None, "twin_file": None, "depth": 10},
            {"name": "core.rotation.test-2", "kind": "test", "verifies": ["core.rotation"], "path": CHAPTER,
             "line": line(text, "module tb2;") - 3, "file": "build/checks/core.rotation.test-2.sv", "module": None,
             "twin": None, "twin_file": None, "depth": None}]

    def test_the_manifest_holds_the_constant_of_each_parameter(self):
        text = GOOD + THREADS + WIDTH
        manifest = json.loads(Book({"core/core.rst": text}, tangle=True).files["build/checks.json"])
        assert manifest["constants"] == {"CORE_THREADS": 8, "CORE_TURN_WIDTH": 3}

    def test_a_proof_without_a_depth_has_the_depth_20(self):
        text = GOOD + "\n.. check:: prove\n   :verifies: core.rotation\n\n   module props;\n   endmodule\n"
        checks = json.loads(Book({"core/core.rst": text}, tangle=True).files["build/checks.json"])["checks"]
        assert [check["depth"] for check in checks] == [None, 20]

    def test_without_a_root_nothing_is_tangled(self):
        assert Book({"core/core.rst": GOOD}).files == {}



class TangleRecordTest:
    """The tangle keeps a file in build/ that changed after the last tangle, and reports it."""

    PATH = "build/rtl/core/core_rotate.v"

    def tangle(self, root, text=GOOD):
        return Book({"core/core.rst": text}, tangle=True, root=root)

    def test_the_record_holds_the_sha256_of_each_file(self, tmp_path):
        files = self.tangle(tmp_path).files
        record = json.loads(files["build/tangle.json"])["files"]
        assert sorted(record) == sorted(name.removeprefix("build/") for name in files
                                        if name not in ("build/tangle.json", "build/checks.json"))
        for name, entry in record.items():
            assert entry["sha256"] == hashlib.sha256((tmp_path / "build" / name).read_bytes()).hexdigest()

    def test_a_file_edited_by_hand_is_kept_and_reported(self, tmp_path):
        first = self.tangle(tmp_path)
        (tmp_path / self.PATH).write_text("// my edit\n")
        second = self.tangle(tmp_path)
        assert (tmp_path / self.PATH).read_text() == "// my edit\n"
        assert (f"WARNING: [tangle] {self.PATH}: the file changed after the last tangle, so the tangle kept it"
                in second.warnings)
        assert "fix: delete the file to tangle it again" in second.warnings
        # The record keeps the hash of the last tangle, so the next tangle reports the file again.
        assert (json.loads(second.files["build/tangle.json"])["files"]["rtl/core/core_rotate.v"] ==
                json.loads(first.files["build/tangle.json"])["files"]["rtl/core/core_rotate.v"])
        assert "[tangle]" in self.tangle(tmp_path).warnings

    def test_a_file_that_nobody_edited_is_tangled_again(self, tmp_path):
        self.tangle(tmp_path)
        second = self.tangle(tmp_path, GOOD.replace("turn + 3'd1;", "turn + 3'd2;"))
        assert "3'd2" in (tmp_path / self.PATH).read_text()
        assert "[tangle]" not in second.warnings

    def test_a_deleted_file_is_tangled_again(self, tmp_path):
        self.tangle(tmp_path)
        (tmp_path / self.PATH).unlink()
        second = self.tangle(tmp_path)
        assert (tmp_path / self.PATH).exists()
        assert "[tangle]" not in second.warnings

    def test_a_file_that_the_record_does_not_know_is_kept_and_reported(self, tmp_path):
        (tmp_path / self.PATH).parent.mkdir(parents=True)
        (tmp_path / self.PATH).write_text("// not the tangle's\n")
        book = self.tangle(tmp_path)
        assert (tmp_path / self.PATH).read_text() == "// not the tangle's\n"
        assert f"WARNING: [tangle] {self.PATH}: " in book.warnings
        assert "rtl/core/core_rotate.v" not in json.loads(book.files["build/tangle.json"])["files"]

    def test_a_kept_file_fails_a_build_with_w_and_keep_going(self, tmp_path):
        self.tangle(tmp_path)
        tools = Path(bcw.__file__).parent
        (tmp_path / "conf.py").write_text(f"import sys\nsys.path.insert(0, {str(tools)!r})\nextensions = ['bcw']\n"
                                          f"bcw_tangle_root = {str(tmp_path)!r}\n")
        command = [sys.executable, "-m", "sphinx", "-E", "-q", "-W", "--keep-going", "-b", "dummy", "-c",
                   str(tmp_path), str(tmp_path / "book"), str(tmp_path / "check")]
        assert subprocess.run(command, capture_output=True).returncode == 0
        (tmp_path / self.PATH).write_text("// my edit\n")
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 1, result.stderr
        assert "[tangle] build/rtl/core/core_rotate.v" in result.stderr

    EXTRA = "build/rtl/core/extra.v"

    def with_extra(self, root):
        """Tangle GOOD with one more file, EXTRA, so that a later tangle of GOOD leaves EXTRA an orphan."""
        return self.tangle(root, GOOD + source(self.EXTRA, "// extra"))

    def recorded(self, book):
        return json.loads(book.files["build/tangle.json"])["files"]

    def test_an_orphan_that_nobody_edited_is_deleted(self, tmp_path):
        assert "rtl/core/extra.v" in self.recorded(self.with_extra(tmp_path))
        book = self.tangle(tmp_path)
        assert not (tmp_path / self.EXTRA).exists()
        assert "rtl/core/extra.v" not in self.recorded(book)
        assert "[tangle]" not in book.warnings

    def test_an_orphan_edited_by_hand_is_kept_and_reported(self, tmp_path):
        first = self.with_extra(tmp_path)
        (tmp_path / self.EXTRA).write_text("// my edit\n")
        book = self.tangle(tmp_path)
        assert (tmp_path / self.EXTRA).read_text() == "// my edit\n"
        assert (f"WARNING: [tangle] {self.EXTRA}: the book no longer tangles the file, but it changed after the "
                "last tangle, so the tangle kept it") in book.warnings
        assert self.recorded(book)["rtl/core/extra.v"] == self.recorded(first)["rtl/core/extra.v"]
        assert f"[tangle] {self.EXTRA}" in self.tangle(tmp_path).warnings

    def test_an_orphan_that_someone_deleted_leaves_the_record(self, tmp_path):
        self.with_extra(tmp_path)
        (tmp_path / self.EXTRA).unlink()
        book = self.tangle(tmp_path)
        assert "rtl/core/extra.v" not in self.recorded(book)
        assert "[tangle]" not in book.warnings

    def test_a_file_that_the_tangle_never_wrote_stays(self, tmp_path):
        self.tangle(tmp_path)
        (tmp_path / "build/rtl/notes.txt").write_text("my notes\n")
        book = self.tangle(tmp_path)
        assert (tmp_path / "build/rtl/notes.txt").read_text() == "my notes\n"
        assert "[tangle]" not in book.warnings

    def test_a_file_that_already_holds_the_tangle_is_not_reported(self, tmp_path):
        self.tangle(tmp_path)
        (tmp_path / "build" / "tangle.json").unlink()
        assert "[tangle]" not in self.tangle(tmp_path).warnings


class FragmentTangleTest:
    """The tangle puts each fragment in place of its use, with the indentation of the use."""

    def test_a_file_from_a_skeleton_and_fragments_of_two_chapters(self):
        core = GOOD + source("build/rtl/core/pair.v", "module pair (input wire a, output wire b);",
                             "    <<:core.pair-logic>>", "    <<:zeta.more>>", "endmodule") + FRAGMENT
        zeta = chapter("Zeta", body="\nMore\n====\n" + source(":zeta.more", "// one", "// two"))
        files = Book({"core/core.rst": core, "zeta/zeta.rst": zeta}, tangle=True).files
        assert tangled(files, "build/rtl/core/pair.v") == [
            ("module pair (input wire a, output wire b);", CHAPTER, line(core, "module pair")),
            ("    assign b = a;", CHAPTER, line(core, "assign b = a;")),
            ("    // one", "book/zeta/zeta.rst", line(zeta, "// one")),
            ("    // two", "book/zeta/zeta.rst", line(zeta, "// two")),
            ("endmodule", CHAPTER, line(core, "endmodule", after="<<:zeta.more>>"))]
        assert not any("pair-logic" in name or "zeta.more" in name for name in files)

    def test_a_fragment_inside_a_fragment_adds_its_indentation(self):
        text = (GOOD + SKELETON.replace("<<:core.pair-logic>>", "<<:core.outer>>")
                + source(":core.outer", "begin", "    <<:core.pair-logic>>", "end") + FRAGMENT)
        lines = tangled(Book({"core/core.rst": text}, tangle=True).files, "build/rtl/core/pair.v")
        assert lines[1:4] == [("    begin", CHAPTER, line(text, "begin")),
                              ("        assign b = a;", CHAPTER, line(text, "assign b = a;")),
                              ("    end", CHAPTER, line(text, "end", after="<<:core.pair-logic>>"))]

    def test_the_indentation_makes_working_python(self):
        text = GOOD + source("build/model/body.py", "def f(x):", "    <<:core.body>>", "", "RESULT = f(1)") + source(
            ":core.body", "y = x + 1", "return y")
        files = Book({"core/core.rst": text}, tangle=True).files
        names = {}
        exec(files["build/model/body.py"], names)
        assert names["RESULT"] == 2
        assert tangled(files, "build/model/body.py")[1:3] == [("    y = x + 1", CHAPTER, line(text, "y = x + 1")),
                                                              ("    return y", CHAPTER, line(text, "return y"))]

    # A line that ends in a backslash goes on in the next line, in Python and in a Verilog
    # macro. The map names the chapter line of each line, so the next line maps to its own
    # chapter line, also where it comes from another block or a fragment.
    BACKSLASH = {
        "a fragment ends in a backslash": (
            source("build/model/b.py", "def f(x):", "    <<:core.sum>>", "        1", "    return total", "",
                   "RESULT = f(1)") + source(":core.sum", "total = x + \\")),
        "an outer line ends in a backslash": (
            source("build/model/b.py", "def f(x):", "    total = x + \\", "    <<:core.one>>", "    return total", "",
                   "RESULT = f(1)") + source(":core.one", "1")),
    }

    @pytest.mark.parametrize("case", BACKSLASH)
    def test_the_line_after_a_backslash_maps_to_its_own_chapter_line(self, case, tmp_path):
        text = GOOD + self.BACKSLASH[case]
        files = Book({"core/core.rst": text}, tangle=True).files
        names = {}
        exec(files["build/model/b.py"], names)
        assert names["RESULT"] == 2
        lines = tangled(files, "build/model/b.py")
        # Each line of code maps to the chapter line that holds it.
        assert all(text.splitlines()[number - 1].strip() == code.strip() for code, _, number in lines), lines
        for name, content in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(content)
        after = next(number for number in range(2, len(lines) + 1) if lines[number - 2][0].endswith("\\"))
        assert linemap.lookup(str(tmp_path / "build/model/b.py"), after) == lines[after - 1][1:]

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



class ModelTest:
    """The model that the checks, the tangle and the weave read, built once from the chapters."""

    def test_the_model_orders_the_chapters_and_groups_them_in_parts(self):
        zeta = chapter("Zeta", kind="tutorial")
        alpha = chapter("Alpha")
        model = Book({"alpha/alpha.rst": alpha, "core/core.rst": GOOD, "zeta/zeta.rst": zeta}).model
        assert [document.name for document in model.documents] == ["alpha", "core", "zeta"]
        assert [document.name for document in model.ordered] == ["zeta", "alpha", "core"]
        assert [(kind, [document.name for document in documents]) for kind, documents in model.parts] == [
            ("tutorial", ["zeta"]), ("reference", ["alpha", "core"])]
        assert model.left == []

    def test_a_chapter_of_no_known_kind_is_in_a_last_part(self):
        model = Book({"core/core.rst": GOOD, "story/story.rst": chapter("Story", kind="story")}).model
        assert [(kind, [document.name for document in documents]) for kind, documents in model.parts] == [
            ("reference", ["core"]), (None, ["story"])]

    def test_the_model_holds_the_fragments_the_files_and_the_uses(self):
        text = GOOD + SKELETON + FRAGMENT
        model = Book({"core/core.rst": text}).model
        assert model.fragments[":core.pair-logic"].line == line(text, ".. source:: :core.pair-logic")
        assert sorted(model.files) == ["build/model/core_rotate.py", "build/rtl/core/core_rotate.v",
                                       "build/rtl/core/pair.v"]
        [(block, number)] = model.uses[":core.pair-logic"]
        assert (block.target, number) == ("build/rtl/core/pair.v", line(text, "<<:core.pair-logic>>"))

    def test_a_use_inside_a_fragment_is_a_use(self):
        text = (GOOD + SKELETON.replace("<<:core.pair-logic>>", "<<:core.outer>>")
                + source(":core.outer", "<<:core.pair-logic>>") + FRAGMENT)
        uses = Book({"core/core.rst": text}).model.uses
        assert [(block.target, number) for block, number in uses[":core.pair-logic"]] == [
            (":core.outer", line(text, "<<:core.pair-logic>>"))]
        assert [block.target for block, _ in uses[":core.outer"]] == ["build/rtl/core/pair.v"]

    def test_the_model_holds_the_checks_in_the_chapter_order(self):
        zeta = chapter("Zeta", kind="tutorial", body="\n.. check:: test\n   :verifies: core.rotation\n\n   x\n")
        model = Book({"core/core.rst": GOOD, "zeta/zeta.rst": zeta}).model
        assert [(block.path, block.check) for block in model.checks] == [("book/zeta/zeta.rst", "test"),
                                                                          (CHAPTER, "equiv")]

    def test_the_model_holds_the_values_the_units_and_the_failures(self):
        text = GOOD + THREADS + WIDTH + parameter("core.bad", "core.none", unit="bits")
        model = Book({"core/core.rst": text}).model
        assert model.values == {"core.threads": 8, "core.turn-width": 3}
        assert model.units == {"core.threads": "threads", "core.turn-width": "bits", "core.bad": "bits"}
        assert list(model.failures) == ["core.bad"]
