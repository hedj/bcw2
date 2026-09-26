"""Tests of tools/bcw.py on one chapter that need more than its findings: the reading, stamps and the summary.

The cases in tools/tests/cases hold the tests that only compare the findings of
a chapter. Each test here builds a book from GOOD, the chapter of
tools/tests/book.py, and reads more of the result.
"""

import contextlib
import hashlib
import io

import bcw
from book import ENGLISH, GENERAL, GOOD, Book, deprecations, findings, line


class GoodTest:
    def test_a_correct_chapter_has_no_findings_and_no_warnings(self):
        book = Book({"core/core.rst": GOOD}, general=GENERAL)
        assert book.findings == []
        assert book.warnings == ""

    def test_the_build_gives_no_sphinx_deprecation_warning(self):
        assert deprecations(lambda: Book({"core/core.rst": GOOD})) == []

    def test_the_reading_of_good(self):
        document = Book({"core/core.rst": GOOD}).documents[0]
        assert (document.path, document.name, document.kind) == ("book/core/core.rst", "core", "reference")
        assert [(chunk.line, chunk.label, chunk.anchor) for chunk in document.chunks] == [
    (line(GOOD, ".. requirement::"), "REQUIREMENT", "core.rotation"),
    (line(GOOD, ".. rationale::"), "RATIONALE", None),
    (line(GOOD, ".. open::"), "OPEN", None),
    (line(GOOD, ".. definition:: core.turn"), "DEFINITION", "core.turn"),
    (line(GOOD, ".. definition:: core.core"), "DEFINITION", "core.core"),
    (line(GOOD, ".. goal::"), "GOAL", "core.timing")]
        rotation = document.chunks[0]
        assert rotation.lines == [(line(GOOD, "The core shall"), "The core shall give the turn after"),
                                  (line(GOOD, "thread *t* to"), "thread *t* to thread *t* + 1.")]
        assert rotation.english == ENGLISH
        assert rotation.option_lines == {"parent": line(GOOD, ":parent: core.timing")}
        assert [chunk.term for chunk in document.chunks if chunk.term] == ["turn", "core"]
        assert [(block.kind, block.line, block.target, block.chunk and block.chunk.anchor)
                for block in document.blocks] == [
    ("twin", line(GOOD, ".. twin::"), "build/model/core_rotate.py", "core.rotation"),
    ("source", line(GOOD, ".. source::"), "build/rtl/core/core_rotate.v", None),
    ("check", line(GOOD, ".. check:: equiv"), None, None)]
        assert document.sections == [(line(GOOD, "Core"), 1, "Core"), (line(GOOD, "Overview"), 2, "Overview"),
                                     (line(GOOD, "Rotation"), 2, "Rotation"), (line(GOOD, "Goals"), 2, "Goals")]


class LabelsTest:
    """doc.labels: the extension registers a directive for each label. ParseErrorTest has an unknown label."""

    def test_each_label_is_a_directive(self):
        assert (sorted(bcw.CHUNK_DIRECTIVES) ==
                ["definition", "discussion", "goal", "open", "parameter", "rationale", "requirement",
                 "target"])


class AnchorsTest:
    """doc.anchors"""

    def test_a_duplicate_anchor_in_another_chapter_is_a_finding(self):
        other = (":kind: reference\n\n====\nBank\n====\n\nOverview\n========\n\nText.\n\nBanks\n=====\n\n"
                 ".. definition:: core.turn\n   :parent: core.core\n\n   A :dfn:`bank` is a register set.\n")
        book = Book({"core/core.rst": GOOD, "bank/bank.rst": other})
        # The extension reads the chapters in order of name, so the later name holds the duplicate.
        assert book.tuples() == [("book/bank/bank.rst", line(other, ".. definition::"), "anchor-prefix", "core.turn"),
                                 ("book/core/core.rst", line(GOOD, ".. definition:: core.turn"), "anchors",
                                  "core.turn")]
        assert (f"book/bank/bank.rst:{line(other, '.. definition::')}" in
                [f for f in book.findings if f.check == "anchors"][0].message)


class StampsTest:
    """doc.stamps"""

    def test_a_stale_stamp_is_a_finding_that_gives_the_new_stamp(self):
        text = GOOD.replace("thread *t* + 1.", "thread *t* + 2.")
        result = [f for f in Book({"core/core.rst": text}).findings if f.check == "stamps"]
        new = hashlib.sha256(("REQUIREMENT " + ENGLISH.replace("+ 1.", "+ 2.")).encode()).hexdigest()[:8]
        assert [(f.line, f.anchor) for f in result] == [(line(text, ".. twin::"), "core.rotation")]
        assert f":stamp: {new}" in result[0].fix


class SummaryTest:
    def test_bcw_summary_prints_the_counts_on_standard_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Book({"core/core.rst": GOOD}, retired={"core.turn"}, bcw_summary=True)
        assert output.getvalue() == "bcw: 1 chapters, 1 findings, 0 rules with more than 2 parents\n"

    def test_without_it_nothing_is_printed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Book({"core/core.rst": GOOD})
        assert output.getvalue() == ""

