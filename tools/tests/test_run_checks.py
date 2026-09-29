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
BLOCKS = ROOT / "tools" / "smtbmc_blocks.py"
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

    def test_a_testbench_that_does_not_finish_in_its_timeout_fails(self, tmp_path):
        bench = "module tb;\n    logic clk = 0;\n    always #1 clk = ~clk;\nendmodule\n"
        text, result = run(tmp_path, check("test", bench, "   :timeout: 2\n"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] "
                                                 "core.rotation.test: the testbench did not finish in 2 s")

    def test_code_without_a_module_fails(self, tmp_path):
        text, result = run(tmp_path, check("test", "initial $finish;"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] "
                                                 "core.rotation.test: the code declares no module")


def model(code, path="build/model/core/ref.c"):
    """A source directive that tangles a C reference model to path."""
    body = "".join(f"   {text}\n" if text else "\n" for text in code.splitlines())
    return f"\n.. source:: {path}\n\n{body}"


# The next turn in C, with the number of threads as an argument, as the testbench passes it.
REF_NEXT = """\
#include <stdint.h>
uint32_t ref_next(uint32_t turn, uint32_t threads)
{{
    return (turn + {step}) % threads;
}}
"""

MODEL_BENCH = """\
module tb;
    import "DPI-C" function int unsigned ref_next(input int unsigned turn, input int unsigned threads);
    logic [2:0] turn, next;
    core_rotate dut (.turn(turn), .next(next));
    initial begin
        for (int t = 0; t < 8; t++) begin
            turn = 3'(t);
            #1;
            if (32'(next) != ref_next(t, bcw_params::CORE_THREADS)) $fatal(1, "turn %0d", t);
        end
        $finish;
    end
endmodule
"""


class ModelTest:
    """A test calls the C models of build/model through DPI-C."""

    def test_a_testbench_calls_a_model_with_the_value_of_a_parameter(self, tmp_path):
        text, result = run(tmp_path, THREADS + model(REF_NEXT.format(step=1)) + check("test", MODEL_BENCH))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[-1] == "run_checks: 2 passed, 0 failed"

    def test_a_wrong_model_fails_the_testbench(self, tmp_path):
        text, result = run(tmp_path, THREADS + model(REF_NEXT.format(step=2)) + check("test", MODEL_BENCH))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == (f"{CHAPTER}:{line(text, '.. check:: test')}: FAIL: [check] "
                                                 "core.rotation.test: the testbench stopped with exit 1")

    @pytest.mark.parametrize("fault, needle", [("    return turn +;", "return turn +;"),
                                               ("    int unused;", "int unused;")])
    def test_a_model_that_does_not_compile_fails_at_its_chapter_line(self, tmp_path, fault, needle):
        code = REF_NEXT.format(step=1).replace("{\n", "{\n" + fault + "\n")
        text, result = run(tmp_path, THREADS + model(code))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert (f"{CHAPTER}:{line(text, '#include <stdint.h>')}: FAIL: [model] build/model/core/ref.c: "
                "the C compiler could not build the model") in lines
        assert any(entry.startswith(f"    {CHAPTER}:{line(text, needle)}:") for entry in lines)
        assert lines[-1] == "run_checks: 1 passed, 1 failed"


def mutant(old, new, kills="core.rotation.test", path="build/rtl/core/core_rotate.v"):
    """A mutant of the file at path that replaces the line old with the line new."""
    return f"\n.. mutant:: {path}\n   :kills: {kills}\n\n   -{old}\n   +{new}\n"


# GOOD's core_rotate adds 1; each of these gives another next turn.
ROTATE = "    assign next = turn + 3'd1;"
PLUS_TWO = "    assign next = turn + 3'd2;"
SAME = "    assign next = turn;"
# A fault at turn 5 only, which the testbench of turn 2 cannot see.
ONLY_AT_FIVE = "    assign next = (turn == 3'd5) ? 3'd0 : turn + 3'd1;"

# A testbench that waits for the next turn of 2, with a clock that never stops.
WAITING = """\
module tb;
    logic clk = 0;
    logic [2:0] turn, next;
    core_rotate dut (.turn(turn), .next(next));
    always #1 clk = ~clk;
    initial begin
        turn = 3'd2;
        wait (next == 3'd3);
        $finish;
    end
endmodule
"""


