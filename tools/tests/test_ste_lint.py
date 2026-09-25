"""Tests of tools/ste_lint.py, the language linter copied from BCW-1."""

import subprocess
import sys

from book import ROOT

LINT = ROOT / "tools" / "ste_lint.py"


def run(*args):
    return subprocess.run([sys.executable, str(LINT), *args], capture_output=True, text=True)


class SteLintTest:
    def test_the_selftest_passes(self):
        result = run("--selftest")
        assert (result.returncode, result.stdout) == (0, "selftest OK\n")

    def test_a_clean_file_exits_0(self, tmp_path):
        path = tmp_path / "clean.md"
        path.write_text("The core gives each thread its turn.\n")
        assert run(str(path)).returncode == 0

    def test_a_semicolon_is_a_hard_finding_and_exits_1(self, tmp_path):
        path = tmp_path / "bad.md"
        path.write_text("The core rotates; the thread waits.\n")
        result = run(str(path))
        assert result.returncode == 1
        assert f"{path}:1:17 semicolon:" in result.stdout
