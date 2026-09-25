"""Tests of tools/bcw.py on one chapter: the reading, the chunk checks and the tangle.

Each test builds a book from GOOD, the chapter of tools/tests/book.py, with one
thing changed, and expects the findings of the rule that the change breaks.
"""

import contextlib
import hashlib
import io
import unittest

import bcw
from book import ENGLISH, GENERAL, GOOD, STAMP, Book, deprecations, findings, line


class GoodTest(unittest.TestCase):
    def test_a_correct_chapter_has_no_findings_and_no_warnings(self):
        book = Book({"core/core.rst": GOOD}, general=GENERAL)
        self.assertEqual(book.findings, [])
        self.assertEqual(book.warnings, "")

    def test_the_build_gives_no_sphinx_deprecation_warning(self):
        self.assertEqual(deprecations(lambda: Book({"core/core.rst": GOOD})), [])

    def test_the_reading_of_good(self):
        document = Book({"core/core.rst": GOOD}).documents[0]
        self.assertEqual((document.path, document.name, document.kind), ("book/core/core.rst", "core", "reference"))
        self.assertEqual([(chunk.line, chunk.label, chunk.anchor) for chunk in document.chunks], [
            (line(GOOD, ".. requirement::"), "REQUIREMENT", "core.rotation"),
            (line(GOOD, ".. rationale::"), "RATIONALE", None),
            (line(GOOD, ".. open::"), "OPEN", None),
            (line(GOOD, ".. definition:: core.turn"), "DEFINITION", "core.turn"),
            (line(GOOD, ".. definition:: core.core"), "DEFINITION", "core.core"),
            (line(GOOD, ".. goal::"), "GOAL", "core.timing")])
        rotation = document.chunks[0]
        self.assertEqual(rotation.lines, [(line(GOOD, "The core shall"), "The core shall give the turn after"),
                                          (line(GOOD, "thread *t* to"), "thread *t* to thread *t* + 1.")])
        self.assertEqual(rotation.english, ENGLISH)
        self.assertEqual(rotation.option_lines, {"parent": line(GOOD, ":parent: core.timing")})
        self.assertEqual([chunk.term for chunk in document.chunks if chunk.term], ["turn", "core"])
        self.assertEqual([(block.kind, block.line, block.target, block.chunk and block.chunk.anchor)
                          for block in document.blocks], [
            ("twin", line(GOOD, ".. twin::"), "build/model/core_rotate.py", "core.rotation"),
            ("source", line(GOOD, ".. source::"), "build/rtl/core/core_rotate.v", None)])
        self.assertEqual(document.sections, [(line(GOOD, "Core"), 1, "Core"), (line(GOOD, "Overview"), 2, "Overview"),
                                             (line(GOOD, "Rotation"), 2, "Rotation"), (line(GOOD, "Goals"), 2, "Goals")])


class LabelsTest(unittest.TestCase):
    """doc.labels: docutils rejects a directive that the extension does not register."""

    def test_an_unknown_label_is_an_error_on_its_line(self):
        text = GOOD.replace(".. rationale::", ".. reason::")
        book = Book({"core/core.rst": text})
        self.assertEqual(book.others(), [("book/core/core.rst", line(text, ".. reason::"),
                                          'Unknown directive type "reason".')])

    def test_each_label_is_a_directive(self):
        self.assertEqual(sorted(bcw.CHUNK_DIRECTIVES),
                         ["definition", "discussion", "goal", "open", "parameter", "rationale", "requirement",
                          "target"])


class OneShallTest(unittest.TestCase):
    """doc.one-shall"""

    def test_a_requirement_without_shall_is_a_finding(self):
        text = GOOD.replace("The core shall give", "The core gives")
        self.assertIn((line(text, ".. requirement::"), "one-shall", "core.rotation"), findings(text))

    def test_shall_inside_a_quotation_does_not_count(self):
        text = GOOD.replace("The core shall give", "The core ``shall`` give")
        self.assertIn((line(text, ".. requirement::"), "one-shall", "core.rotation"), findings(text))

    def test_a_second_shall_is_a_finding_on_its_line(self):
        text = GOOD.replace("*t* + 1.", "*t* + 1 and shall not stall.")
        self.assertIn((line(text, "shall not stall"), "one-shall", "core.rotation"), findings(text))

    def test_a_shall_in_a_definition_is_a_finding_on_its_line(self):
        text = GOOD.replace("A :dfn:`turn` is", "A :dfn:`turn` shall be")
        self.assertEqual(findings(text), [(line(text, "`turn` shall"), "one-shall", "core.turn")])

    def test_a_shall_in_a_rationale_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.", "eight cycles apart, and shall stay so.")
        self.assertEqual(findings(text), [(line(text, "shall stay so"), "one-shall", None)])

    def test_a_shall_inside_a_quotation_of_another_chunk_passes(self):
        text = GOOD.replace("A :dfn:`turn` is", "A :dfn:`turn`, not a ``shall``, is")
        self.assertEqual(findings(text), [])


