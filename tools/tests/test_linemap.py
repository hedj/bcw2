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
   <<:core.other>>

A fragment adds a second module to the same file.

.. source:: :core.other

   module core_other (input wire c, output wire d);
       assign d = c
   endmodule
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

    def test_verilator_error_in_the_fragment_maps_to_its_chapter_line(self):
        result = subprocess.run(["verilator", "--lint-only", VERILOG], capture_output=True, text=True)
        assert f"%Error: {VERILOG}:6:1: syntax error" in result.stderr
        assert f"%Error: {SOURCE}:{line(CHAPTER, 'module core_other') + 2}:1: syntax error" in \
            self.filter(result.stderr)

    def test_iverilog_error_maps_to_its_chapter_line(self):
        result = subprocess.run(["iverilog", "-o", os.devnull, VERILOG], capture_output=True, text=True)
        assert f"{VERILOG}:6: syntax error" in result.stderr
        assert f"{SOURCE}:{line(CHAPTER, 'module core_other') + 2}: syntax error" in self.filter(result.stderr)

    def test_an_absolute_path_in_a_tool_message_maps_like_a_relative_one(self):
        text = f"%Error: {self.root / VERILOG}:3:1: x"
        assert linemap.rewrite(text) == f"%Error: {SOURCE}:{line(CHAPTER, 'endmodule')}:1: x"

    def test_each_line_maps_to_its_chapter_line(self):
        assert linemap.lookup(VERILOG, 1) == (SOURCE, line(CHAPTER, "module core_pair"))
        assert linemap.lookup(VERILOG, 3) == (SOURCE, line(CHAPTER, "endmodule"))
        assert linemap.lookup(VERILOG, 4) == (SOURCE, line(CHAPTER, "module core_other"))

    def test_the_tangled_file_holds_no_marker(self):
        assert "bcw:" not in (self.root / VERILOG).read_text()

    def test_a_line_that_no_chapter_line_holds_maps_to_nothing(self):
        assert linemap.lookup("build/rtl/bcw_params.sv", 1) is None

    def test_a_file_without_a_map_maps_to_nothing(self, tmp_path):
        (tmp_path / "loose.v").write_text("module loose;\nendmodule\n")
        assert linemap.lookup(str(tmp_path / "loose.v"), 1) is None

    def test_an_unmappable_location_is_kept_with_a_note(self):
        for text in [f"{VERILOG}:99: out of range", "build/rtl/none.v:3: no such file"]:
            assert linemap.rewrite(text) == text + linemap.NOTE

    def test_a_range_maps_both_of_its_lines(self):
        # yosys and SymbiYosys give a place as line.column-line.column.
        first, last = line(CHAPTER, "module core_pair"), line(CHAPTER, "endmodule")
        assert linemap.rewrite(f"Assert failed in m: {VERILOG}:1.5-3.9 (x)") == \
            f"Assert failed in m: {SOURCE}:{first}.5-{last}.9 (x)"

    def test_a_range_with_an_unmappable_end_is_kept_with_a_note(self):
        assert linemap.rewrite(f"{VERILOG}:1.5-99.9") == f"{VERILOG}:1.5-99.9" + linemap.NOTE

    def test_a_line_without_a_location_is_unchanged(self):
        assert self.filter("%Error: Cannot continue\n") == "%Error: Cannot continue\n"


def test_a_range_across_two_chapters_is_kept_with_a_note(tmp_path, monkeypatch):
    # A fragment from another chapter can put the two ends of a range in two chapters.
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "tangle.json").write_text(
        '{"files": {"checks/x.sv": {"sha256": "", "lines": [["book/a/a.rst", 5], ["book/b/b.rst", 9]]}}}')
    monkeypatch.chdir(tmp_path)
    assert linemap.rewrite("build/checks/x.sv:1.1-2.3") == "build/checks/x.sv:1.1-2.3" + linemap.NOTE


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
