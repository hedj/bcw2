"""Tests of tools/bcw.py on one chapter: the reading, the chunk checks and the tangle.

GOOD is a small chapter that obeys every documentation rule. A test changes
one thing in it and expects the findings of the rule that the change breaks.
The helper line() finds a line number by its text, so that the tests do not
depend on the layout of GOOD. Each test builds a Sphinx book in a temporary
folder, with the chapter at book/core/core.rst.
"""

import contextlib
import hashlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.util.console import nocolor
from sphinx.util.docutils import docutils_namespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import bcw  # noqa: E402

nocolor()

ENGLISH = "The core shall give the turn after thread *t* to thread *t* + 1."
STAMP = hashlib.sha256(("REQUIREMENT " + ENGLISH).encode()).hexdigest()[:8]

GOOD = f"""\
:kind: reference

====
Core
====

Overview
========

The core runs every thread through one pipeline.

Rotation
========

.. requirement:: core.rotation
   :parent: core.timing

   The core shall give the turn after
   thread *t* to thread *t* + 1.

   .. twin::
      :file: build/model/core_rotate.py
      :stamp: {STAMP}

      def core_rotate(turn):
          return {{'next': turn + 1}}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [2:0] turn, output wire [2:0] next);
       assign next = turn + 3'd1;
   endmodule

.. rationale::

   A thread's instructions are eight cycles apart.

.. open:: The thread count is not settled.

.. definition:: core.turn
   :parent: core.core

   A :dfn:`turn` is a thread's cycle in the rotation.

.. definition:: core.core
   :parent: core.timing

   The :dfn:`core` runs the threads in turn.

**Thread.** An unlabelled bold paragraph is prose.

Goals
=====

.. goal:: core.timing

   No thread can change the timing of another thread.
"""

# The general words of the GOAL and the rules of GOOD. The labels, the defined
# terms and the options are not in it.
GENERAL = {"the", "shall", "give", "after", "thread", "t", "to", "a", "is", "cycle", "in",
           "rotation", "runs", "no", "can", "change", "timing", "of", "another"}

# A warning with a location starts with its path. A warning without one starts with its level.
WARNING = re.compile(r"^(?:(?P<path>[^\s:]+?)(?::(?P<line>\d+))?: )?(?:WARNING|ERROR|CRITICAL|SEVERE): (?P<text>.*)$")


def line(text, needle):
    """The 1-based number of the first line of text that holds needle."""
    return next(number for number, content in enumerate(text.splitlines(), 1)
                if needle in content)


class Book:
    """A book built in a temporary folder with the extension.

    chapters maps each path under book/ to its text. general and retired are
    sets of words and anchors, or None for no list file. tools maps the name of
    each file in tools/ to its text. With tangle, the tangle writes under the
    temporary folder. builder names the Sphinx builder, and output keeps the text
    of each HTML, CSS and LaTeX file that it writes. index replaces the index, which
    lists the chapters by default. With pdf, latexmk makes a PDF of the LaTeX,
    and pdf keeps its exit status and the size of the PDF.
    """

    def __init__(self, chapters, general=None, retired=None, tools=None, tangle=False, builder="dummy",
                 index=None, pdf=False, **overrides):
        directory = tempfile.TemporaryDirectory()
        self.root = Path(directory.name)
        try:
            source = self.root / "book"
            index = index or "Book\n====\n\n.. toctree::\n\n" + "".join(
                f"   {Path(relative).with_suffix('')}\n" for relative in chapters)
            for relative, text in {"index.rst": index, **chapters}.items():
                (source / relative).parent.mkdir(parents=True, exist_ok=True)
                (source / relative).write_text(text)
            overrides = {"extensions": ["bcw"], **overrides}
            if general is not None:
                (source / "general-words.txt").write_text("".join(word + "\n" for word in sorted(general)))
                overrides["bcw_general_words"] = str(source / "general-words.txt")
            if retired is not None:
                (source / "retired-anchors.txt").write_text("".join(anchor + "\n" for anchor in sorted(retired)))
                overrides["bcw_retired_anchors"] = str(source / "retired-anchors.txt")
            if tools is not None:
                (self.root / "tools").mkdir()
                for name, text in tools.items():
                    (self.root / "tools" / name).write_text(text)
                overrides["bcw_tools"] = [str(self.root / "tools" / name) for name in sorted(tools)]
            if tangle:
                overrides["bcw_tangle_root"] = str(self.root)
            warnings = io.StringIO()
            with docutils_namespace():
                app = Sphinx(str(source), None, str(self.root / "out"), str(self.root / "doctrees"), builder,
                             confoverrides=overrides, status=None, warning=warnings, freshenv=True)
                app.build()
                self.resolved = {name: app.env.get_and_resolve_doctree(name, app.builder)
                                 for name in sorted(app.env.found_docs)}
            self.findings = app.env.bcw_findings
            for finding in self.findings:
                finding.path = finding.path.replace(str(self.root) + "/", "")
            self.documents = [app.env.bcw_documents[name] for name in sorted(app.env.bcw_documents)]
            self.warnings = warnings.getvalue().replace(str(self.root) + "/", "")
            self.files = {str(path.relative_to(self.root)): path.read_text()
                          for path in sorted(self.root.glob("build/**/*")) if path.is_file()}
            self.output = {str(path.relative_to(self.root / "out")): path.read_text()
                           for path in sorted((self.root / "out").glob("**/*"))
                           if path.suffix in (".html", ".tex", ".css")}
            if pdf:
                result = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error"],
                                        cwd=self.root / "out", capture_output=True, text=True)
                made = sorted((self.root / "out").glob("*.pdf"))
                self.pdf = (result.returncode, made[0].stat().st_size if made else 0, result.stdout[-2000:])
        finally:
            directory.cleanup()

    def others(self):
        """(path, line, first line of text) of each warning that is not a finding of the extension."""
        found = []
        for text in self.warnings.splitlines():
            match = WARNING.match(text)
            if match and not re.match(r"\[[\w-]+\] ", match["text"]):
                found.append((match["path"] or "", int(match["line"]) if match["line"] else None, match["text"]))
        return found

    def tuples(self):
        """(path, line, check, anchor) of each finding, with each other warning as the check "sphinx"."""
        found = [(f.path, f.line, f.check, f.anchor) for f in self.findings]
        found += [(path, number, "sphinx", None) for path, number, _ in self.others()]
        return sorted(found, key=lambda f: (f[0], f[1] or 0, f[2]))


def findings(text, retired=None, tools=None, general=None):
    """The findings on text as the chapter book/core/core.rst, as (line, check, anchor).

    With general=None, the extension skips doc.known-words, so that a test of
    another rule can add new words.
    """
    return [(number, name, anchor) for path, number, name, anchor
            in Book({"core/core.rst": text}, general, retired, tools).tuples()]


def only(check_name, text, **options):
    return [f for f in findings(text, **options) if f[1] == check_name]


class GoodTest(unittest.TestCase):
    def test_a_correct_chapter_has_no_findings_and_no_warnings(self):
        book = Book({"core/core.rst": GOOD}, general=GENERAL)
        self.assertEqual(book.findings, [])
        self.assertEqual(book.warnings, "")

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