class AnchorsTest(unittest.TestCase):
    """doc.anchors"""

    def test_a_rule_without_an_anchor_is_an_error_on_its_line(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition::")
        book = Book({"core/core.rst": text})
        self.assertEqual([(path, number) for path, number, _ in book.others()],
                         [("book/core/core.rst", line(text, ".. definition::"))])
        self.assertIn("1 argument(s) required, 0 supplied", book.warnings)

    def test_an_anchor_outside_the_grammar_is_a_finding(self):
        text = GOOD.replace(".. definition:: core.turn", ".. definition:: Core_Turn")
        self.assertEqual(findings(text), [(line(text, "Core_Turn"), "anchors", "Core_Turn")])

    def test_the_anchor_form_is_parts_of_lower_case_letters_digits_and_hyphens_joined_by_dots(self):
        for anchor, good in [("core.rot-2", True), ("core.2x", True), ("core.b.c", True),
                             ("core", False), ("1core.x", False), ("core..x", False),
                             ("core.Rot", False), ("core_x.y", False), ("-core.x", False)]:
            with self.subTest(anchor=anchor):
                text = GOOD.replace(".. definition:: core.turn", ".. definition:: " + anchor)
                expected = [] if good else [(line(text, ".. definition:: " + anchor), "anchors", anchor)]
                self.assertEqual(findings(text), expected)

    def test_a_retired_anchor_is_a_finding(self):
        self.assertEqual(findings(GOOD, retired={"core.turn"}),
                         [(line(GOOD, ".. definition:: core.turn"), "anchors", "core.turn")])

    def test_a_duplicate_anchor_in_another_chapter_is_a_finding(self):
        other = (":kind: reference\n\n====\nBank\n====\n\nOverview\n========\n\nText.\n\nBanks\n=====\n\n"
                 ".. definition:: core.turn\n   :parent: core.core\n\n   A :dfn:`bank` is a register set.\n")
        book = Book({"core/core.rst": GOOD, "bank/bank.rst": other})
        # The extension reads the chapters in order of name, so the later name holds the duplicate.
        self.assertEqual(book.tuples(), [("book/bank/bank.rst", line(other, ".. definition::"), "anchor-prefix", "core.turn"),
                                         ("book/core/core.rst", line(GOOD, ".. definition:: core.turn"), "anchors",
                                          "core.turn")])
        self.assertIn(f"book/bank/bank.rst:{line(other, '.. definition::')}",
                      [f for f in book.findings if f.check == "anchors"][0].message)


class GoalTest(unittest.TestCase):
    def test_a_goal_needs_no_shall(self):
        self.assertEqual(findings(GOOD), [])

    def test_a_goal_without_an_anchor_is_an_error(self):
        text = GOOD + "\n.. goal::\n\n   Another goal.\n"
        self.assertEqual(findings(text), [(line(text, "Another goal") - 2, "sphinx", None)])

    def test_a_twin_inside_a_goal_is_a_finding(self):
        text = GOOD + "\n   .. twin::\n\n      x\n"
        self.assertEqual(findings(text), [(len(text.splitlines()) - 2, "stamps", "core.timing")])


class StampsTest(unittest.TestCase):
    """doc.stamps"""

    def test_a_stale_stamp_is_a_finding_that_gives_the_new_stamp(self):
        text = GOOD.replace("thread *t* + 1.", "thread *t* + 2.")
        result = [f for f in Book({"core/core.rst": text}).findings if f.check == "stamps"]
        new = hashlib.sha256(("REQUIREMENT " + ENGLISH.replace("+ 1.", "+ 2.")).encode()).hexdigest()[:8]
        self.assertEqual([(f.line, f.anchor) for f in result], [(line(text, ".. twin::"), "core.rotation")])
        self.assertIn(f":stamp: {new}", result[0].fix)

    def test_a_missing_stamp_is_a_finding(self):
        text = GOOD.replace(f"      :stamp: {STAMP}\n", "")
        self.assertEqual(findings(text), [(line(text, ".. twin::"), "stamps", "core.rotation")])

    def test_reflowed_english_and_changed_options_keep_the_stamp(self):
        text = GOOD.replace("after\n   thread", "after thread").replace(
            ":parent: core.timing\n\n   The core", ":parent: core.timing, core.core\n\n   The core")
        self.assertEqual(findings(text), [])

    def test_a_twin_inside_a_chunk_that_is_not_a_rule_is_a_finding(self):
        text = GOOD.replace("eight cycles apart.\n", "eight cycles apart.\n\n   .. twin::\n\n      x\n")
        self.assertEqual(findings(text), [(line(text, "eight cycles apart.") + 2, "stamps", None)])

    def test_a_twin_outside_any_chunk_is_a_finding(self):
        text = GOOD + "\nSome prose.\n\n.. twin::\n\n   x\n"
        self.assertEqual(findings(text), [(len(text.splitlines()) - 2, "stamps", None)])


class SummaryTest(unittest.TestCase):
    def test_bcw_summary_prints_the_counts_on_standard_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Book({"core/core.rst": GOOD}, retired={"core.turn"}, bcw_summary=True)
        self.assertEqual(output.getvalue(), "bcw: 1 chapters, 1 findings, 0 rules with more than 2 parents\n")

    def test_without_it_nothing_is_printed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Book({"core/core.rst": GOOD})
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
