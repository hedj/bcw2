"""What entangled 2.1.13 does with this repository's source form.

These tests record the results of the experiment of step 1 of the tooling
plan. Each one runs the pinned tools on a small chapter in a temporary
project. If a later entangled changes one of these behaviours, its test fails.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_BIN = ROOT / ".venv" / "bin"
sys.path.insert(0, str(ROOT / "tools"))

import tangle  # noqa: E402

CHAPTER = """\
# Core

**REQUIREMENT.** Rotation shall be fixed and unconditional.
{rule=core.rotation}

``` {.python .formal file=build/model/core_rotate.py stamp=1a2b3c4d}
def core_rotate(turn):
    return {'next': turn + 1}
```

``` {.verilog file=build/rtl/core/core_rotate.v implements=core.rotation}
module core_rotate (input wire [2:0] turn, output wire [2:0] next);
    assign next = turn + 3'd1;
endmodule
```

A second block joins the same file.

``` {.verilog file=build/rtl/core/core_rotate.v}
// A comment line.
```
"""

VERILOG = "build/rtl/core/core_rotate.v"
MODEL = "build/model/core_rotate.py"


class Project:
    """A temporary project with the repository's entangled.toml and one chapter."""

    def __init__(self, chapter):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        shutil.copy(ROOT / "entangled.toml", self.root)
        self.chapter = self.root / "book" / "core" / "core.md"
        self.chapter.parent.mkdir(parents=True)
        self.chapter.write_text(chapter)

    def run(self, *args):
        return subprocess.run(
            args, cwd=self.root, capture_output=True, text=True
        )

    def entangled(self):
        return self.run(str(VENV_BIN / "entangled"), "tangle")

    def tangle(self):
        return self.run(str(VENV_BIN / "python"), str(ROOT / "tools" / "tangle.py"))

    def read(self, name):
        return (self.root / name).read_text()

    def close(self):
        self.dir.cleanup()


class EntangledTest(unittest.TestCase):
    def project(self, chapter=CHAPTER):
        project = Project(chapter)
        self.addCleanup(project.close)
        return project

    def test_extra_attributes_and_classes_are_ignored(self):
        project = self.project()
        result = project.tangle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("return {'next': turn + 1}", project.read(MODEL))
        self.assertIn("assign next = turn + 3'd1;", project.read(VERILOG))

    def test_markers_name_the_source_file_block_and_position(self):
        project = self.project()
        project.tangle()
        lines = project.read(VERILOG).splitlines()
        self.assertEqual(
            lines[0], "// ~/~ begin <<book/core/core.md#" + VERILOG + ">>[init]"
        )
        self.assertEqual(lines[4], "// ~/~ end")
        self.assertEqual(
            lines[5], "// ~/~ begin <<book/core/core.md#" + VERILOG + ">>[1]"
        )
        self.assertEqual(project.read(MODEL).splitlines()[0][:12], "# ~/~ begin ")

    def test_entangled_omits_the_final_newline_when_it_creates_a_file(self):
        project = self.project()
        result = project.entangled()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(project.read(VERILOG).endswith("\n"))

    def test_tangle_ends_every_tangled_file_with_a_newline(self):
        project = self.project()
        project.tangle()
        self.assertTrue(project.read(VERILOG).endswith("// ~/~ end\n"))
        self.assertTrue(project.read(MODEL).endswith("# ~/~ end\n"))

    def test_retangle_after_the_newline_fix_reports_no_conflict(self):
        project = self.project()
        project.tangle()
        project.chapter.write_text(CHAPTER.replace("3'd1", "3'd2"))
        later = (project.root / VERILOG).stat().st_mtime + 2
        os.utime(project.chapter, (later, later))
        result = project.tangle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3'd2", project.read(VERILOG))

    def test_verilator_accepts_the_tangled_file(self):
        project = self.project()
        project.tangle()
        result = project.run("verilator", "--lint-only", "-Wall", VERILOG)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verilator_reports_the_tangled_file_and_line(self):
        project = self.project(CHAPTER.replace("3'd1;", "3'd1"))
        project.tangle()
        result = project.run("verilator", "--lint-only", "-Wall", VERILOG)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("%Error: " + VERILOG + ":4:1: syntax error", result.stderr)


class AddFinalNewlinesTest(unittest.TestCase):
    def test_changes_only_files_that_lack_the_newline(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / ".entangled").mkdir()
            (root / ".entangled" / "filedb.json").write_text(
                '{"target": ["a.v", "b.v", "c.v"], "source": [], "files": {}}'
            )
            (root / "a.v").write_bytes(b"x")
            (root / "b.v").write_bytes(b"y\n")
            (root / "c.v").write_bytes(b"")
            self.assertEqual(tangle.add_final_newlines(root), ["a.v"])
            self.assertEqual((root / "a.v").read_bytes(), b"x\n")
            self.assertEqual((root / "b.v").read_bytes(), b"y\n")
            self.assertEqual((root / "c.v").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
