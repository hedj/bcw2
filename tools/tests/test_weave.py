"""Tests of tools/weave.py, which builds the reader edition as HTML and as LaTeX for the PDF.

Each test builds a small book with the extensions bcw and weave, and reads the
HTML or LaTeX that Sphinx writes.
"""

import re
import unittest

from test_bcw import GENERAL, GOOD, Book
from test_bcw_rules import CORE_CHAPTER, DESIGN, chapter

INDEX = "Book\n====\n\n.. chapters::\n"
LATEX = [("index", "book.tex", "Book", "Author", "manual")]
BOOK = {"core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN, "guide/guide.rst": chapter("Guide", "tutorial")}


def weave(chapters, builder, **options):
    return Book(chapters, builder=builder, index=INDEX, extensions=["bcw", "weave"], latex_documents=LATEX,
                **options)


def body(page):
    """The page without the sidebar of the theme, which repeats the table of contents."""
    return page.split('class="sphinxsidebar"')[0]


def after(text, *needles):
    """Whether the needles occur in text in this order."""
    at = -1
    for needle in needles:
        at = text.find(needle, at + 1)
        if at < 0:
            return False
    return True


class OrderTest(unittest.TestCase):
    def test_the_index_lists_the_chapters_in_chapter_order_under_their_kinds(self):
        book = weave(BOOK, "html")
        self.assertEqual(book.tuples(), [])
        index = body(book.output["index.html"])
        self.assertEqual(re.findall(r'<span class="caption-text">([^<]+)</span>', index), ["Tutorials", "Reference"])
        links = re.findall(r'href="(\w+/\w+\.html)"', index)
        self.assertEqual(sorted(set(links), key=links.index), ["guide/guide.html", "design/design.html", "core/core.html"])

    def test_a_chapter_whose_name_sorts_after_the_index_is_listed(self):
        index = body(weave({**BOOK, "zeta/zeta.rst": chapter("Zeta")}, "html").output["index.html"])
        links = re.findall(r'href="(\w+/\w+\.html)"', index)
        self.assertEqual(sorted(set(links), key=links.index),
                         ["guide/guide.html", "design/design.html", "core/core.html", "zeta/zeta.html"])

    def test_a_chapter_outside_the_order_is_listed_last(self):
        cycle = DESIGN + "\n.. definition:: design.zyx\n   :parent: core.core\n\n   A :dfn:`zyx` is a thing.\n"
        index = body(weave({**BOOK, "design/design.rst": cycle}, "html").output["index.html"])
        self.assertEqual(re.findall(r'<span class="caption-text">([^<]+)</span>', index), ["Tutorials", "Unordered"])

    def test_each_kind_starts_an_unnumbered_part_in_the_latex(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        self.assertTrue(after(tex, r"\part*{Tutorials}\addcontentsline{toc}{part}{Tutorials}", r"\chapter{Guide}",
                              r"\part*{Reference}\addcontentsline{toc}{part}{Reference}",
                              r"\chapter{Design}", r"\chapter{Core}"), tex)


class NumberingTest(unittest.TestCase):
    """The HTML numbers the chapters through the whole book, as LaTeX does in the PDF."""

    def setUp(self):
        self.book = weave(BOOK, "html")

    def test_the_index_numbers_the_chapters_through_every_part(self):
        index = body(self.book.output["index.html"])
        self.assertEqual(re.findall(r'href="\w+/\w+\.html">(\d+)\. (\w+)</a>', index),
                         [("1", "Guide"), ("2", "Design"), ("3", "Core")])

    def test_a_chapter_and_its_sections_carry_its_number(self):
        core = body(self.book.output["core/core.html"])
        self.assertEqual(re.findall(r'<span class="section-number">([\d.]+) </span>', core),
                         ["3.", "3.1.", "3.2.", "3.3.", "3.4."])

    def test_the_link_to_the_previous_chapter_carries_its_number(self):
        self.assertIn('title="previous chapter"><span class="section-number">2. </span>Design',
                      self.book.output["core/core.html"])

    def test_the_pdf_shows_chapter_numbers_in_numerals(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        self.assertNotIn("fncychap", tex)


class ChunkTest(unittest.TestCase):
    def setUp(self):
        self.core = weave(BOOK, "html").output["core/core.html"]

    def test_each_chunk_is_a_container_whose_id_is_its_anchor(self):
        for label, anchor in [("requirement", "core.rotation"), ("definition", "core.turn"), ("goal", "core.timing")]:
            with self.subTest(anchor=anchor):
                self.assertRegex(self.core, rf'<div class="chunk {label}[^"]*" id="{re.escape(anchor)}">')

    def test_the_first_line_shows_the_label_and_the_anchor(self):
        self.assertRegex(self.core, r'<p class="chunk-label"><strong>REQUIREMENT</strong> '
                                    r'<code[^>]*><span class="pre">core.rotation</span></code></p>')

    def test_the_serves_line_links_to_each_parent(self):
        self.assertRegex(self.core, r'Serves: <a class="reference internal" href="\.\./design/design\.html#design\.timing">')
        self.assertRegex(self.core, r'Serves: <a class="reference internal" href="#core\.core">')

    def test_an_open_chunk_shows_its_title(self):
        self.assertRegex(self.core, r"<strong>OPEN</strong> The thread count is not settled\.")


class CodeTest(unittest.TestCase):
    def test_in_html_each_twin_and_each_source_is_a_closed_disclosure(self):
        core = weave(BOOK, "html").output["core/core.html"]
        self.assertRegex(core, r"(?s)<details><summary>Formal twin</summary>.*?return.*?</details>")
        self.assertRegex(core, r"(?s)<details><summary>Verilog: build/rtl/core/core_rotate\.v</summary>.*?endmodule.*?</details>")

    def test_in_latex_the_twin_is_small_under_its_rule(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        self.assertTrue(after(tex, "The core shall give", "Formal twin", r"\fvset{fontsize=\small}", "return",
                              r"\section{Explanation}"), tex)

    def test_in_latex_the_verilog_moves_to_the_end_of_its_chapter(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        core = tex[tex.index(r"\chapter{Core}"):]
        self.assertTrue(after(core, "Verilog:", r"\section{Explanation}", r"\section{Implementation}", "endmodule"),
                        core)
        self.assertLess(core.index(r"\section{Implementation}"), core.index("endmodule"))


class ExplanationTest(unittest.TestCase):
    def setUp(self):
        self.core = weave(BOOK, "html").output["core/core.html"]
        self.heading = self.core.index(">Explanation<")

    def test_each_rationale_moves_to_the_explanation_section_at_the_end_of_its_chapter(self):
        self.assertGreater(self.core.index("eight cycles apart"), self.heading)

    def test_a_why_line_links_to_it_from_its_old_place(self):
        match = re.search(r'Why: <a class="reference internal" href="#([^"]+)">', self.core)
        self.assertLess(match.start(), self.heading)
        self.assertGreater(self.core.index(f'id="{match.group(1)}"'), self.heading)

    def test_the_why_line_is_not_styled_as_a_chunk(self):
        self.assertIn('<p class="chunk-why">Why:', self.core)

    def test_it_links_back_to_the_section_that_it_came_from(self):
        self.assertIn('<a class="reference internal" href="#rotation">Rotation</a>', self.core[self.heading:])


class StyleTest(unittest.TestCase):
    """The stylesheet of the weave sets each rule apart from the prose around it."""

    def setUp(self):
        self.book = weave(BOOK, "html")

    def test_each_page_links_the_stylesheet(self):
        for page, prefix in [("index.html", ""), ("core/core.html", "../")]:
            with self.subTest(page=page):
                self.assertRegex(self.book.output[page],
                                 rf'<link rel="stylesheet" type="text/css" href="{prefix}_static/weave\.css[^"]*" />')

    def test_a_requirement_and_a_definition_have_their_own_background(self):
        css = self.book.output["_static/weave.css"]

        def background(selector):
            return re.search(rf"(?s){re.escape(selector)} \{{[^}}]*background: ([^;]+);", css).group(1)

        colours = [background(".chunk"), background(".chunk.requirement"), background(".chunk.definition")]
        self.assertEqual(len(set(colours)), 3, colours)

    def test_each_chunk_has_a_border_and_each_label_its_colour(self):
        css = self.book.output["_static/weave.css"]
        self.assertRegex(css, r"(?s)\.chunk \{[^}]*border-left:")
        for label in ["goal", "requirement", "parameter", "definition", "rationale", "discussion", "target", "open"]:
            with self.subTest(label=label):
                self.assertRegex(css, rf"\.chunk\.{label}\b[^{{]*\{{[^}}]*border-left-color:")


class ChecksTest(unittest.TestCase):
    def test_the_weave_leaves_the_checks_unchanged(self):
        self.assertEqual(Book({"core/core.rst": GOOD}, general=GENERAL, extensions=["bcw", "weave"]).tuples(), [])


class PdfTest(unittest.TestCase):
    def test_latexmk_makes_a_pdf_of_the_latex(self):
        status, size, log = weave(BOOK, "latex", pdf=True).pdf
        self.assertEqual(status, 0, log)
        self.assertGreater(size, 10000)
        self.assertNotIn("multiply defined", log)
        self.assertNotIn("undefined", log)


if __name__ == "__main__":
    unittest.main()
