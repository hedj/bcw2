"""Tests of tools/metrics.py, which counts the McCabe and Halstead metrics of the code of the system with radon."""

import json
import subprocess
import sys

from radon.metrics import h_visit

from book import ROOT

METRICS = ROOT / "tools" / "metrics.py"
PLAIN = "def f(x):\n    return x\n"
BRANCH = "def f(x):\n    if x:\n        return 1\n    return x\n"


def measure(root, files):
    """The metrics that tools/metrics.py prints for the files, by path under root."""
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    result = subprocess.run([sys.executable, str(METRICS)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class MetricsTest:
    def test_a_function_without_a_branch_has_mccabe_complexity_1(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": PLAIN})["mccabe"] == 1

    def test_a_branch_adds_1_to_mccabe_complexity(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": BRANCH})["mccabe"] == 2

    def test_the_methods_of_a_class_count(self, tmp_path):
        text = "class C:\n    def f(self, x):\n        if x:\n            return 1\n        return x\n"
        assert measure(tmp_path, {"tools/a.py": text})["mccabe"] == 2

    def test_a_nested_function_counts(self, tmp_path):
        text = "def f(x):\n    def g(y):\n        if y:\n            return 1\n        return 2\n    return g(x)\n"
        assert measure(tmp_path, {"tools/a.py": text})["mccabe"] == 3

    def test_the_files_add_up(self, tmp_path):
        assert measure(tmp_path, {"tools/a.py": PLAIN, "tools/b.py": BRANCH})["mccabe"] == 3

    def test_the_tests_are_left_out(self, tmp_path):
        metrics = measure(tmp_path, {"tools/a.py": PLAIN, "tools/tests/test_a.py": BRANCH})
        assert metrics["mccabe"] == 1

    def test_the_halstead_measures_are_those_of_radon(self, tmp_path):
        text = "def f(x, y):\n    return (x + y) * (x - y) // 2\n"
        total = h_visit(text).total
        assert measure(tmp_path, {"tools/a.py": text}) == {"mccabe": 1, "halstead_volume": total.volume,
                                                           "halstead_effort": total.effort}
