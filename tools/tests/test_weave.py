"""Tests of tools/weave.py, which builds the reader edition as HTML and as LaTeX for the PDF.

Each test builds a small book with the extensions bcw and weave, and reads the
HTML or LaTeX that Sphinx writes. The tests that only read the HTML of BOOK share
one build of it, through the fixture html.
"""

import re

import pytest

from book import CORE_CHAPTER, DESIGN, GENERAL, GOOD, Book, chapter, deprecations, parameter, target

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

    def test_a_chapter_and_its_sections_carry_its_number(self, core):
        core = body(core)
        assert (re.findall(r'<span class="section-number">([\d.]+) </span>', core) ==
                ["3.", "3.1.", "3.2.", "3.3.", "3.4."])

    def test_the_link_to_the_previous_chapter_carries_its_number(self, core):
        assert 'title="previous chapter"><span class="section-number">2. </span>Design' in core

    def test_the_contents_of_the_pdf_are_titled_contents_not_after_the_first_part(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        assert after(tex, r"\begin{document}", r"\renewcommand{\contentsname}{Contents}\sphinxtableofcontents"), tex

    def test_the_pdf_shows_chapter_numbers_in_numerals(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        assert "fncychap" not in tex


class ChunkTest:
    @pytest.mark.parametrize("label, anchor", [("requirement", "core.rotation"), ("definition", "core.turn"),
                                               ("goal", "core.timing")])
    def test_each_chunk_is_a_container_whose_id_is_its_anchor(self, core, label, anchor):
        assert re.search(rf'<div class="chunk {label}[^"]*" id="{re.escape(anchor)}">', core)

    def test_the_first_line_shows_the_label_and_the_anchor(self, core):
        assert re.search((r'<p class="chunk-label"><strong>REQUIREMENT</strong> '
                          r'<code[^>]*><span class="pre">core.rotation</span></code></p>'), core)

    def test_the_serves_line_links_to_each_parent(self, core):
        assert re.search(r'Serves: <a class="reference internal" href="\.\./design/design\.html#design\.timing">',
                         core)
        assert re.search(r'Serves: <a class="reference internal" href="#core\.core">', core)

    def test_an_open_chunk_shows_its_title(self, core):
        assert re.search(r"<strong>OPEN</strong> The thread count is not settled\.", core)


class CodeTest:
    def test_in_html_each_twin_and_each_source_is_a_closed_disclosure(self, core):
        assert re.search(r"(?s)<details><summary>Formal twin</summary>.*?return.*?</details>", core)
        assert re.search(r"(?s)<details><summary>Verilog: build/rtl/core/core_rotate\.v</summary>"
                         r".*?endmodule.*?</details>", core)

    def test_in_latex_the_twin_is_small_under_its_rule(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        assert after(tex, "The core shall give", "Formal twin", r"\fvset{fontsize=\small}", "return",
                     r"\section{Explanation}"), tex

    def test_in_latex_the_verilog_moves_to_the_end_of_its_chapter(self):
        tex = weave(BOOK, "latex").output["book.tex"]
        core = tex[tex.index(r"\chapter{Core}"):]
        assert after(core, "Verilog:", r"\section{Explanation}", r"\section{Implementation}", "endmodule"), core
        assert core.index(r"\section{Implementation}") < core.index("endmodule")


class ExplanationTest:
    @pytest.fixture
    def heading(self, core):
        """Where the Explanation section starts in the page of the core chapter."""
        return core.index(">Explanation<")

    def test_each_rationale_moves_to_the_explanation_section_at_the_end_of_its_chapter(self, core, heading):
        assert core.index("eight cycles apart") > heading

    def test_a_why_line_links_to_it_from_its_old_place(self, core, heading):
        match = re.search(r'Why: <a class="reference internal" href="#([^"]+)">', core)
        assert match.start() < heading
        assert core.index(f'id="{match.group(1)}"') > heading

    def test_the_why_line_is_not_styled_as_a_chunk(self, core):
        assert '<p class="chunk-why">Why:' in core

    def test_it_links_back_to_the_section_that_it_came_from(self, core, heading):
        assert '<a class="reference internal" href="#rotation">Rotation</a>' in core[heading:]


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

    def test_the_first_line_shows_the_value(self):
        core = weave(VALUED_BOOK, "html").output["core/core.html"]
        assert re.search((r'<strong>PARAMETER</strong> <code[^>]*><span class="pre">core\.threads</span></code>'
                          r' = 8 threads</p>'), core)
        assert re.search((r'<strong>PARAMETER</strong> <code[^>]*><span class="pre">core\.turn-width</span></code>'
                          r' = clog2\(core\.threads\) = 3 bits</p>'), core)
        assert re.search(r'<span class="pre">core\.spare</span></code> = 2</p>', core)

    def test_the_latex_shows_the_values_too(self):
        tex = weave(VALUED_BOOK, "latex").output["book.tex"]
        assert (r"one for each of {\hyperref[\detokenize{core/core:core.threads}]"
                r"{\sphinxcrossref{\DUrole{param}{8 threads}}}}") in tex
        assert r"\sphinxcode{\sphinxupquote{core.threads}} = 8 threads" in tex

    def test_a_citation_of_a_parameter_without_a_value_shows_its_anchor(self):
        text = VALUED.replace("   :value: 8\n", "")
        core = weave({**BOOK, "core/core.rst": text}, "html").output["core/core.html"]
        assert re.search((r'one for each of <a class="reference internal" href="#core\.threads"><code[^>]*>'
                          r'<span class="pre">core\.threads</span></code></a>'), core)


TARGETED = VALUED.replace("A thread's instructions", "The aim is :param:`core.aim`. A thread's instructions") + \
    target("core.aim", "core.threads * 2", parent="core.threads", unit="threads", text="The aim of the core.")
TARGETED_BOOK = {**BOOK, "core/core.rst": TARGETED}


@pytest.fixture(scope="module")
def targeted():
    """The page of the core chapter of TARGETED_BOOK, woven as HTML once."""
    return weave(TARGETED_BOOK, "html").output["core/core.html"]


class TargetValueTest:
    """The weave shows the value of a TARGET as it shows the value of a PARAMETER."""

    def test_a_target_is_a_container_whose_id_is_its_anchor(self, targeted):
        assert re.search(r'<div class="chunk target[^"]*" id="core\.aim">', targeted)

    def test_the_first_line_shows_the_value(self, targeted):
        assert re.search((r'<strong>TARGET</strong> <code[^>]*><span class="pre">core\.aim</span></code>'
                          r' = core\.threads \* 2 = 16 threads</p>'), targeted)

    def test_a_citation_shows_the_value_and_unit_as_a_link_to_the_target(self, targeted):
        assert ('The aim is <a class="reference internal" href="#core.aim">'
                '<span class="param">16 threads</span></a>.') in targeted

    def test_the_latex_shows_the_values_too(self):
        tex = weave(TARGETED_BOOK, "latex").output["book.tex"]
        assert (r"The aim is {\hyperref[\detokenize{core/core:core.aim}]"
                r"{\sphinxcrossref{\DUrole{param}{16 threads}}}}") in tex
        assert r"\sphinxcode{\sphinxupquote{core.aim}} = core.threads * 2 = 16 threads" in tex


class ChecksTest:
    def test_the_weave_leaves_the_checks_unchanged(self):
        assert Book({"core/core.rst": GOOD}, general=GENERAL, extensions=["bcw", "weave"]).tuples() == []

    @pytest.mark.parametrize("builder", ["html", "latex"])
    def test_the_weave_gives_no_sphinx_deprecation_warning(self, builder):
        assert deprecations(lambda: weave(BOOK, builder)) == []


# The bar and background of each label in weave.css, or of .chunk where the label sets none.
COLOURS = {"goal": ("7B3FA0", "F7F7F7"), "requirement": ("1F5FBF", "EDF3FC"),
           "parameter": ("0E7C86", "F7F7F7"), "definition": ("2E7D32", "EDF6EE"),
           "rationale": ("8A8A8A", "F7F7F7"), "discussion": ("8A8A8A", "F7F7F7"),
           "target": ("C26A00", "F7F7F7"), "open": ("C26A00", "F7F7F7")}


@pytest.fixture(scope="module")
def tex():
    """BOOK woven as LaTeX, built once for the tests that only read it."""
    return weave(BOOK, "latex").output["book.tex"]


class PdfStyleTest:
    """The PDF sets each chunk apart with the bar colour and background of its label in weave.css."""

    @pytest.mark.parametrize("label, bar, background", [(label, *pair) for label, pair in COLOURS.items()])
    def test_each_label_has_the_colours_of_the_stylesheet(self, tex, label, bar, background):
        assert rf"\definecolor{{bcwbar{label}}}{{HTML}}{{{bar}}}" in tex
        assert rf"\definecolor{{bcwback{label}}}{{HTML}}{{{background}}}" in tex

    @pytest.mark.parametrize("label", LABELS)
    def test_each_label_has_a_box_that_the_class_of_its_container_applies(self, tex, label):
        assert (rf"\newenvironment{{sphinxclass{label}}}{{\begin{{bcwchunk}}{{bcwbar{label}}}"
                rf"{{bcwback{label}}}}}{{\end{{bcwchunk}}}}") in tex

    def test_the_box_holds_the_chunk(self, tex):
        assert after(tex, r"\begin{sphinxuseclass}{requirement}", r"\sphinxstylestrong{REQUIREMENT}",
                     "The core shall give", r"\end{sphinxuseclass}"), tex


FRAGMENTED = (CORE_CHAPTER + "\n.. source:: build/rtl/core/pair.v\n\n"
              "   module pair (input wire a, output wire b);\n       <<core.pair-logic>>\n   endmodule\n"
              "\n.. source:: core.pair-logic\n\n   assign b = a;\n")
FRAGMENTED_BOOK = {**BOOK, "core/core.rst": FRAGMENTED}


@pytest.fixture(scope="module")
def fragmented():
    """The page of the core chapter of FRAGMENTED_BOOK, woven as HTML once."""
    return weave(FRAGMENTED_BOOK, "html").output["core/core.html"]


class FragmentWeaveTest:
    """The weave names each fragment, and links each block that uses fragments to them."""

    def test_a_fragment_is_a_closed_disclosure_named_after_the_fragment(self, fragmented):
        assert re.search(r"(?s)<details><summary>Fragment: core\.pair-logic</summary>.*?assign.*?</details>",
                         fragmented)

    def test_the_first_block_of_a_fragment_carries_its_id(self, fragmented):
        assert 'id="fragment-core.pair-logic"' in fragmented

    def test_a_block_that_uses_fragments_links_to_each(self, fragmented):
        assert re.search(r'<p class="fragment-uses">Uses: <a class="reference internal" '
                         r'href="#fragment-core\.pair-logic"><code[^>]*><span class="pre">core\.pair-logic</span>',
                         fragmented)
        # The line follows the disclosure of its block.
        assert fragmented.index("Verilog: build/rtl/core/pair.v") < fragmented.index('class="fragment-uses"')

    def test_the_latex_links_the_use_to_the_fragment(self):
        tex = weave(FRAGMENTED_BOOK, "latex").output["book.tex"]
        assert r"Uses: {\hyperref[\detokenize{core/core:fragment-core.pair-logic}]" in tex
        assert r"\label{\detokenize{core/core:fragment-core.pair-logic}}" in tex

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

