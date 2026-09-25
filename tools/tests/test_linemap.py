"""Tests of tools/linemap.py, with real tool output on a chapter that tools/bcw.py tangles."""

import os
import subprocess
import sys

import pytest

import linemap
from book import ROOT, Book, line

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


class LinemapTest:
    @pytest.fixture(scope="class")
    def tangled(self):
        """The files that the tangle writes for CHAPTER, built once for the class."""
        return Book({"core/core.rst": CHAPTER}, tangle=True).files

    @pytest.fixture(autouse=True)
    def root(self, tangled, tmp_path, monkeypatch):
        """Each test runs in its own folder that holds the tangled files."""
        for name, text in tangled.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text)
        monkeypatch.chdir(tmp_path)
        self.root = tmp_path

    def filter(self, text):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "linemap.py")],
                                input=text, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def test_verilator_error_in_the_second_block_maps_to_its_chapter_line(self):
        result = subprocess.run(["verilator", "--lint-only", VERILOG], capture_output=True, text=True)
        assert f"%Error: {VERILOG}:8:1: syntax error" in result.stderr
        assert f"%Error: {SOURCE}:{line(CHAPTER, 'module core_other') + 2}:1: syntax error" in \
            self.filter(result.stderr)

    def test_iverilog_error_maps_to_its_chapter_line(self):
        result = subprocess.run(["iverilog", "-o", os.devnull, VERILOG], capture_output=True, text=True)
        assert f"{VERILOG}:8: syntax error" in result.stderr
        assert f"{SOURCE}:{line(CHAPTER, 'module core_other') + 2}: syntax error" in self.filter(result.stderr)

    def test_python_traceback_maps_to_its_chapter_line(self):
        code = "import runpy; runpy.run_path('build/model/twin.py')['twin'](1)"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert 'File "build/model/twin.py", line 3, in twin' in result.stderr
        assert f'File "{SOURCE}", line {line(CHAPTER, "undefined_name")}, in twin' in self.filter(result.stderr)

    def test_an_absolute_path_maps_like_a_relative_one(self):
        text = f'File "{self.root / "build/model/twin.py"}", line 3, in twin'
        assert linemap.rewrite(text) == f'File "{SOURCE}", line {line(CHAPTER, "undefined_name")}, in twin'

    def test_each_line_after_a_marker_maps_to_its_chapter_line(self):
        assert linemap.lookup(VERILOG, 2) == (SOURCE, line(CHAPTER, "module core_pair"))
        assert linemap.lookup(VERILOG, 4) == (SOURCE, line(CHAPTER, "endmodule"))
        assert linemap.lookup(VERILOG, 6) == (SOURCE, line(CHAPTER, "module core_other"))

    def test_a_marker_line_maps_to_nothing(self):
        assert [linemap.lookup(VERILOG, number) for number in (1, 5)] == [None, None]

    def test_an_unmappable_location_is_kept_with_a_note(self):
        for text in [f"{VERILOG}:99: out of range", "build/rtl/none.v:3: no such file"]:
            assert linemap.rewrite(text) == text + linemap.NOTE

    def test_a_line_without_a_location_is_unchanged(self):
        assert self.filter("%Error: Cannot continue\n") == "%Error: Cannot continue\n"


FRAGMENTS = """\
:kind: reference

====
Core
====

Overview
========

Prose.

Three
=====

.. source:: build/rtl/core/core_three.v

   module core_three (input wire a, output wire b, output wire c);
       <<:core.three-logic>>
       assign c = missing_two;
   endmodule

.. source:: :core.three-logic

   assign b = missing_one;
"""


class FragmentLinemapTest:
    """A Verilator error inside a fragment, or after one, maps to its own chapter line."""

    def test_each_error_maps_to_the_line_that_holds_it(self, tmp_path, monkeypatch):
        for name, text in Book({"core/core.rst": FRAGMENTS}, tangle=True).files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text)
        monkeypatch.chdir(tmp_path)
        result = subprocess.run(["verilator", "--lint-only", "build/rtl/core/core_three.v"],
                                capture_output=True, text=True)
        mapped = subprocess.run([sys.executable, str(ROOT / "tools" / "linemap.py")], input=result.stderr,
                                capture_output=True, text=True).stdout
        assert f"{SOURCE}:{line(FRAGMENTS, 'missing_one')}:" in mapped, mapped
        assert f"{SOURCE}:{line(FRAGMENTS, 'missing_two')}:" in mapped, mapped
