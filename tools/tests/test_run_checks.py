"""Tests of tools/run_checks.py, which runs each test check with Verilator and each prove check with SymbiYosys.

Each test tangles GOOD with one more check into a folder, then runs the runner
there, as make check does. A runner that only seems to run is as bad as none,
so each kind has a test that fails as well as one that passes.
"""

import subprocess
import sys

from book import GOOD, ROOT, THREADS, Book, line

RUNNER = ROOT / "tools" / "run_checks.py"
CHAPTER = "book/core/core.rst"


def check(kind, code, options=""):
    """A check of core.rotation with the kind, the extra option lines and the code."""
    body = "".join(f"   {text}\n" if text else "\n" for text in code.splitlines())
    return f"\n.. check:: {kind}\n   :verifies: core.rotation\n{options}\n{body}"


def run(tmp_path, extra):
    """Tangle GOOD and extra into tmp_path, run the runner there, and return (text of the chapter, result)."""
    text = GOOD + extra
    Book({"core/core.rst": text}, tangle=True, root=tmp_path)
    result = subprocess.run([sys.executable, str(RUNNER)], cwd=tmp_path, capture_output=True, text=True)
    return text, result


# GOOD's core_rotate adds 1 to turn, so the next turn of 2 is 3.
TESTBENCH = """\
module tb;
    logic [2:0] turn, next;
    core_rotate dut (.turn(turn), .next(next));
    initial begin
        turn = 3'd2;
        #1;
        if (next != 3'd{expected}) $fatal(1, "next is %0d", next);
        $finish;
    end
endmodule
"""

PROPERTIES = """\
module props (input logic [2:0] turn);
    logic [2:0] next;
    core_rotate dut (.turn(turn), .next(next));
    always_comb assert ({property});
endmodule
"""


# GOOD's equiv check comes first in the chapter, so the result of the new check is on the second line.


class TestbenchTest:
    def test_a_testbench_that_finishes_passes(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3)))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == [
            f"{CHAPTER}:{line(text, '.. check:: equiv')}: NOTE: [check] core.rotation.equiv: "
            "the runner cannot run an equiv check yet",
            f"{CHAPTER}:{line(text, '.. check:: test')}: PASS: [check] core.rotation.test",
            "run_checks: 1 passed, 0 failed, 1 not run"]

    def test_a_fatal_testbench_fails_at_its_directive_and_names_its_chapter_line(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=4)))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] core.rotation.test: "
                            "the testbench stopped with exit 1")
        assert f"    %Error: {CHAPTER}:{line(text, '$fatal')}: Verilog $stop" in lines
        assert lines[-1] == "run_checks: 0 passed, 1 failed, 1 not run"

    def test_a_testbench_reads_the_parameters_of_the_book(self, tmp_path):
        bench = "module tb;\n    initial if (bcw_params::CORE_THREADS != 8) $fatal(1);\nendmodule\n"
        _, result = run(tmp_path, THREADS + check("test", bench))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_testbench_that_does_not_build_fails_with_the_error_of_verilator(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3).replace("dut (", "dut (.clock(turn), ")))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] core.rotation.test: "
                            "Verilator could not build the testbench")
        assert any(entry.startswith(f"    %Error-PINNOTFOUND: {CHAPTER}:{line(text, 'core_rotate dut')}:") for entry in lines)

    def test_code_without_a_module_fails(self, tmp_path):
        text, result = run(tmp_path, check("test", "initial $finish;"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] "
                                                 "core.rotation.test: the code declares no module")


class ProofTest:
    def test_a_property_that_holds_passes(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != turn")))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[1] == f"{CHAPTER}:{line(text, '.. check:: prove')}: PASS: [check] " \
                                                "core.rotation.prove"

    def test_a_property_that_fails_names_the_chapter_line_of_the_assertion(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != 3'd0")))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: prove')}: FAIL: [check] core.rotation.prove: "
                            "the proof failed")
        number = line(text, "assert (")
        assert any("Assert failed in props:" in entry and f"{CHAPTER}:{number}." in entry and f"-{number}." in entry
                   for entry in lines)
        assert not any("SBY" in entry for entry in lines)
        assert lines[-1] == "run_checks: 0 passed, 1 failed, 1 not run"

    def test_a_proof_that_yosys_cannot_read_fails_with_the_error(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != turn").replace(
            "always_comb assert", "always_comb asert")))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: prove')}: FAIL: [check] core.rotation.prove: "
                            "SymbiYosys stopped with an error")
        assert any(f"{CHAPTER}:{line(text, 'asert (')}: ERROR:" in entry for entry in lines)

    def test_the_job_has_the_depth_of_the_check(self, tmp_path):
        run(tmp_path, check("prove", PROPERTIES.format(property="next != turn"), "   :depth: 5\n"))
        job = (tmp_path / "build" / "run" / "core.rotation.prove.sby").read_text()
        assert "\ndepth 5\n" in job
