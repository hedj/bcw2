"""Tests of tools/ste_lint.py, the language linter copied from BCW-1."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINT = ROOT / "tools" / "ste_lint.py"


def run(*args):
    return subprocess.run([sys.executable, str(LINT), *args], capture_output=True, text=True)


class SteLintTest(unittest.TestCase):
    def test_the_selftest_passes(self):
        result = run("--selftest")
        self.assertEqual((result.returncode, result.stdout), (0, "selftest OK\n"))

    def test_a_clean_file_exits_0(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "clean.md"
            path.write_text("The core gives each thread its turn.\n")
            self.assertEqual(run(str(path)).returncode, 0)

    def test_a_semicolon_is_a_hard_finding_and_exits_1(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "bad.md"
            path.write_text("The core rotates; the thread waits.\n")
            result = run(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{path}:1:17 semicolon:", result.stdout)


if __name__ == "__main__":
    unittest.main()
