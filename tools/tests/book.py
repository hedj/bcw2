"""Helpers of the tests of tools/: a chapter that obeys every rule, and a book built from it.

GOOD is a small chapter that obeys every documentation rule. A test changes
one thing in it and expects the findings of the rule that the change breaks.
The helper line() finds a line number by its text, so that the tests do not
depend on the layout of GOOD. Book builds a Sphinx book in a temporary folder,
with each chapter at its path under book/.
"""

import hashlib
import io
import json
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.util.console import nocolor
from sphinx.util.docutils import docutils_namespace

import bcw

ROOT = Path(__file__).resolve().parents[2]

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
          return {{'next': (turn + 1) % 8}}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [2:0] turn, output wire [2:0] next);
       assign next = turn + 3'd1;
   endmodule

.. check:: equiv
   :verifies: core.rotation
   :module: core_rotate

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


def line(text, needle, after=None):
    """The 1-based number of the first line of text that holds needle.

    With after, the first such line below the first line that holds after.
    """
    start = line(text, after) if after is not None else 0
    return next(number for number, content in enumerate(text.splitlines(), 1)
                if number > start and needle in content)


class Book:
    """A book built in a temporary folder with the extension.

    chapters maps each path under book/ to its text. general and retired are
    sets of words and anchors, or None for no list file. tools maps the name of
    each file in tools/ to its text. With tangle, the tangle writes under the
    temporary folder. builder names the Sphinx builder, and output keeps the text
    of each HTML, CSS and LaTeX file that it writes. index replaces the index, which
    lists the chapters by default. With pdf, latexmk makes a PDF of the LaTeX,
    and pdf keeps its exit status and the size of the PDF. With root, the book is
    built in that folder, which stays after the build, so that a test can build
    twice in one folder.
    """

    def __init__(self, chapters, general=None, retired=None, tools=None, tangle=False, builder="dummy",
                 index=None, pdf=False, root=None, **overrides):
        directory = tempfile.TemporaryDirectory() if root is None else None
        self.root = Path(directory.name if root is None else root)
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
                self.resolved = {name: app.env.get_and_resolve_doctree(name, app.builder, tags=app.builder.tags)
                                 for name in sorted(app.env.found_docs)}
            self.findings = app.env.bcw_findings
            self.values = app.env.bcw_values
            self.model = bcw.model(app.env)
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
            if directory is not None:
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


def deprecations(build):
    """The message of each warning of a Sphinx deprecation that build() gives."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        build()
    return [str(warning.message) for warning in caught if warning.category.__name__.startswith("RemovedInSphinx")]


def findings(text, retired=None, tools=None, general=None):
    """The findings on text as the chapter book/core/core.rst, as (line, check, anchor).

    With general=None, the extension skips doc.known-words, so that a test of
    another rule can add new words.
    """
    return [(number, name, anchor) for path, number, name, anchor
            in Book({"core/core.rst": text}, general, retired, tools).tuples()]


def only(check_name, text, **options):
    return [f for f in findings(text, **options) if f[1] == check_name]


def chapter(title, kind="reference", body=""):
    rule = "=" * len(title)
    return f":kind: {kind}\n\n{rule}\n{title}\n{rule}\n\nOverview\n========\n\nText.\n{body}"


DESIGN = chapter("Design", body="\nGoals\n=====\n\n.. goal:: design.timing\n\n   No thread can change the timing.\n")
CORE_CHAPTER = GOOD.replace(":parent: core.timing", ":parent: design.timing")


def parameter(anchor, value, parent="core.core", unit=None, text="The number of threads."):
    """A PARAMETER chunk to add at the end of GOOD. value None leaves out the value option."""
    lines = [f"\n.. parameter:: {anchor}", f"   :parent: {parent}"]
    lines += [f"   :value: {value}"] if value is not None else []
    lines += [f"   :unit: {unit}"] if unit else []
    return "\n".join(lines) + f"\n\n   {text}\n"


THREADS = parameter("core.threads", "8", unit="threads")
WIDTH = parameter("core.turn-width", "clog2(core.threads)", parent="core.threads", unit="bits",
                  text="The width of the index of a thread.")


def target(anchor, value, parent="core.core", unit=None, text="The number of threads."):
    """A TARGET chunk to add at the end of GOOD. value or parent None leaves out that option."""
    lines = [f"\n.. target:: {anchor}"]
    lines += [f"   :parent: {parent}"] if parent is not None else []
    lines += [f"   :value: {value}"] if value is not None else []
    lines += [f"   :unit: {unit}"] if unit else []
    return "\n".join(lines) + f"\n\n   {text}\n"


def tangled(files, path):
    """(text, chapter path, chapter line) of each line of the tangled file at path.

    The text comes from the file, and the chapter line from build/tangle.json, whose
    keys are relative to build/. A line that no chapter line holds gives None twice.
    """
    entries = json.loads(files["build/tangle.json"])["files"][path.removeprefix("build/")]["lines"]
    texts = files[path].splitlines()
    assert len(entries) == len(texts), (path, len(entries), len(texts))
    return [(text, *(entry or (None, None))) for text, entry in zip(texts, entries)]
