"""Tests of ./dev, run on a copy of it in a temporary Git repository, with a stub in place of nix."""

import os
import shutil
import subprocess

import pytest

from book import ROOT

STUB = '#!/bin/sh\nprintf "%s\\n" "$@" > "$(dirname "$0")/arguments"\n'


class DevTest:
    @pytest.fixture(autouse=True)
    def repository(self, tmp_path):
        self.root = tmp_path / "repository"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        shutil.copy2(ROOT / "dev", self.root / "dev")
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        (self.bin / "nix").write_text(STUB)
        (self.bin / "nix").chmod(0o755)

    def run(self, store):
        return subprocess.run([str(self.root / "dev"), "true"], capture_output=True, text=True,
                              env={**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "NIX_STORE_DIR": str(store)})

    def hooks_path(self):
        return subprocess.run(["git", "-C", str(self.root), "config", "core.hooksPath"],
                              capture_output=True, text=True).stdout.strip()

    def test_a_missing_store_stops_before_nix_runs(self, tmp_path):
        store = tmp_path / "missing" / "store"
        result = self.run(store)
        assert result.returncode == 1
        assert result.stderr == (f"dev: the Nix store {store} does not exist. If Nix came from a distribution "
                                 'package, create the store and start the Nix daemon: see "The environment" in '
                                 "readme.build.\n")
        assert not (self.bin / "arguments").exists()
        assert self.hooks_path() == ""

    def test_with_a_store_nix_runs_the_command_in_the_environment(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        result = self.run(store)
        assert result.returncode == 0, result.stderr
        assert (self.bin / "arguments").read_text().splitlines() == [
            "--extra-experimental-features", "nix-command", "--extra-experimental-features", "flakes",
            "develop", str(self.root), "--command", "true"]
        assert self.hooks_path() == "tools/hooks"
