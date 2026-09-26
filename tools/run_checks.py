"""Run the checks of the book: each test with Verilator, each prove with SymbiYosys, and each equiv with z3.

make check runs it from the root of the repository, after the tangle. It reads
build/checks.json, which the tangle writes, and runs each check in the chapter
order. The top module of a test or a prove is the first module in its code, and
the top module of an equiv is its module option. Each check reads
build/rtl/bcw_params.sv and each Verilog file of build/rtl.

A test passes when Verilator builds the testbench and the testbench exits 0. A
prove passes when SymbiYosys proves each assertion with the smtbmc engine and
Yices, to the depth of the check.

An equiv passes when z3 proves that the module equals its twin. yosys writes
the module as SMT. tools/twin.py translates the function of the twin, which
returns a dict of the output ports, with a bit-vector for each input port. z3
then looks for input values where an output of the module differs from the
value of the twin. A module that holds state fails: a prove check can prove it.

The runner prints each result at the chapter line of its check directive. After
a failure come the lines of the tool that tell why, with each location mapped
to its chapter line by tools/linemap.py:

    book/core/core.rst:91: FAIL: [check] core.rotation.test: the testbench stopped with exit 1
        %Error: book/core/core.rst:101: Verilog $stop

It exits 1 if a check fails. The work of each check is in build/run/<name>.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import z3

import linemap
import twin

MODULE = re.compile(r"^\s*module\s+(\w+)", re.MULTILINE)
# The lines of SymbiYosys that tell why a proof failed, and its last line.
PROOF_LINES = re.compile(r"Assert failed|ERROR|DONE")
PROOF_PREFIX = re.compile(r"^SBY\s+[\d:]+\s+\[[^\]]*\]\s+")
# The comments of yosys write_smt2 that name each port, and that mark a register or a memory.
PORT = re.compile(r"^; yosys-smt2-(input|output) (\S+) (\d+)$", re.MULTILINE)
STATE = re.compile(r"^; yosys-smt2-(register|memory) ", re.MULTILINE)


def sources():
    """The package of PARAMETERs, then each Verilog file of build/rtl."""
    return ["build/rtl/bcw_params.sv"] + sorted(str(path) for path in Path("build/rtl").rglob("*.v"))


def constants():
    """The value of each PARAMETER of the book, by its constant name."""
    return json.loads(Path("build/checks.json").read_text())["constants"]


def run_test(check, top, work):
    """None if the testbench passes, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    build = subprocess.run(["verilator", "--binary", "--quiet", "-j", "0", "--top-module", top,
                            "--Mdir", str(work), *sources(), check["file"]], capture_output=True, text=True)
    if build.returncode:
        return "Verilator could not build the testbench", build.stdout + build.stderr
    result = subprocess.run([str(work / f"V{top}")], capture_output=True, text=True)
    if result.returncode:
        return f"the testbench stopped with exit {result.returncode}", result.stdout + result.stderr
    return None


def run_prove(check, top, work):
    """None if SymbiYosys proves the properties, or (reason, output)."""
    work.parent.mkdir(parents=True, exist_ok=True)
    job = work.parent / f"{check['name']}.sby"
    reads = "".join(f"read -formal {Path(path).absolute()}\n" for path in sources() + [check["file"]])
    job.write_text(f"[options]\nmode prove\ndepth {check['depth']}\n\n[engines]\nsmtbmc yices\n\n"
                   f"[script]\n{reads}prep -top {top}\n")
    result = subprocess.run(["sby", "-f", "-d", str(work), str(job)], capture_output=True, text=True)
    if result.returncode == 0:
        return None
    lines = [PROOF_PREFIX.sub("", text) for text in result.stdout.splitlines() if PROOF_LINES.search(text)]
    reason = "the proof failed" if result.returncode == 2 else "SymbiYosys stopped with an error"
    return reason, "\n".join(lines)


def run_equiv(check, top, work):
    """None if z3 proves that each output of the module equals the value of the twin, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    smt = work / "module.smt2"
    result = subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv {' '.join(sources())}; prep -top {top}; "
                             f"write_smt2 -wires {smt}"], capture_output=True, text=True)
    if result.returncode:
        return "yosys could not read the module", result.stdout + result.stderr
    text = smt.read_text()
    if STATE.search(text):
        return "the module holds state: prove it with a prove check", ""
    if check["twin_file"] is None:
        return f"{check['verifies'][0]} has no twin", ""
    ports = PORT.findall(text)
    inputs = {name: z3.BitVec(f"port_{name}", int(width)) for kind, name, width in ports if kind == "input"}
    outputs = {name: z3.BitVec(f"port_{name}", int(width)) for kind, name, width in ports if kind == "output"}
    try:
        width, values = twin.translate(Path(check["twin_file"]).read_text(), check["twin"], inputs, constants())
    except twin.TwinError as error:
        return "the twin cannot be translated", f"{check['twin_file']}:{error.line}: {error}"
    if not isinstance(values, dict):
        return f"{check['twin']} returns one value, not a dict of the output ports", ""
    if sorted(values) != sorted(outputs):
        return (f"the twin gives the outputs {', '.join(sorted(values))}, but the module has the outputs "
                f"{', '.join(outputs)}"), ""
    # Each port becomes a bit-vector that equals its bits in one state of the module. The
    # outputs are natural numbers, and the values of the twin are in two's complement.
    solver = z3.Solver()
    solver.add(z3.parse_smt2_string(text + f"(declare-const state |{top}_s|)" + "".join(
        f"(declare-const port_{name} (_ BitVec {size}))(assert (= port_{name} (|{top}_n {name}| state)))"
        for _, name, size in ports)))
    wide = max([width] + [term.size() + 1 for term in outputs.values()])
    module = {name: z3.ZeroExt(wide - term.size(), term) for name, term in outputs.items()}
    values = {name: z3.SignExt(wide - width, values[name]) for name in outputs}
    solver.add(z3.Or([module[name] != values[name] for name in outputs]))
    if solver.check() == z3.unsat:
        return None
    model = solver.model()

    def number(term, signed=False):
        value = model.eval(term, model_completion=True)
        return value.as_signed_long() if signed else value.as_long()

    shown = ", ".join(f"{name}={number(term)}" for name, term in inputs.items())
    return "the module and the twin differ", "\n".join(
        f"{shown}: module {name}={number(module[name])}, twin {name}={number(values[name], signed=True)}"
        for name in outputs if number(module[name]) != number(values[name], signed=True))


RUNNERS = {"test": run_test, "prove": run_prove, "equiv": run_equiv}


def main():
    checks = json.loads(Path("build/checks.json").read_text())["checks"]
    passed = failed = 0
    for check in checks:
        place = f"{check['path']}:{check['line']}"
        if check["kind"] == "equiv":
            top = check["module"]
        else:
            module = MODULE.search(Path(check["file"]).read_text())
            top = module.group(1) if module else None
        if top is None:
            failure = "the code declares no module", ""
        else:
            failure = RUNNERS[check["kind"]](check, top, Path("build/run") / check["name"])
        if failure is None:
            print(f"{place}: PASS: [check] {check['name']}")
            passed += 1
            continue
        reason, output = failure
        print(f"{place}: FAIL: [check] {check['name']}: {reason}")
        for text in output.splitlines():
            print("    " + linemap.rewrite(text))
        failed += 1
    print(f"run_checks: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
