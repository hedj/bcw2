"""Tests of tools/metrics.py, which counts the lines, McCabe and Halstead metrics of the code of the system with radon."""

import json
import subprocess
import sys

import textstat
from radon.metrics import h_visit

from book import ROOT

METRICS = ROOT / "tools" / "metrics.py"
PLAIN = "def f(x):\n    return x\n"
BRANCH = "def f(x):\n    if x:\n        return 1\n    return x\n"


def measure(root, files):
    """The metrics that tools/metrics.py prints for the files, by path under root."""
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    result = subprocess.run([sys.executable, str(METRICS)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class MetricsTest:
    def test_a_function_without_a_branch_has_mccabe_complexity_1(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": PLAIN})["mccabe"] == 1

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
                                                           "reading_grade": 0, "ste_violations": 0,
                                                           "ste_advisory": 0, "documents": {}}

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
LONG = "The consideration of international collaboration necessitates extraordinary organisational capability.\n"


class DocumentsTest:
    def test_words_in_markdown_leave_out_fenced_blocks_and_inline_code(self, tmp_path):
        text = "Cats run fast.\n\n```\nnot these words here\n```\n\nDogs `x y z` sleep.\n"
        metrics = measure(tmp_path, {"CLAUDE.md": text})
        assert metrics["words"] == 5
        assert metrics["reading_grade"] == textstat.flesch_kincaid_grade("Cats run fast.\n\n\n\nDogs  sleep.\n")

    def test_words_in_rst_leave_out_code_directives_literal_blocks_options_and_underlines(self, tmp_path):
        # Title, Cats run fast., Dogs sleep., Here is code:, Use and timing closure now.
        assert measure(tmp_path, {"book/a/a.rst": RST})["words"] == 14

    def test_readme_build_is_read_as_rst(self, tmp_path):
        text = "Build\n=====\n\nRun this::\n\n    make test\n\nDone.\n"
        assert measure(tmp_path, {"readme.build": text})["words"] == 4

    def test_the_reading_grade_is_that_of_textstat(self, tmp_path):
        text = "The cat sat on the mat. It was a very long and complicated consideration of possibilities.\n"
        assert measure(tmp_path, {"CLAUDE.md": text})["reading_grade"] == textstat.flesch_kincaid_grade(text)

    def test_the_total_reading_grade_is_that_of_all_the_prose_together(self, tmp_path):
        metrics = measure(tmp_path, {"A.md": SIMPLE, "B.md": LONG})
        pooled = textstat.flesch_kincaid_grade(SIMPLE + "\n\n" + LONG)
        mean = (textstat.flesch_kincaid_grade(SIMPLE) + textstat.flesch_kincaid_grade(LONG)) / 2
        assert metrics["reading_grade"] == pooled
        assert pooled != mean

    def test_hard_and_advisory_ste_findings_are_counted_apart(self, tmp_path):
        metrics = measure(tmp_path, {"CLAUDE.md": "Cats run; dogs sleep; birds fly. The file was written today.\n"})
        assert (metrics["ste_violations"], metrics["ste_advisory"]) == (2, 1)

    def test_each_document_has_its_own_measures_and_the_totals_add_up(self, tmp_path):
        metrics = measure(tmp_path, {"A.md": SIMPLE, "B.md": "Cats run; dogs sleep. The file was written today.\n"})
        documents = metrics["documents"]
        assert set(documents) == {"A.md", "B.md"}
        assert documents["A.md"] == {"words": 3, "reading_grade": textstat.flesch_kincaid_grade(SIMPLE),
                                     "ste_violations": 0, "ste_advisory": 0}
        for key in ("words", "ste_violations", "ste_advisory"):
            assert metrics[key] == sum(document[key] for document in documents.values())

    def test_only_the_book_readme_build_and_root_markdown_are_documents(self, tmp_path):
        files = {"tools/notes.md": "Many words here.\n", "docs/other.md": "Not counted.\n", "README.md": "One two.\n",
                 "readme.build": "Three four five.\n", "book/x/y.rst": "Six.\n"}
        metrics = measure(tmp_path, files)
        assert set(metrics["documents"]) == {"README.md", "readme.build", "book/x/y.rst"}
        assert metrics["words"] == 6
