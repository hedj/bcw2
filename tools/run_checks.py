"""Run the checks of the book: each test with Verilator, each prove with SymbiYosys, and each equiv with z3.

make check runs it from the root of the repository, after the tangle. It reads
build/checks.json, which the tangle writes, and runs each check in the chapter
order. The top module of a test or a prove is the first module in its code, and
the top module of an equiv is its module option. Each check reads
build/rtl/bcw_params.sv and each Verilog file of build/rtl.

Before the checks, the runner compiles each C reference model of build/model
with the C compiler, into build/run/model, and links each model into each test,
so that a testbench can call its functions through DPI-C. Verilator would build
a C file as C++, whose names the DPI-C imports cannot find. A model that does
not compile is a failure at its first chapter line.

A test passes when Verilator builds the testbench and the testbench exits 0
within its timeout option, in seconds (60 if the option is not there). A
prove passes when SymbiYosys proves each assertion with the smtbmc engine and
Yices, to the depth of the check.

An equiv passes when z3 proves that the module equals its twin. yosys writes
the module as SMT. tools/twin.py translates the function of the twin, which
returns a dict of the output ports, with a bit-vector for each input port. z3
then looks for input values where an output of the module differs from the
value of the twin, comparing the term of each output with the term of the twin.
A module that holds state fails: a prove check can prove it.

The runner prints each result at the chapter line of its check directive. After
a failure come the lines of the tool that tell why, with each location mapped
to its chapter line by tools/linemap.py:

    book/core/core.rst:91: FAIL: [check] core.rotation.test: the testbench stopped with exit 1
        %Error: book/core/core.rst:101: Verilog $stop

After a test or a prove passes, the runner runs it once for each mutant that
names it in its kills option, with the mutated copy of the file in place of the
file. The check must fail: a mutant passes when the check fails, and fails when
the check passes or the mutated file does not build. The runner reports each
mutant at the chapter line of its directive:

    book/core/core.rst:95: FAIL: [mutant] core.rotation.test: the check passes with the mutant

It exits 1 if a check or a mutant fails. The work of each check is in
build/run/<name>, and of each of its mutants in build/run/<name>/mutant-<n>.
"""

import functools
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
MODELS = Path("build/model")
OBJECTS = Path("build/run/model")
COMPILE = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-c"]


def sources():
    """The package of PARAMETERs, then each Verilog file of build/rtl."""
    return ["build/rtl/bcw_params.sv"] + sorted(str(path) for path in Path("build/rtl").rglob("*.v"))


def constants():
    """The value of each PARAMETER of the book, by its constant name."""
    return json.loads(Path("build/checks.json").read_text())["constants"]


def compile_models():
    """The object of each C model that compiles, and (path, output) of each that does not."""
    objects, failures = [], []
    for source in sorted(MODELS.rglob("*.c")):
        target = OBJECTS / source.relative_to(MODELS).with_suffix(".o")
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([*COMPILE, str(source), "-o", str(target)], capture_output=True, text=True)
        if result.returncode:
            failures.append((source.as_posix(), result.stdout + result.stderr))
        else:
            objects.append(str(target.resolve()))
    return objects, failures


