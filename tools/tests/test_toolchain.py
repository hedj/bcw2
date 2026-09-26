"""Tests of the formal and FPGA tools that the environment pins: yosys, SymbiYosys with Yices, nextpnr and ecppack.

A tool that only seems to run is as bad as one that is missing, so the tests of
SymbiYosys expect a failure as well as a pass.
"""

import subprocess

import pytest

from book import GOOD, THREADS, Book

# A counter that stops at TOP. The property count <= 9 holds for TOP 9, and fails for TOP 10.
COUNTER = """\
module sat (input wire clk, input wire rst_n, output reg [3:0] count);
    initial assume (!rst_n);
    localparam [3:0] TOP = 4'd{top};
    always @(posedge clk)
        if (!rst_n) count <= 4'd0;
        else if (count != TOP) count <= count + 4'd1;
    always @(posedge clk) if (rst_n) assert (count <= 4'd9);
endmodule
"""
JOB = "[options]\nmode prove\ndepth 20\n\n[engines]\nsmtbmc yices\n\n[script]\nread -formal sat.sv\nprep -top sat\n\n[files]\nsat.sv\n"


def run(command, folder):
    return subprocess.run(command, cwd=folder, capture_output=True, text=True)


@pytest.mark.parametrize("top, status", [(9, "PASS"), (10, "FAIL")])
def test_symbiyosys_with_yices_proves_a_true_property_and_refutes_a_false_one(tmp_path, top, status):
    (tmp_path / "sat.sv").write_text(COUNTER.format(top=top))
    (tmp_path / "sat.sby").write_text(JOB)
    result = run(["sby", "-f", "sat.sby"], tmp_path)
    assert f"DONE ({status}" in result.stdout, result.stdout[-2000:]


def test_yosys_nextpnr_and_ecppack_build_a_bitstream(tmp_path):
    (tmp_path / "blink.v").write_text("module blink (input wire clk, output wire led);\n"
                                      "    reg [23:0] count = 24'd0;\n"
                                      "    always @(posedge clk) count <= count + 24'd1;\n"
                                      "    assign led = count[23];\nendmodule\n")
    steps = [["yosys", "-q", "-p", "synth_ecp5 -top blink -json blink.json", "blink.v"],
             ["nextpnr-ecp5", "--25k", "--package", "CABGA256", "--json", "blink.json", "--textcfg", "blink.config",
              "--lpf-allow-unconstrained", "--quiet", "--seed", "1"],
             ["ecppack", "blink.config", "blink.bit"]]
    for step in steps:
        result = run(step, tmp_path)
        assert result.returncode == 0, (step, result.stderr[-2000:])
    assert (tmp_path / "blink.bit").stat().st_size > 100000


def test_yosys_reads_the_package_of_the_book_and_a_scoped_name(tmp_path):
    package = Book({"core/core.rst": GOOD + THREADS}, tangle=True).files["build/rtl/bcw_params.sv"]
    (tmp_path / "bcw_params.sv").write_text(package)
    (tmp_path / "count.v").write_text("module count (input wire [bcw_params::CORE_THREADS-1:0] a, output wire b);\n"
                                      "    assign b = a == bcw_params::CORE_THREADS'(1);\nendmodule\n")
    result = run(["yosys", "-q", "-p", "read_verilog -sv bcw_params.sv count.v; prep -top count; "
                  "write_smt2 -wires count.smt2"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "; yosys-smt2-input a 8\n" in (tmp_path / "count.smt2").read_text()
