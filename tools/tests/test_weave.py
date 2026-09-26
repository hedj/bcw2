"""Tests of tools/weave.py, which builds the reader edition as HTML and as LaTeX for the PDF.

ReferenceTest compares the HTML and the LaTeX of one book, GOLDEN_BOOK, with the
reference outputs in tools/tests/golden. The other tests each build a small book
with the extensions bcw and weave, and test one meaning of the output, such as
the order of the parts or a PDF without undefined references. The tests that only
read the HTML of BOOK share one build of it, through the fixture html.
"""

import re
from pathlib import Path

import pytest

from book import CORE_CHAPTER, DESIGN, GENERAL, GOOD, Book, chapter, deprecations, parameter, target

INDEX = "Book\n====\n\n.. chapters::\n"
LATEX = [("index", "book.tex", "Book", "Author", "manual")]
BOOK = {"core/core.rst": CORE_CHAPTER, "design/design.rst": DESIGN, "guide/guide.rst": chapter("Guide", "tutorial")}


def weave(chapters, builder, **options):
    options.setdefault("index", INDEX)
    return Book(chapters, builder=builder, extensions=["bcw", "weave"], latex_documents=LATEX, **options)


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


@pytest.fixture(scope="module")
def html():
    """BOOK woven as HTML, built once for the tests that only read it."""
    return weave(BOOK, "html")


@pytest.fixture(scope="module")
def core(html):
    """The page of the core chapter in html."""
    return html.output["core/core.html"]


