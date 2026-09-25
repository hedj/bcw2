"""What Sphinx 9.0.4 and docutils 0.22.4 do with this repository's source form.

These tests record the behaviours that the book's Sphinx extension relies on.
Each one builds a small book in a temporary folder. If a later Sphinx changes
one of these behaviours, its test fails.
"""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.console import nocolor
from sphinx.util.docutils import SphinxDirective, docutils_namespace

INDEX = "Book\n====\n\n.. toctree::\n   :glob:\n\n   */*\n"
CHAPTER = """\
:kind: reference

====
Core
====

Overview
========

A :dfn:`thread` runs.
"""

nocolor()


class Requirement(SphinxDirective):
    required_arguments = 1
    has_content = True
    option_spec = {"parent": directives.unchanged}

    def run(self):
        return []


def extension(app):
    app.add_directive("requirement", Requirement)


def build(root, text, setup=extension, fresh=True):
    """Build book/core/core.rst under root with the dummy builder.

    Returns the warnings, with the source folder written as "book", and the environment.
    docutils_namespace resets the global registry of directives and nodes after the
    build, as sphinx-build does, so that one build does not leak into the next.
    """
    source = Path(root) / "book"
    (source / "core").mkdir(parents=True, exist_ok=True)
    for path, content in [(source / "core" / "core.rst", text), (source / "index.rst", INDEX)]:
        if not path.exists() or path.read_text() != content:
            path.write_text(content)
    warnings = io.StringIO()
    with docutils_namespace():
        app = Sphinx(str(source), None, str(Path(root) / "out"), str(Path(root) / "doctrees"), "dummy",
                     status=None, warning=warnings, freshenv=fresh)
        setup(app)
        app.build()
    return warnings.getvalue().replace(str(source), "book"), app.env


class SphinxTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = directory.name

    def test_a_clean_chapter_gives_no_warning(self):
        self.assertEqual(build(self.root, CHAPTER)[0], "")

    def test_an_unknown_directive_is_an_error_on_its_line(self):
        warnings = build(self.root, CHAPTER + "\n.. nosuch:: x\n")[0]
        self.assertIn('book/core/core.rst:12: ERROR: Unknown directive type "nosuch".', warnings)

    def test_an_unknown_option_is_an_error_on_the_directive_line(self):
        warnings = build(self.root, CHAPTER + "\n.. requirement:: core.x\n   :parnet: y\n\n   Text.\n")[0]
        self.assertIn('book/core/core.rst:12: ERROR: Error in "requirement" directive:\n'
                      'unknown option: "parnet".', warnings)

    def test_dfn_gives_an_emphasis_node_with_the_class_dfn(self):
        doctree = build(self.root, CHAPTER)[1].get_doctree("core/core")
        found = [(node.tagname, node["classes"], node.astext()) for node in doctree.findall(nodes.emphasis)]
        self.assertEqual(found, [("emphasis", ["dfn"], "thread")])

    def test_a_field_list_at_the_start_is_metadata(self):
        self.assertEqual(build(self.root, CHAPTER)[1].metadata["core/core"], {"kind": "reference"})

    def test_a_logged_warning_carries_its_file_and_line(self):
        def setup(app):
            def warn(app, doctree):
                logging.getLogger("bcw").warning("[check] core.x: message", location=(app.env.docname, 5))
            app.connect("doctree-read", warn)
        self.assertIn("book/core/core.rst:5: WARNING: [check] core.x: message", build(self.root, CHAPTER, setup)[0])

    def test_a_second_build_does_not_read_an_unchanged_chapter_again(self):
        text = CHAPTER + "\n.. nosuch:: x\n"
        self.assertIn("nosuch", build(self.root, text, fresh=False)[0])
        self.assertEqual(build(self.root, text, fresh=False)[0], "")

    def test_w_and_keep_going_exit_1_on_a_warning_and_0_without(self):
        source = Path(self.root) / "book"
        build(self.root, CHAPTER)
        (Path(self.root) / "conf.py").write_text("")
        command = [sys.executable, "-m", "sphinx", "-E", "-q", "-W", "--keep-going", "-b", "dummy",
                   "-c", self.root, str(source), str(Path(self.root) / "out")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        (source / "core" / "core.rst").write_text(CHAPTER + "\n.. nosuch:: x\n")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
