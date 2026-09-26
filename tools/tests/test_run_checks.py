"""Tests of tools/run_checks.py, which runs each check: test with Verilator, prove with SymbiYosys, equiv with z3.

Each test tangles GOOD with one more check into a folder, then runs the runner
there, as make check does. A runner that only seems to run is as bad as none,
so each kind has a test that fails as well as one that passes.
"""

import re
import subprocess
import sys

import pytest

from book import GOOD, ROOT, THREADS, Book, line

RUNNER = ROOT / "tools" / "run_checks.py"
CHAPTER = "book/core/core.rst"


def check(kind, code, options=""):
    """A check of core.rotation with the kind, the extra option lines and the code."""
    body = "".join(f"   {text}\n" if text else "\n" for text in code.splitlines())
    return f"\n.. check:: {kind}\n   :verifies: core.rotation\n{options}\n{body}"


def run(tmp_path, extra, chapter=GOOD):
    """Tangle chapter and extra into tmp_path, run the runner there, and return (text of the chapter, result)."""
    text = chapter + extra
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


# GOOD's equiv check comes first in the chapter and passes, so the result of the new check is on the
# second line.


class TestbenchTest:
    def test_a_testbench_that_finishes_passes(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3)))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == [
            f"{CHAPTER}:{line(text, '.. check:: equiv')}: PASS: [check] core.rotation.equiv",
            f"{CHAPTER}:{line(text, '.. check:: test')}: PASS: [check] core.rotation.test",
            "run_checks: 2 passed, 0 failed"]

    def test_a_fatal_testbench_fails_at_its_directive_and_names_its_chapter_line(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=4)))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] core.rotation.test: "
                            "the testbench stopped with exit 1")
        assert f"    %Error: {CHAPTER}:{line(text, '$fatal')}: Verilog $stop" in lines
        assert lines[-1] == "run_checks: 1 passed, 1 failed"

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
        assert lines[-1] == "run_checks: 1 passed, 1 failed"

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


TWIN = "return {'next': (turn + 1) % 8}"


def twin(body):
    """GOOD with body in place of the return line of its twin."""
    assert GOOD.count(TWIN) == 1
    return GOOD.replace(TWIN, body)


def equiv(module):
    """An equiv check of core.rotation against the module."""
    return f"\n.. check:: equiv\n   :verifies: core.rotation\n   :module: {module}\n"


def failure(text, reason, occurrence=1):
    """The first line of the failure of the equiv check at the occurrence of its directive."""
    number = [index for index, content in enumerate(text.splitlines(), 1) if ".. check:: equiv" in content]
    return f"{CHAPTER}:{number[occurrence - 1]}: FAIL: [check] {'core.rotation.equiv' + ('-2' if occurrence == 2 else '')}: " \
           f"{reason}"


