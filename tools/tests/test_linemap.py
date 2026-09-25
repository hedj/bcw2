"""Tests of tools/linemap.py, with real tool output on a chapter that tools/bcw.py tangles."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_bcw import ROOT, Book, line

sys.path.insert(0, str(ROOT / "tools"))

import linemap  # noqa: E402

CHAPTER = """\
:kind: reference

====
Core
====

Overview
========

Prose.

Pair
====

.. source:: build/rtl/core/core_pair.v

   module core_pair (input wire a, output wire b);
       assign b = a;
   endmodule

A second block joins the same file.

.. source:: build/rtl/core/core_pair.v

   module core_other (input wire c, output wire d);
       assign d = c
   endmodule

.. source:: build/model/twin.py

   def twin(turn):
       return {'next': turn + undefined_name}
"""

VERILOG = "build/rtl/core/core_pair.v"
SOURCE = "book/core/core.rst"


class LinemapTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name, text in Book({"core/core.rst": CHAPTER}, tangle=True).files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text)
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

    def filter(self, text):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "linemap.py")],
                                input=text, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_verilator_error_in_the_second_block_maps_to_its_chapter_line(self):
        result = subprocess.run(["verilator", "--lint-only", VERILOG], capture_output=True, text=True)
        self.assertIn(f"%Error: {VERILOG}:8:1: syntax error", result.stderr)
        self.assertIn(f"%Error: {SOURCE}:{line(CHAPTER, 'module core_other') + 2}:1: syntax error",
                      self.filter(result.stderr))

    def test_iverilog_error_maps_to_its_chapter_line(self):
        result = subprocess.run(["iverilog", "-o", os.devnull, VERILOG], capture_output=True, text=True)
        self.assertIn(f"{VERILOG}:8: syntax error", result.stderr)
        self.assertIn(f"{SOURCE}:{line(CHAPTER, 'module core_other') + 2}: syntax error", self.filter(result.stderr))

    def test_python_traceback_maps_to_its_chapter_line(self):
        code = "import runpy; runpy.run_path('build/model/twin.py')['twin'](1)"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertIn('File "build/model/twin.py", line 3, in twin', result.stderr)
        self.assertIn(f'File "{SOURCE}", line {line(CHAPTER, "undefined_name")}, in twin', self.filter(result.stderr))

    def test_an_absolute_path_maps_like_a_relative_one(self):
        text = f'File "{self.root / "build/model/twin.py"}", line 3, in twin'
        self.assertEqual(linemap.rewrite(text), f'File "{SOURCE}", line {line(CHAPTER, "undefined_name")}, in twin')

    def test_each_line_after_a_marker_maps_to_its_chapter_line(self):
        self.assertEqual(linemap.lookup(VERILOG, 2), (SOURCE, line(CHAPTER, "module core_pair")))
        self.assertEqual(linemap.lookup(VERILOG, 4), (SOURCE, line(CHAPTER, "endmodule")))
        self.assertEqual(linemap.lookup(VERILOG, 6), (SOURCE, line(CHAPTER, "module core_other")))

    def test_a_marker_line_maps_to_nothing(self):
        self.assertEqual([linemap.lookup(VERILOG, number) for number in (1, 5)], [None, None])

    def test_an_unmappable_location_is_kept_with_a_note(self):
        for text in [f"{VERILOG}:99: out of range", "build/rtl/none.v:3: no such file"]:
            self.assertEqual(linemap.rewrite(text), text + linemap.NOTE)

    def test_a_line_without_a_location_is_unchanged(self):
        self.assertEqual(self.filter("%Error: Cannot continue\n"), "%Error: Cannot continue\n")


if __name__ == "__main__":
    unittest.main()
