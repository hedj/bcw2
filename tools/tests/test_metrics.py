"""Tests of tools/metrics.py, which counts the lines, McCabe and Halstead metrics of the code of the system with radon."""

import contextlib
import io
import json
import os
import runpy
import sys
from unittest import mock

from radon.metrics import h_visit

from book import ROOT

METRICS = ROOT / "tools" / "metrics.py"
PLAIN = "def f(x):\n    return x\n"
BRANCH = "def f(x):\n    if x:\n        return 1\n    return x\n"


def run(root, *arguments):
    """What tools/metrics.py prints when it runs in root with the arguments.

    It runs in this process, not in a new one, so that a test does not start Python and
    import radon again.
    """
    output, previous = io.StringIO(), os.getcwd()
    os.chdir(root)
    try:
        with mock.patch.object(sys, "argv", [str(METRICS), *arguments]), contextlib.redirect_stdout(output):
            runpy.run_path(str(METRICS), run_name="__main__")
    finally:
        os.chdir(previous)
    return output.getvalue()


def compare(root, before):
    """The rows of the table that tools/metrics.py --compare prints for root, by measure name."""
    path = root / "before.json"
    path.write_text(json.dumps(before))
    return {line.split()[0]: line for line in run(root, "--compare", str(path)).splitlines()[1:] if line.strip()}


def measure(root, files):
    """The metrics that tools/metrics.py prints for the files, by path under root."""
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return json.loads(run(root))


