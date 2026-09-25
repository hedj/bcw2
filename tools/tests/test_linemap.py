"""Tests of tools/linemap.py, with real tool output on a tangled chapter."""

import os
import subprocess
import sys
import unittest

from test_entangled import ROOT, VENV_BIN, Project

sys.path.insert(0, str(ROOT / "tools"))

import linemap  # noqa: E402

# The line numbers in the comments on the right are the Markdown lines.
CHAPTER = """\
# Core

Prose.

``` {.verilog file=build/rtl/core/core_pair.v}
module core_pair (input wire a, output wire b);
    assign b = a;
endmodule
```

A second block joins the same file.

``` {.verilog file=build/rtl/core/core_pair.v}
module core_other (input wire c, output wire d);
    assign d = c
endmodule
```

``` {.python file=build/model/twin.py}
def twin(turn):
    return {'next': turn + undefined_name}
```
"""
# Line 5: the first Verilog fence. Line 13: the second. Line 15: the missing ";".
# Line 16: the endmodule where the tools report it. Line 19: the Python fence.
# Line 21: the undefined name.

VERILOG = "build/rtl/core/core_pair.v"
SOURCE = "book/core/core.md"


class LinemapTest(unittest.TestCase):
    def setUp(self):
        self.project = Project(CHAPTER)
        self.addCleanup(self.project.close)
        self.assertEqual(self.project.tangle().returncode, 0)
        cwd = os.getcwd()
        os.chdir(self.project.root)
        self.addCleanup(os.chdir, cwd)

    def filter(self, text):
        result = subprocess.run([str(VENV_BIN / "python"), str(ROOT / "tools" / "linemap.py")],
                                input=text, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_verilator_error_in_the_second_block_maps_to_its_markdown_line(self):
        result = subprocess.run(["verilator", "--lint-only", VERILOG], capture_output=True, text=True)
        self.assertIn(f"%Error: {VERILOG}:9:1: syntax error", result.stderr)
        self.assertIn(f"%Error: {SOURCE}:16:1: syntax error", self.filter(result.stderr))

    def test_iverilog_error_maps_to_its_markdown_line(self):
        result = subprocess.run(["iverilog", "-o", os.devnull, VERILOG], capture_output=True, text=True)
        self.assertIn(f"{VERILOG}:9: syntax error", result.stderr)
        self.assertIn(f"{SOURCE}:16: syntax error", self.filter(result.stderr))

    def test_python_traceback_maps_to_its_markdown_line(self):
        code = "import runpy; runpy.run_path('build/model/twin.py')['twin'](1)"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertIn('File "build/model/twin.py", line 3, in twin', result.stderr)
        self.assertIn(f'File "{SOURCE}", line 21, in twin', self.filter(result.stderr))

    def test_an_absolute_path_maps_like_a_relative_one(self):
        line = f'File "{self.project.root / "build/model/twin.py"}", line 3, in twin'
        self.assertEqual(linemap.rewrite(line), f'File "{SOURCE}", line 21, in twin')

    def test_markers_map_to_the_fences(self):
        self.assertEqual(linemap.lookup(VERILOG, 1), (SOURCE, 5))
        self.assertEqual(linemap.lookup(VERILOG, 5), (SOURCE, 9))
        self.assertEqual(linemap.lookup(VERILOG, 6), (SOURCE, 13))
        self.assertEqual(linemap.lookup(VERILOG, 10), (SOURCE, 17))

    def test_an_unmappable_location_is_kept_with_a_note(self):
        for line in [f"{VERILOG}:99: out of range", "build/rtl/none.v:3: no such file"]:
            self.assertEqual(linemap.rewrite(line), line + linemap.NOTE)

    def test_a_line_without_a_location_is_unchanged(self):
        self.assertEqual(self.filter("%Error: Cannot continue\n"), "%Error: Cannot continue\n")


if __name__ == "__main__":
    unittest.main()