class EquivTest:
    def test_a_module_that_equals_its_twin_passes(self, tmp_path):
        text, result = run(tmp_path, "")
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == [f"{CHAPTER}:{line(text, '.. check:: equiv')}: PASS: [check] "
                                              "core.rotation.equiv", "run_checks: 1 passed, 0 failed"]

    def test_a_twin_that_differs_fails_with_the_input_and_both_outputs(self, tmp_path):
        text, result = run(tmp_path, "", twin("return {'next': (turn + 2) % 8}"))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[0] == failure(text, "the module and the twin differ")
        match = re.fullmatch(r"    turn=(\d+): module next=(\d+), twin next=(\d+)", lines[1])
        assert match, lines[1]
        turn, module, value = map(int, match.groups())
        assert (module, value) == ((turn + 1) % 8, (turn + 2) % 8)
        assert lines[-1] == "run_checks: 0 passed, 1 failed"

    def test_a_twin_can_give_a_python_int(self, tmp_path):
        text, result = run(tmp_path, "", twin("return {'next': 0}"))
        lines = result.stdout.splitlines()
        assert lines[0] == failure(text, "the module and the twin differ")
        assert lines[1].endswith(", twin next=0")

    def test_only_the_output_that_differs_is_shown(self, tmp_path):
        chapter = twin("return {'next': (turn + 1) % 8, 'same': turn + 1}").replace(
            "output wire [2:0] next);", "output wire [2:0] next, output wire [2:0] same);").replace(
            "       assign next = turn + 3'd1;\n", "       assign next = turn + 3'd1;\n       assign same = turn;\n")
        text, result = run(tmp_path, "", chapter)
        lines = result.stdout.splitlines()
        assert lines[0] == failure(text, "the module and the twin differ")
        match = re.fullmatch(r"    turn=(\d+): module same=(\d+), twin same=(\d+)", lines[1])
        assert match, lines[1]
        assert lines[2] == "run_checks: 0 passed, 1 failed"

    def test_a_twin_reads_the_parameters_of_the_book(self, tmp_path):
        chapter = twin("return {'next': (turn + 1) % CORE_THREADS}").replace(
            "      def core_rotate(turn):", "      from bcw_params import CORE_THREADS\n\n\n      def core_rotate(turn):")
        text, result = run(tmp_path, THREADS, chapter)
        assert result.returncode == 0, result.stdout + result.stderr

    @pytest.mark.parametrize("module", [
        "module state (input wire clk, output reg [2:0] turn);\n       always @(posedge clk) turn <= turn + 3'd1;",
        "module state (input wire clk, input wire [1:0] a, output wire [2:0] q);\n       reg [2:0] m [0:3];\n"
        "       always @(posedge clk) m[a] <= q + 3'd1;\n       assign q = m[a];"], ids=["register", "memory"])
    def test_a_module_with_state_fails(self, tmp_path, module):
        source = f"\n.. source:: build/rtl/core/state.v\n\n   {module}\n   endmodule\n"
        text, result = run(tmp_path, source + equiv("state"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == failure(text, "the module holds state: prove it with a prove check", 2)

    def test_a_module_that_yosys_cannot_find_fails_with_the_error(self, tmp_path):
        text, result = run(tmp_path, equiv("nothing"))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == failure(text, "yosys could not read the module", 2)
        assert "    ERROR: Module `nothing' not found!" in lines

    def test_a_twin_without_the_outputs_of_the_module_fails(self, tmp_path):
        text, result = run(tmp_path, "", twin("return {'nxt': turn}"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[0] == failure(
            text, "the twin gives the outputs nxt, but the module has the outputs next")

    def test_a_twin_that_branches_with_z3_if_passes(self, tmp_path):
        chapter = twin("return {'next': z3.If(turn == 7, 0, turn + 1)}").replace(
            "      def core_rotate(turn):", "      import z3\n\n\n      def core_rotate(turn):")
        text, result = run(tmp_path, "", chapter)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[0] == f"{CHAPTER}:{line(text, '.. check:: equiv')}: PASS: [check] " \
                                                "core.rotation.equiv"

    def test_a_twin_that_raises_fails_with_its_traceback(self, tmp_path):
        # A comparison other than == and != of a z3 value has no Python truth value, so the twin raises.
        text, result = run(tmp_path, "", twin("return {'next': 0 if turn >= 7 else turn + 1}"))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[0] == failure(text, "the twin failed")
        assert any(f'File "{CHAPTER}", line {line(text, "0 if turn")}, in core_rotate' in entry for entry in lines)

    def test_a_twin_function_that_does_not_exist_fails(self, tmp_path):
        text, result = run(tmp_path, "", GOOD.replace("   :module: core_rotate\n",
                                                      "   :module: core_rotate\n   :twin: nothing\n"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[0] == failure(text, "build/model/core_rotate.py defines no function nothing")

    def test_a_requirement_without_a_twin_fails(self, tmp_path):
        start, end = GOOD.index("   .. twin::"), GOOD.index(TWIN) + len(TWIN) + 1
        text, result = run(tmp_path, "", GOOD[:start] + GOOD[end:])
        assert result.returncode == 1
        assert result.stdout.splitlines()[0] == failure(text, "core.rotation has no twin")
