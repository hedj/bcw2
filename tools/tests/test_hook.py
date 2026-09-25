"""Tests of tools/hooks/pre-push, run in a temporary clone of this repository."""

import os
import subprocess

import pytest

from book import ROOT

HOOK = ROOT / "tools" / "hooks" / "pre-push"
ZERO = "0" * 40


class PrePushTest:
    @pytest.fixture(autouse=True)
    def clone(self, tmp_path):
        self.clone = tmp_path / "clone"
        subprocess.run(["git", "clone", "--quiet", str(ROOT), str(self.clone)], check=True)
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
        assert text.count(":param:`core.threads`.") == 1
        chapter.write_text(text.replace(":param:`core.threads`.", ":param:`core.threads`. It shall not stall."))

    def test_a_good_commit_passes(self):
        result = self.push(self.good)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_failing_commit_stops_the_push(self):
        self.break_the_chapter()
        self.git("-c", "user.name=test", "-c", "user.email=test@example.com",
                 "commit", "--quiet", "-am", "Break the chapter")
        bad = self.git("rev-parse", "HEAD")
        result = self.push(bad)
        assert result.returncode == 1
        assert f"pre-push: make check failed on {bad}, so the push is stopped." in result.stderr
        assert "[one-shall] core.rotation" in result.stdout

    def test_uncommitted_edits_play_no_part(self):
        self.break_the_chapter()
        result = self.push(self.good)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_deleted_branch_runs_nothing(self):
        result = self.push(ZERO)
        assert (result.returncode, result.stdout) == (0, "")

    def test_the_worktree_is_removed(self):
        self.push(self.good)
        assert len(self.git("worktree", "list").splitlines()) == 1