# verifies: doc.mutants-fail
class MutantTest:
    """Each mutant makes each check that its kills option names fail."""

    def place(self, text):
        return f"{CHAPTER}:{line(text, '.. mutant::')}"

    def test_a_mutant_that_the_testbench_catches_passes(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3)) + mutant(ROTATE, PLUS_TWO))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[2:] == [f"{self.place(text)}: PASS: [mutant] core.rotation.test",
                                                  "run_checks: 3 passed, 0 failed"]

    def test_a_mutant_that_the_testbench_cannot_see_fails(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3)) + mutant(ROTATE, ONLY_AT_FIVE))
        assert result.returncode == 1
        assert result.stdout.splitlines()[2:] == [
            f"{self.place(text)}: FAIL: [mutant] core.rotation.test: the check passes with the mutant",
            "run_checks: 2 passed, 1 failed"]

    def test_a_mutant_leaves_the_tangled_file_as_it_was(self, tmp_path):
        run(tmp_path, check("test", TESTBENCH.format(expected=3)) + mutant(ROTATE, PLUS_TWO))
        assert ROTATE in (tmp_path / "build/rtl/core/core_rotate.v").read_text()

    def test_a_mutant_that_a_proof_catches_passes(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != turn"))
                           + mutant(ROTATE, SAME, kills="core.rotation.prove"))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[2] == f"{self.place(text)}: PASS: [mutant] core.rotation.prove"

    def test_a_mutant_that_a_proof_cannot_see_fails(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != turn"))
                           + mutant(ROTATE, PLUS_TWO, kills="core.rotation.prove"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[2] == (f"{self.place(text)}: FAIL: [mutant] core.rotation.prove: "
                                                 "the check passes with the mutant")

    def test_a_mutant_that_does_not_build_fails(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=3))
                           + mutant(ROTATE, "    assign next = ;"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[2] == (f"{self.place(text)}: FAIL: [mutant] core.rotation.test: "
                                                 "the mutant does not build")

    def test_a_mutant_that_stops_the_testbench_finishing_passes(self, tmp_path):
        text, result = run(tmp_path, check("test", WAITING, "   :timeout: 2\n") + mutant(ROTATE, PLUS_TWO))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[2] == f"{self.place(text)}: PASS: [mutant] core.rotation.test"

    def test_the_mutants_of_a_check_that_fails_are_not_reported(self, tmp_path):
        text, result = run(tmp_path, check("test", TESTBENCH.format(expected=4)) + mutant(ROTATE, PLUS_TWO))
        assert result.returncode == 1
        assert not any("[mutant]" in entry for entry in result.stdout.splitlines())
        assert result.stdout.splitlines()[-1] == "run_checks: 1 passed, 1 failed"

    def test_a_mutant_of_a_proof_runs_the_base_case_through_the_blocks(self, tmp_path):
        run(tmp_path, check("prove", PROPERTIES.format(property="next != turn"))
            + mutant(ROTATE, SAME, kills="core.rotation.prove"))
        work = tmp_path / "build" / "run" / "core.rotation.prove.mutant-1"
        assert "\nmode bmc\n" in (work / "run.sby").read_text()
        assert str(BLOCKS) in (work / "run" / "logfile.txt").read_text()

    @pytest.mark.parametrize("steps, sent", [("10", "0:4:10"), ("3:10", "3:10")])
    def test_the_blocks_check_4_steps_in_each_query(self, tmp_path, steps, sent):
        smtbmc = tmp_path / "yosys-smtbmc"
        smtbmc.write_text('#!/bin/sh\necho "$@"\n')
        smtbmc.chmod(0o755)
        result = subprocess.run([sys.executable, str(BLOCKS), "-s", "yices", "-t", steps, "design.smt2"],
                                capture_output=True, text=True, env={"PATH": str(tmp_path)})
        assert result.stdout.split() == ["-s", "yices", "-t", sent, "design.smt2"]


# verifies: doc.proof-meaning
class MeaningTest:
    def test_an_assertion_whose_condition_never_holds_fails_at_its_chapter_line(self, tmp_path):
        code = PROPERTIES.format(property="next != turn").replace(
            "always_comb assert", "always_comb if (turn == 3'd1 && turn == 3'd2) assert")
        text, result = run(tmp_path, check("prove", code))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: prove')}: FAIL: [check] core.rotation.prove: "
                            "the condition of an assertion never holds")
        assert any(f"{CHAPTER}:{line(text, 'assert (')}." in entry for entry in lines[2:])

    def test_an_assertion_that_holds_for_any_dut_fails_at_its_chapter_line(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next == next")))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == (f"{CHAPTER}:{line(text, '.. check:: prove')}: FAIL: [check] core.rotation.prove: "
                            "an assertion holds whatever dut does")
        assert any(f"{CHAPTER}:{line(text, 'assert (')}." in entry and "holds with a free dut" in entry
                   for entry in lines[2:])

    def test_a_harness_without_an_instance_dut_fails(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next != turn").replace(
            "core_rotate dut", "core_rotate rotate")))
        assert result.stdout.splitlines()[1] == (f"{CHAPTER}:{line(text, '.. check:: prove')}: FAIL: [check] "
                                                 "core.rotation.prove: the harness has no instance dut")

    def test_the_mutants_of_a_proof_without_meaning_are_not_reported(self, tmp_path):
        text, result = run(tmp_path, check("prove", PROPERTIES.format(property="next == next"))
                           + mutant(ROTATE, SAME, kills="core.rotation.prove"))
        assert "[mutant]" not in result.stdout


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

    @pytest.mark.parametrize("value, differs", [("1 if turn == 7 else 0", False), ("1 if turn == 6 else 0", True)])
    def test_a_1_bit_output_is_compared_as_a_number(self, tmp_path, value, differs):
        chapter = twin(f"return {{'next': (turn + 1) % 8, 'last': {value}}}").replace(
            "output wire [2:0] next);", "output wire [2:0] next, output wire last);").replace(
            "       assign next = turn + 3'd1;\n", "       assign next = turn + 3'd1;\n       assign last = turn == 3'd7;\n")
        text, result = run(tmp_path, "", chapter)
        lines = result.stdout.splitlines()
        if not differs:
            assert lines == [f"{CHAPTER}:{line(text, '.. check:: equiv')}: PASS: [check] core.rotation.equiv",
                             "run_checks: 1 passed, 0 failed"], result.stdout + result.stderr
            return
        assert lines[0] == failure(text, "the module and the twin differ"), result.stdout + result.stderr
        assert re.fullmatch(r"    turn=([67]): module last=([01]), twin last=([01])", lines[1]), lines[1]

    def test_a_twin_reads_the_parameters_of_the_book(self, tmp_path):
        text, result = run(tmp_path, THREADS, twin("return {'next': (turn + 1) % CORE_THREADS}"))
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

    def test_a_twin_that_branches_on_equality_passes(self, tmp_path):
        text, result = run(tmp_path, "", twin("return {'next': 0 if turn == 7 else turn + 1}"))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[0] == f"{CHAPTER}:{line(text, '.. check:: equiv')}: PASS: [check] " \
                                                "core.rotation.equiv"

    def test_a_twin_outside_the_language_fails_at_its_chapter_line(self, tmp_path):
        text, result = run(tmp_path, "", twin("return {'next': {7: 0}[turn]}"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[:2] == [
            failure(text, "the twin cannot be translated"),
            f"    {CHAPTER}:{line(text, '{7: 0}[turn]')}: '{{7: 0}}[turn]' is not in the twin language"]

    def test_a_twin_that_returns_one_value_fails(self, tmp_path):
        text, result = run(tmp_path, "", twin("return (turn + 1) % 8"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[0] == failure(text, "core_rotate returns one value, not a dict of the "
                                                              "output ports")

    def test_a_twin_function_that_does_not_exist_fails(self, tmp_path):
        text, result = run(tmp_path, "", GOOD.replace("   :module: core_rotate\n",
                                                      "   :module: core_rotate\n   :twin: nothing\n"))
        assert result.returncode == 1
        assert result.stdout.splitlines()[:2] == [
            failure(text, "the twin cannot be translated"),
            f"    {CHAPTER}:{line(text, 'def core_rotate')}: the twin defines no function nothing"]

    MIX = ("\n.. source:: build/rtl/core/mix.v\n\n"
           "   module mix (input wire [7:0] a, input wire [7:0] b, output wire [7:0] y);\n"
           "       assign y = (a & b) ^ (a >> 1);\n   endmodule\n"
           "\n.. check:: equiv\n   :verifies: core.rotation\n   :module: mix\n")

    def mixed(self, body):
        """GOOD with a second twin function mix, whose output y is body."""
        return GOOD.replace("      def core_rotate(turn):",
                            f"      def mix(a, b):\n          return {{'y': {body}}}\n\n\n      def core_rotate(turn):")

    @pytest.mark.parametrize("value", [15, 255])
    def test_a_negative_twin_value_never_equals_an_output(self, tmp_path, value):
        # The twin needs 4 bits and the output has 8, so the runner must extend both correctly. With
        # one output, a wrong extension makes the whole check pass.
        wide = ("\n.. source:: build/rtl/core/wide.v\n\n"
                "   module wide (input wire [2:0] turn, output wire [7:0] out);\n"
                f"       assign out = 8'd{value};\n   endmodule\n"
                "\n.. check:: equiv\n   :verifies: core.rotation\n   :module: wide\n")
        chapter = GOOD.replace("      def core_rotate(turn):",
                               "      def wide(turn):\n          return {'out': -1}\n\n\n      def core_rotate(turn):")
        text, result = run(tmp_path, wide, chapter)
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == failure(text, "the module and the twin differ", 2)
        assert re.fullmatch(rf"    turn=\d+: module out={value}, twin out=-1", lines[2]), lines[2]

    def test_a_twin_with_bit_operations_passes(self, tmp_path):
        text, result = run(tmp_path, self.MIX, self.mixed("(a & b) ^ (a >> 1)"))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[1] == f"{CHAPTER}:{line(text, '.. check:: equiv', ':module: core_rotate')}: " \
                                                "PASS: [check] core.rotation.equiv-2"

    def test_a_twin_with_other_bit_operations_fails_with_the_inputs(self, tmp_path):
        text, result = run(tmp_path, self.MIX, self.mixed("(a | b) ^ (a >> 1)"))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == failure(text, "the module and the twin differ", 2)
        match = re.fullmatch(r"    a=(\d+), b=(\d+): module y=(\d+), twin y=(\d+)", lines[2])
        assert match, lines[2]
        a, b, module, value = map(int, match.groups())
        assert (module, value) == ((a & b) ^ (a >> 1), (a | b) ^ (a >> 1))

    def test_a_twin_takes_its_arguments_by_name_in_any_order(self, tmp_path):
        chapter = self.mixed("(a & b) ^ (a >> 1)").replace("def mix(a, b):", "def mix(b, a):")
        text, result = run(tmp_path, self.MIX, chapter)
        assert result.returncode == 0, result.stdout + result.stderr

    @staticmethod
    def module(name, ports, body, function):
        """(the source and the equiv of a module, GOOD with the twin function too)."""
        extra = (f"\n.. source:: build/rtl/core/{name}.v\n\n   module {name} ({ports});\n       {body}\n"
                 f"   endmodule\n\n.. check:: equiv\n   :verifies: core.rotation\n   :module: {name}\n")
        lines = "".join(f"      {line}\n" for line in function.splitlines())
        return extra, GOOD.replace("      def core_rotate(turn):", f"{lines}\n\n      def core_rotate(turn):")

    MUL = ("input wire [1:0] f3, input wire [31:0] a, b, output wire [31:0] y",
           "wire signed [63:0] p = $signed({f3 != 2'd3 && a[31], a}) * $signed({!f3[1] && b[31], b});\n"
           "       assign y = f3 == 2'd0 ? p[31:0] : p[63:32];")

    @pytest.mark.parametrize("unsigned_b, passes", [("f3 < 2", True), ("f3 == 0", False)])
    def test_a_signed_32_bit_multiply_is_proved_or_refuted(self, tmp_path, unsigned_b, passes):
        # Through equalities of the ports, z3 did not prove this multiply in 600 seconds.
        extra, chapter = self.module("mul", *self.MUL, (
            "def mul(f3, a, b):\n"
            "    x = a - 4294967296 if f3 != 3 and a >= 2147483648 else a\n"
            f"    z = b - 4294967296 if {unsigned_b} and b >= 2147483648 else b\n"
            "    p = x * z\n"
            "    return {'y': p & 4294967295 if f3 == 0 else (p >> 32) & 4294967295}"))
        text, result = run(tmp_path, extra, chapter)
        assert (result.returncode == 0) == passes, result.stdout + result.stderr
        if not passes:
            assert re.fullmatch(r"    a=\d+, b=\d+, f3=1: module y=\d+, twin y=\d+", result.stdout.splitlines()[2])

    @pytest.mark.parametrize("value, passes", [(5, True), (6, False)])
    def test_a_module_without_inputs_is_proved_or_refuted(self, tmp_path, value, passes):
        # The narrowest input splits the goal, and this module has none.
        extra, chapter = self.module("five", "output wire [3:0] y", "assign y = 4'd5;",
                                     f"def five():\n    return {{'y': {value}}}")
        text, result = run(tmp_path, extra, chapter)
        assert (result.returncode == 0) == passes, result.stdout + result.stderr

    @pytest.mark.parametrize("bit, passes", [(20, True), (21, False)])
    def test_input_bits_that_yosys_reorders_are_put_back(self, tmp_path, bit, passes):
        # yosys declares one function for the bits 31, 19:12, 20 and 30:21 of i, in that order.
        extra, chapter = self.module(
            "jimm", "input wire [31:0] i, output wire [31:0] y",
            "assign y = {{11{i[31]}}, i[31], i[19:12], i[20], i[30:21], 1'b0};",
            f"def jimm(i):\n    j = (((i >> 31) << 20) | (((i >> 12) & 255) << 12) | (((i >> {bit}) & 1) << 11)\n"
            "         | (((i >> 21) & 1023) << 1))\n    return {'y': j | 4292870144 if i >> 31 == 1 else j}")
        text, result = run(tmp_path, extra, chapter)
        assert (result.returncode == 0) == passes, result.stdout + result.stderr

    # An 8-bit multiply from the partial products of its 4-bit halves.
    MUL8 = ("input wire [7:0] a, b, output wire [15:0] y",
            "assign y = 16'(a[3:0]) * b[3:0] + ((16'(a[3:0]) * b[7:4]) << 4) + ((16'(a[7:4]) * b[3:0]) << 4)\n"
            "                  + ((16'(a[7:4]) * b[7:4]) << 8);")
    RULE = "def mul8(a, b):\n    return {'y': a * b}\n"
    SPLIT = ("def mul8_split(a, b):\n    al = a & 15\n    ah = a >> 4\n    bl = b & 15\n    bh = b >> 4\n"
             "    return {'y': al * bl + ((al * bh) << 4) + ((ah * bl) << 4) + ((ah * bh) << 8)}\n")

    def split_check(self, twin_text):
        extra, chapter = self.module("mul8", *self.MUL8, twin_text)
        return extra.replace("   :module: mul8\n", "   :module: mul8\n   :twin: mul8_split\n"), chapter

    def test_a_twin_in_steps_is_proved_equal_to_the_rule_then_to_the_module(self, tmp_path):
        text, result = run(tmp_path, *self.split_check(self.RULE + self.SPLIT))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_steps_that_differ_from_the_rule_fail_with_the_inputs(self, tmp_path):
        text, result = run(tmp_path, *self.split_check(self.RULE + self.SPLIT.replace("((ah * bh) << 8)",
                                                                                      "((ah * bh) << 7)")))
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines[1] == failure(text, "the twin functions mul8_split and mul8 differ", 2)
        match = re.fullmatch(r"    a=(\d+), b=(\d+): mul8 y=(\d+), mul8_split y=(\d+)", lines[2])
        assert match, lines[2]
        a, b, rule, steps = map(int, match.groups())
        assert (rule, steps) == (a * b, a * b - ((a >> 4) * (b >> 4) << 7))

    def test_steps_without_the_rule_fail(self, tmp_path):
        text, result = run(tmp_path, *self.split_check(self.SPLIT))
        assert result.returncode == 1
        assert result.stdout.splitlines()[1] == failure(text, "the twin cannot be translated", 2)

    def test_a_requirement_without_a_twin_fails(self, tmp_path):
        start, end = GOOD.index("   .. twin::"), GOOD.index(TWIN) + len(TWIN) + 1
        text, result = run(tmp_path, "", GOOD[:start] + GOOD[end:])
        assert result.returncode == 1
        assert result.stdout.splitlines()[0] == failure(text, "core.rotation has no twin")
