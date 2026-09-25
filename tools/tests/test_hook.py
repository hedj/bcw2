"""Tests of tools/hooks/pre-push, run in a temporary clone of this repository."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_bcw import ROOT

HOOK = ROOT / "tools" / "hooks" / "pre-push"
ZERO = "0" * 40


class PrePushTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.clone = Path(directory.name) / "clone"
        subprocess.run(["git", "clone", "--quiet", str(ROOT), str(self.clone)], check=True)
        os.symlink(ROOT / ".venv", self.clone / ".venv")
        self.good = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.clone), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def push(self, sha):
        return subprocess.run(
            [str(HOOK)], cwd=self.clone, capture_output=True, text=True,
            input=f"refs/heads/x {sha} refs/heads/x {ZERO}\n",
            env={**os.environ, "PRE_PUSH_TARGETS": "check"})

    def break_the_chapter(self):
        chapter = self.clone / "book" / "core" / "core.rst"
        text = chapter.read_text()
        self.assertEqual(text.count("thread count."), 1)
        chapter.write_text(text.replace("thread count.", "thread count. It shall not stall."))

    def test_a_good_commit_passes(self):
        result = self.push(self.good)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_failing_commit_stops_the_push(self):
        self.break_the_chapter()
        self.git("-c", "user.name=test", "-c", "user.email=test@example.com",
                 "commit", "--quiet", "-am", "Break the chapter")
        bad = self.git("rev-parse", "HEAD")
        result = self.push(bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"pre-push: make check failed on {bad}, so the push is stopped.", result.stderr)
        self.assertIn("[one-shall] core.rotation", result.stdout)

    def test_uncommitted_edits_play_no_part(self):
        self.break_the_chapter()
        result = self.push(self.good)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_deleted_branch_runs_nothing(self):
        result = self.push(ZERO)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_the_worktree_is_removed(self):
        self.push(self.good)
        self.assertEqual(len(self.git("worktree", "list").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