def run_test(check, top, work, files, objects):
    """None if the testbench passes, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    build = subprocess.run(["verilator", "--binary", "--quiet", "-j", "0", "--top-module", top,
                            "--Mdir", str(work), *files, check["file"], *objects],
                           capture_output=True, text=True)
    if build.returncode:
        return "Verilator could not build the testbench", build.stdout + build.stderr
    try:
        result = subprocess.run([str(work / f"V{top}")], capture_output=True, text=True, timeout=check["timeout"])
    except subprocess.TimeoutExpired:
        return f"the testbench did not finish in {check['timeout']} s", ""
    if result.returncode:
        return f"the testbench stopped with exit {result.returncode}", result.stdout + result.stderr
    return None


def run_prove(check, top, work, files):
    """None if SymbiYosys proves the properties, or (reason, output)."""
    work.parent.mkdir(parents=True, exist_ok=True)
    job = work.parent / f"{check['name']}.sby"
    reads = "".join(f"read -formal {Path(path).absolute()}\n" for path in files + [check["file"]])
    job.write_text(f"[options]\nmode prove\ndepth {check['depth']}\n\n[engines]\nsmtbmc yices\n\n"
                   f"[script]\n{reads}prep -top {top}\n")
    result = subprocess.run(["sby", "-f", "-d", str(work), str(job)], capture_output=True, text=True)
    if result.returncode == 0:
        return None
    lines = [PROOF_PREFIX.sub("", text) for text in result.stdout.splitlines() if PROOF_LINES.search(text)]
    reason = "the proof failed" if result.returncode == 2 else "SymbiYosys stopped with an error"
    return reason, "\n".join(lines)


def port_terms(text, top, ports):
    """The term of each port of the module that yosys wrote as SMT, in one state of the module.

    yosys writes a port of 1 bit as a Bool, which becomes a bit-vector of 1 bit here.
    """
    probes = "".join(f"(declare-const probe_{name} (_ BitVec {size}))(assert (= probe_{name} "
                     + (f"(ite (|{top}_n {name}| state) #b1 #b0)" if size == "1" else f"(|{top}_n {name}| state)")
                     + "))" for _, name, size in ports)
    assertions = z3.parse_smt2_string(text + f"(declare-const state |{top}_s|)" + probes)
    return {name: assertion.arg(1) for (_, name, _), assertion in zip(ports, assertions[-len(ports):])}


def parts(term):
    """The parts of a concat, from the top bit down."""
    if z3.is_app_of(term, z3.Z3_OP_CONCAT):
        return [part for child in term.children() for part in parts(child)]
    return [term]


def input_bits(inputs, terms):
    """The (function, term) pairs that put the bits of each input bit-vector in place of the functions of yosys.

    yosys declares a function of the state for some bits of the inputs, in any order, even
    across ports, and writes each input port as a concat of these functions, of extracts of
    them, and of (ite f #b1 #b0) for a bit that it holds as a Bool. With the bits in place,
    each output is a term of the inputs alone, which z3 can compare with the twin term by
    term: through the equalities of the ports, it cannot prove a 32-bit multiply.
    """
    bits, pairs = {}, []
    for name, var in inputs.items():
        high = var.size() - 1
        for part in parts(terms[name]):
            if z3.is_app_of(part, z3.Z3_OP_ITE):
                pairs.append((part.arg(0), z3.Extract(high, high, var) == 1))
            elif not z3.is_bv_value(part):
                function, top, bottom = ((part.arg(0), *part.params()) if z3.is_app_of(part, z3.Z3_OP_EXTRACT)
                                         else (part, part.size() - 1, 0))
                for k in range(top, bottom - 1, -1):
                    bits.setdefault(function, {})[k] = z3.Extract(high - top + k, high - top + k, var)
            high -= part.size()
    return pairs + [(function, z3.Concat(*[got[k] for k in reversed(range(function.size()))])
                     if function.size() > 1 else got[0]) for function, got in bits.items()]


def run_equiv(check, top, work, files):
    """None if z3 proves that each output of the module equals the value of the twin, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    smt = work / "module.smt2"
    result = subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv {' '.join(files)}; prep -top {top}; "
                             f"write_smt2 -wires {smt}"], capture_output=True, text=True)
    if result.returncode:
        return "yosys could not read the module", result.stdout + result.stderr
    text = smt.read_text()
    if STATE.search(text):
        return "the module holds state: prove it with a prove check", ""
    if check["twin_code"] is None:
        return f"{check['verifies'][0]} has no twin", ""
    ports = PORT.findall(text)
    inputs = {name: z3.BitVec(f"port_{name}", int(width)) for kind, name, width in ports if kind == "input"}
    outputs = {name: z3.BitVec(f"port_{name}", int(width)) for kind, name, width in ports if kind == "output"}
    try:
        width, values = twin.translate(check["twin_code"], check["twin"], inputs, constants())
    except twin.TwinError as error:
        return "the twin cannot be translated", f"{check['twin_path']}:{check['twin_line'] + error.line - 1}: {error}"
    if not isinstance(values, dict):
        return f"{check['twin']} returns one value, not a dict of the output ports", ""
    if sorted(values) != sorted(outputs):
        return (f"the twin gives the outputs {', '.join(sorted(values))}, but the module has the outputs "
                f"{', '.join(outputs)}"), ""
    # The outputs are natural numbers, and the values of the twin are in two's complement.
    terms = port_terms(text, top, ports)
    bits = input_bits(inputs, terms)
    wide = max([width] + [term.size() + 1 for term in outputs.values()])
    module = {name: z3.simplify(z3.ZeroExt(wide - term.size(), z3.substitute(terms[name], *bits)))
              for name, term in outputs.items()}
    values = {name: z3.simplify(z3.SignExt(wide - width, values[name])) for name in outputs}
    solver = z3.Solver()
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


RUNNERS = {"prove": run_prove, "equiv": run_equiv}
# The reasons of a check that could not read its code: a mutant that gives one does not build.
UNBUILT = ("Verilator could not build the testbench", "SymbiYosys stopped with an error")


# implements: doc.mutants-fail
def run_mutant(mutant, runner, check, top, work, files):
    """None if the check fails with the mutated file in place of the file, or (reason, output)."""
    copy = work / mutant["file"].removeprefix("build/")
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(mutant["text"])
    failure = runner(check, top, work / "run", [str(copy) if path == mutant["file"] else path for path in files])
    if failure is None:
        return "the check passes with the mutant", ""
    if failure[0] in UNBUILT:
        return "the mutant does not build", failure[1]
    return None


def main():
    manifest = json.loads(Path("build/checks.json").read_text())
    checks, mutants = manifest["checks"], manifest["mutants"]
    files = sources()
    objects, failures = compile_models()
    runners = {**RUNNERS, "test": functools.partial(run_test, objects=objects)}
    passed, failed = 0, len(failures)
    for path, output in failures:
        chapter, line = linemap.lookup(path, 1) or (path, 1)
        print(f"{chapter}:{line}: FAIL: [model] {path}: the C compiler could not build the model")
        for text in output.splitlines():
            print("    " + linemap.rewrite(text))
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
            failure = runners[check["kind"]](check, top, Path("build/run") / check["name"], files)
        if failure is None:
            print(f"{place}: PASS: [check] {check['name']}")
            passed += 1
            killers = [mutant for mutant in mutants if check["name"] in mutant["kills"]]
            for number, mutant in enumerate(killers, 1):
                work = Path("build/run") / check["name"] / f"mutant-{number}"
                survived = run_mutant(mutant, runners[check["kind"]], check, top, work, files)
                where = f"{mutant['path']}:{mutant['line']}: "
                if survived is None:
                    print(f"{where}PASS: [mutant] {check['name']}")
                    passed += 1
                    continue
                print(f"{where}FAIL: [mutant] {check['name']}: {survived[0]}")
                for text in survived[1].splitlines():
                    print("    " + linemap.rewrite(text))
                failed += 1
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