class MetricsTest:
    def test_a_branch_adds_1_to_mccabe_complexity(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": BRANCH})["mccabe"] == 2

    def test_the_methods_of_a_class_count(self, tmp_path):
        text = "class C:\n    def f(self, x):\n        if x:\n            return 1\n        return x\n"
        assert measure(tmp_path, {"tools/a.py": text})["mccabe"] == 2

    def test_a_nested_function_counts(self, tmp_path):
        text = "def f(x):\n    def g(y):\n        if y:\n            return 1\n        return 2\n    return g(x)\n"
        assert measure(tmp_path, {"tools/a.py": text})["mccabe"] == 3

    def test_the_files_add_up(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": PLAIN, "tools/b.py": BRANCH})["mccabe"] == 3

    def test_the_tests_are_left_out(self, tmp_path):
        metrics = measure(tmp_path, {"tools/a.py": PLAIN, "tools/tests/test_a.py": BRANCH})
        assert metrics["mccabe"] == 1

    def test_the_halstead_measures_are_those_of_radon(self, tmp_path):
        text = "def f(x, y):\n    return (x + y) * (x - y) // 2\n"
        total = h_visit(text).total
        assert measure(tmp_path, {"tools/a.py": text}) == {"lines": 2, "mccabe": 1, "halstead_volume": total.volume,
                                                           "halstead_effort": total.effort, "words": 0,
                                                           "ste_violations": 0,
                                                           "ste_advisory": 0, "audit_days": 0, "documents": {},
                                                           "design": None}

    def test_lines_of_code_leave_out_blank_lines_comments_and_docstrings(self, tmp_path):
        text = ('"""A module\ndocstring."""\n\nimport os\n\n\n# A comment.\ndef f(x):\n    """One line."""\n'
                "    y = x + 1  # a comment after code\n    return y\n")
        assert measure(tmp_path, {"tools/a.py": text})["lines"] == 4

    def test_the_lines_of_the_files_add_up_without_the_tests(self, tmp_path):
        files = {"tools/a.py": PLAIN, "tools/b.py": BRANCH, "tools/tests/test_a.py": BRANCH}
        assert measure(tmp_path, files)["lines"] == 6


RST = """Title
=====

Cats run fast.

.. source:: a.v

   module words here

.. requirement:: a.b
   :parent: a.c

   Dogs sleep.

Here is code::

   hidden words

.. check:: test
   :verifies: a.b

   more hidden

.. code-block:: python

   x = 1

Use ``make test`` and :term:`timing closure` now.
"""
SIMPLE = "Go now. Run.\n"


class DocumentsTest:
    def test_words_in_markdown_leave_out_fenced_blocks_and_inline_code(self, tmp_path):
        text = "Cats run fast.\n\n```\nnot these words here\n```\n\nDogs `x y z` sleep.\n"
        metrics = measure(tmp_path, {"CLAUDE.md": text})
        assert metrics["words"] == 5
        assert metrics["documents"]["CLAUDE.md"]["code_lines"] == 1

    def test_words_in_rst_leave_out_code_directives_literal_blocks_options_and_underlines(self, tmp_path):
        # Title, Cats run fast., Dogs sleep., Here is code:, Use and timing closure now.
        assert measure(tmp_path, {"book/a/a.rst": RST})["words"] == 14

    def test_code_lines_in_rst_are_the_lines_of_code_directives_and_literal_blocks_without_options(self, tmp_path):
        # module words here, hidden words, more hidden, x = 1
        assert measure(tmp_path, {"book/a/a.rst": RST})["documents"]["book/a/a.rst"]["code_lines"] == 4

    def test_a_mutant_is_code_not_prose(self, tmp_path):
        text = ".. mutant:: build/a.v\n   :kills: a.b.test\n\n   -    assign a = b;\n   +    assign a = c;\n"
        document = measure(tmp_path, {"book/a/a.rst": text})["documents"]["book/a/a.rst"]
        assert (document["words"], document["code_lines"]) == (0, 2)

    def test_the_audit_time_counts_the_words_and_code_lines_of_the_book_alone(self, tmp_path):
        files = {"book/a/a.rst": RST, "readme.build": "Three four five.\n", "CLAUDE.md": "One two.\n"}
        assert measure(tmp_path, files)["audit_days"] == (14 + 4) / 1200

    def test_readme_build_is_read_as_rst(self, tmp_path):
        text = "Build\n=====\n\nRun this::\n\n    make test\n\nDone.\n"
        assert measure(tmp_path, {"readme.build": text})["words"] == 4

    def test_hard_and_advisory_ste_findings_are_counted_apart(self, tmp_path):
        metrics = measure(tmp_path, {"CLAUDE.md": "Cats run; dogs sleep; birds fly. The file was written today.\n"})
        assert (metrics["ste_violations"], metrics["ste_advisory"]) == (2, 1)

    def test_each_document_has_its_own_measures_and_the_totals_add_up(self, tmp_path):
        metrics = measure(tmp_path, {"A.md": SIMPLE, "B.md": "Cats run; dogs sleep. The file was written today.\n"})
        documents = metrics["documents"]
        assert set(documents) == {"A.md", "B.md"}
        assert documents["A.md"] == {"words": 3, "code_lines": 0, "ste_violations": 0, "ste_advisory": 0}
        for key in ("words", "ste_violations", "ste_advisory"):
            assert metrics[key] == sum(document[key] for document in documents.values())

    def test_only_the_book_readme_build_and_root_markdown_are_documents(self, tmp_path):
        files = {"tools/notes.md": "Many words here.\n", "docs/other.md": "Not counted.\n", "README.md": "One two.\n",
                 "readme.build": "Three four five.\n", "book/x/y.rst": "Six.\n"}
        metrics = measure(tmp_path, files)
        assert set(metrics["documents"]) == {"README.md", "readme.build", "book/x/y.rst"}
        assert metrics["words"] == 6


def node(anchor, position, label="REQUIREMENT", chapter="core", live=0):
    return {"anchor": anchor, "label": label, "chapter": chapter, "position": position, "live": live}


def design(tmp_path, nodes, edges, unimplemented=(), unverified=()):
    """The design section that tools/metrics.py prints for a design graph in build/design.json."""
    graph = {"nodes": nodes, "edges": edges, "unimplemented": list(unimplemented), "unverified": list(unverified)}
    return measure(tmp_path, {"build/design.json": json.dumps(graph)})["design"]


class DesignTest:
    def test_interactivity_counts_the_distinct_elements_that_an_element_needs(self, tmp_path):
        nodes = [node("a", 0), node("p", 1, "GOAL"), node("t", 2, "DEFINITION"), node("u", 3, "DEFINITION")]
        edges = [["a", "p", "parent"], ["a", "t", "term"], ["a", "u", "term"], ["a", "u", "citation"]]
        result = design(tmp_path, nodes, edges)
        assert (result["elements"], result["interactivity_max"], result["interactivity_mean"]) == (4, 3, 0.75)

    def test_an_element_that_needs_more_than_4_elements_is_an_overload(self, tmp_path):
        nodes = [node("a", 0)] + [node(f"n{i}", i + 1, "DEFINITION") for i in range(5)]
        edges = [["a", f"n{i}", "term"] for i in range(5)]
        result = design(tmp_path, nodes, edges)
        assert (result["overload"], result["overloaded"]) == (1, ["a"])
        assert design(tmp_path, nodes, edges[:4])["overload"] == 0

    def test_the_propagation_cost_is_the_mean_share_of_elements_that_depend_on_each_element(self, tmp_path):
        # c needs b and b needs a: a change to a reaches b and c, a change to b reaches c.
        nodes = [node("a", 0), node("b", 1), node("c", 2)]
        result = design(tmp_path, nodes, [["b", "a", "parent"], ["c", "b", "parent"]])
        assert result["propagation_cost"] == (2 + 1 + 0) / 3 / 3

    def test_the_live_peak_and_mean_are_those_of_the_live_sets_that_bcw_gives(self, tmp_path):
        nodes = [node("t", 0, "DEFINITION", live=0), node("x", 1, live=2), node("y", 2, live=1)]
        result = design(tmp_path, nodes, [["y", "t", "term"]])
        assert (result["live_peak"], result["live_mean"]) == (2, 1)

    def test_a_need_of_a_later_element_is_a_forward_reference(self, tmp_path):
        nodes = [node("a", 0), node("b", 1), node("c", 2)]
        result = design(tmp_path, nodes, [["a", "c", "citation"], ["c", "b", "parent"], ["b", "a", "parent"]])
        assert result["forward_references"] == 1

    def test_the_vocabulary_counts_the_defined_terms_that_each_chapter_uses(self, tmp_path):
        nodes = [node("t", 0, "DEFINITION", "design"), node("u", 1, "DEFINITION", "design"),
                 node("a", 2, chapter="core"), node("b", 3, chapter="core"), node("c", 4, chapter="memory")]
        edges = [["a", "t", "term"], ["b", "t", "term"], ["b", "u", "term"], ["c", "u", "term"], ["c", "a", "parent"]]
        result = design(tmp_path, nodes, edges)
        assert result["vocabulary"] == {"core": 2, "memory": 1}
        assert result["vocabulary_total"] == 2

    def test_requirements_without_an_implementation_or_a_check_are_orphans(self, tmp_path):
        nodes = [node("a", 0), node("b", 1), node("g", 2, "GOAL")]
        result = design(tmp_path, nodes, [], unimplemented=["b"], unverified=["a", "b"])
        assert (result["unimplemented"], result["unverified"]) == (1, 2)

    def test_without_a_design_graph_there_is_no_design_section(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": PLAIN})["design"] is None


class CompareTest:
    def test_a_measure_that_rose_is_marked_worse(self, tmp_path):
        before = measure(tmp_path, {"CLAUDE.md": "One.\n"})
        (tmp_path / "CLAUDE.md").write_text("One two three.\n")
        row = compare(tmp_path, before)["words"]
        assert row.split()[1:4] == ["1", "3", "+2"]
        assert row.split()[-1] == "worse"

    def test_a_measure_that_fell_is_not_marked(self, tmp_path):
        before = measure(tmp_path, {"tools/a.py": BRANCH})
        (tmp_path / "tools" / "a.py").write_text(PLAIN)
        row = compare(tmp_path, before)["mccabe"]
        assert row.split()[1:] == ["2", "1", "-1"]

    def test_an_equal_measure_is_not_marked(self, tmp_path):
        before = measure(tmp_path, {"tools/a.py": PLAIN})
        assert compare(tmp_path, before)["lines"].split()[1:] == ["2", "2", "+0"]

    def test_each_scalar_measure_has_a_row(self, tmp_path):
        rows = compare(tmp_path, measure(tmp_path, {"tools/a.py": PLAIN}))
        assert list(rows) == ["lines", "mccabe", "halstead_volume", "halstead_effort", "words", "ste_violations",
                              "ste_advisory", "audit_days", "interactivity_mean", "interactivity_max", "overload",
                              "propagation_cost", "live_peak", "live_mean", "forward_references", "vocabulary_total",
                              "unimplemented", "unverified"]

    def test_a_design_measure_without_a_graph_is_none(self, tmp_path):
        rows = compare(tmp_path, measure(tmp_path, {"tools/a.py": PLAIN}))
        assert rows["live_peak"].split()[1:] == ["none", "none"]

    def test_a_design_measure_is_compared_when_both_sides_have_a_graph(self, tmp_path):
        graph = {"nodes": [node("a", 0), node("t", 1, "DEFINITION")], "edges": [], "unimplemented": [],
                 "unverified": ["a"]}
        before = measure(tmp_path, {"build/design.json": json.dumps(graph)})
        graph["unverified"] = []
        (tmp_path / "build" / "design.json").write_text(json.dumps(graph))
        assert compare(tmp_path, before)["unverified"].split()[1:] == ["1", "0", "-1"]