class OrderTest:
    def test_the_index_lists_the_chapters_in_chapter_order_under_their_kinds(self):
        book = weave(BOOK, "html")
        assert book.tuples() == []
        index = body(book.output["index.html"])
        assert re.findall(r'<span class="caption-text">([^<]+)</span>', index) == ["Tutorials", "Reference"]
        links = re.findall(r'href="(\w+/\w+\.html)"', index)
        assert sorted(set(links), key=links.index) == ["guide/guide.html", "design/design.html", "core/core.html"]

    def test_a_chapter_whose_name_sorts_after_the_index_is_listed(self):
        index = body(weave({**BOOK, "zeta/zeta.rst": chapter("Zeta")}, "html").output["index.html"])
        links = re.findall(r'href="(\w+/\w+\.html)"', index)
        assert (sorted(set(links), key=links.index) ==
                ["guide/guide.html", "design/design.html", "core/core.html", "zeta/zeta.html"])

    def test_a_chapter_outside_the_order_is_listed_last(self):
        cycle = DESIGN + "\n.. definition:: design.zyx\n   :parent: core.core\n\n   A :dfn:`zyx` is a thing.\n"
        index = body(weave({**BOOK, "design/design.rst": cycle}, "html").output["index.html"])
        assert re.findall(r'<span class="caption-text">([^<]+)</span>', index) == ["Tutorials", "Unordered"]

    def test_each_kind_starts_an_unnumbered_part_in_the_latex(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        assert after(tex, r"\part*{Tutorials}\addcontentsline{toc}{part}{Tutorials}", r"\chapter{Guide}",
                     r"\part*{Reference}\addcontentsline{toc}{part}{Reference}",
                     r"\chapter{Design}", r"\chapter{Core}"), tex


class NumberingTest:
    """The HTML numbers the chapters through the whole book, as LaTeX does in the PDF."""

    def test_the_index_numbers_the_chapters_through_every_part(self, html):
        index = body(html.output["index.html"])
        assert (re.findall(r'href="\w+/\w+\.html">(\d+)\. (\w+)</a>', index) ==
                [("1", "Guide"), ("2", "Design"), ("3", "Core")])

    def test_the_link_to_the_previous_chapter_carries_its_number(self, core):
        assert 'title="previous chapter"><span class="section-number">2. </span>Design' in core

LABELS = ["goal", "requirement", "parameter", "definition", "rationale", "discussion", "target", "open"]


class StyleTest:
    """The stylesheet of the weave sets each rule apart from the prose around it."""

    @pytest.mark.parametrize("page, prefix", [("index.html", ""), ("core/core.html", "../")])
    def test_each_page_links_the_stylesheet(self, html, page, prefix):
        assert re.search(rf'<link rel="stylesheet" type="text/css" href="{prefix}_static/weave\.css[^"]*" />',
                         html.output[page])

    def test_a_requirement_and_a_definition_have_their_own_background(self, html):
        css = html.output["_static/weave.css"]

        def background(selector):
            return re.search(rf"(?s){re.escape(selector)} \{{[^}}]*background: ([^;]+);", css).group(1)

        colours = [background(".chunk"), background(".chunk.requirement"), background(".chunk.definition")]
        assert len(set(colours)) == 3, colours

    @pytest.mark.parametrize("label", LABELS)
    def test_each_chunk_has_a_border_and_each_label_its_colour(self, html, label):
        css = html.output["_static/weave.css"]
        assert re.search(r"(?s)\.chunk \{[^}]*border-left:", css)
        assert re.search(rf"\.chunk\.{label}\b[^{{]*\{{[^}}]*border-left-color:", css)


VALUED = CORE_CHAPTER.replace("eight cycles apart.", "eight cycles apart, one for each of :param:`core.threads`.") + \
    parameter("core.threads", "8", unit="threads") + \
    parameter("core.turn-width", "clog2(core.threads)", parent="core.threads", unit="bits", text="The width.") + \
    parameter("core.spare", "2", text="A spare value.")
VALUED_BOOK = {**BOOK, "core/core.rst": VALUED}


class ValueTest:
    """The weave shows the value of each PARAMETER where the text cites it, and on its first line."""

    def test_a_citation_shows_the_value_and_unit_as_a_link_to_the_parameter(self):
        core = weave(VALUED_BOOK, "html").output["core/core.html"]
        assert ('one for each of <a class="reference internal" href="#core.threads">'
                '<span class="param">8 threads</span></a>.') in core

    def test_a_citation_of_a_parameter_without_a_value_shows_its_anchor(self):
        text = VALUED.replace("   :value: 8\n", "")
        core = weave({**BOOK, "core/core.rst": text}, "html").output["core/core.html"]
        assert re.search((r'one for each of <a class="reference internal" href="#core\.threads"><code[^>]*>'
                          r'<span class="pre">core\.threads</span></code></a>'), core)


TARGETED = VALUED.replace("A thread's instructions", "The aim is :param:`core.aim`. A thread's instructions") + \
    target("core.aim", "core.threads * 2", parent="core.threads", unit="threads", text="The aim of the core.")


class ChecksTest:
    def test_the_weave_leaves_the_checks_unchanged(self):
        assert Book({"core/core.rst": GOOD}, general=GENERAL, extensions=["bcw", "weave"]).tuples() == []

    @pytest.mark.parametrize("builder", ["html", "latex"])
    def test_the_weave_gives_no_sphinx_deprecation_warning(self, builder):
        assert deprecations(lambda: weave(BOOK, builder)) == []


FRAGMENTED = (CORE_CHAPTER + "\n.. source:: build/rtl/core/pair.v\n\n"
              "   module pair (input wire a, output wire b);\n       <<:core.pair-logic>>\n   endmodule\n"
              "\n.. source:: :core.pair-logic\n\n   assign b = a;\n")
FRAGMENTED_BOOK = {**BOOK, "core/core.rst": FRAGMENTED}


class FragmentWeaveTest:
    """The weave names each fragment, and links each block that uses fragments to them."""

    def test_latexmk_makes_a_pdf_without_undefined_references(self):
        status, _, log = weave(FRAGMENTED_BOOK, "latex", pdf=True).pdf
        assert status == 0, log
        assert "undefined" not in log


class PdfTest:
    def test_latexmk_makes_a_pdf_of_the_latex(self):
        status, size, log = weave(BOOK, "latex", pdf=True).pdf
        assert status == 0, log
        assert size > 10000
        assert "multiply defined" not in log
        assert "undefined" not in log



INDEXED = INDEX + "\n.. code-index::\n"


class CodeIndexTest:
    """The directive code-index lists each file and each fragment, where it is defined and where it is used."""

    def test_without_the_directive_the_index_has_no_index_of_code(self, html):
        assert "Index of code" not in html.output["index.html"]

    def test_latexmk_makes_a_pdf_of_the_index_without_undefined_references(self):
        status, _, log = weave(FRAGMENTED_BOOK, "latex", index=INDEXED, pdf=True).pdf
        assert status == 0, log
        assert "undefined" not in log


# The reference outputs: one book that holds each feature of the weave, woven once as HTML
# and once as LaTeX. Each test compares an output with its file in tools/tests/golden. After
# a change to the weave, run pytest --update-golden, then read the difference of the files
# in git before the commit.
GOLDEN = Path(__file__).resolve().parent / "golden"
GOLDEN_BOOK = {**BOOK, "core/core.rst": TARGETED + FRAGMENTED[len(CORE_CHAPTER):]}
PAGES = ["index.html", "guide/guide.html", "design/design.html", "core/core.html"]


def main_part(page):
    """The main part of a page: the body, without the head, the sidebar and the footer of the theme."""
    start = page.index('<div class="body" role="main">')
    return page[start:page.index('<div class="sphinxsidebar"', start)].rstrip() + "\n"


def without_date(tex):
    return re.sub(r"(?m)^\\date\{.*\}$", r"\\date{}", tex)


def compare(request, name, text):
    path = GOLDEN / name
    if request.config.getoption("--update-golden"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    assert text == path.read_text(), f"run pytest --update-golden, then read the difference of {path}"


@pytest.fixture(scope="module")
def golden_html():
    return weave(GOLDEN_BOOK, "html", index=INDEXED)


class ReferenceTest:
    """The HTML and the LaTeX of GOLDEN_BOOK are the same as their reference outputs."""

    def test_the_book_gives_no_finding(self, golden_html):
        assert golden_html.tuples() == []

    @pytest.mark.parametrize("page", PAGES)
    def test_each_page_is_its_reference(self, request, golden_html, page):
        compare(request, "html/" + page, main_part(golden_html.output[page]))

    def test_the_latex_is_its_reference(self, request):
        tex = weave(GOLDEN_BOOK, "latex", index=INDEXED).output["book.tex"]
        compare(request, "latex/book.tex", without_date(tex))
