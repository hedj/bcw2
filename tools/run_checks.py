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
Yices, to the depth of the check, and the proof means something: SymbiYosys
reaches the condition of each assertion within that depth (a cover of its
enable), and each assertion of the harness fails when the instance dut is a cut
point, whose outputs are free. An assertion whose condition never holds passes
by default, and one that holds for any dut does not test the design.

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
build/run/<name>, of the cover and the cut point of a prove in
build/run/<name>.cover and build/run/<name>.havoc, and of each mutant in
build/run/<name>/mutant-<n>.
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
# The place of each assertion whose enable a cover reached, and of each assertion that failed.
REACHED = re.compile(r"Reached cover statement in step \d+ at \w+: (\S+)")
FAILED = re.compile(r"Assert failed in \w+: (\S+)")
DUT = re.compile(r"\bdut\s*\(")
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


def symbiyosys(check, top, work, files, mode, engine="smtbmc yices", steps=""):
    """The result of SymbiYosys in the mode on the harness, after the extra yosys steps."""
    work.parent.mkdir(parents=True, exist_ok=True)
    job = work.parent / f"{work.name}.sby"
    reads = "".join(f"read -formal {Path(path).absolute()}\n" for path in files + [check["file"]])
    job.write_text(f"[options]\nmode {mode}\ndepth {check['depth']}\n\n[engines]\n{engine}\n\n"
                   f"[script]\n{reads}prep -top {top}\n{steps}")
    return subprocess.run(["sby", "-f", "-d", str(work), str(job)], capture_output=True, text=True)


def proof_lines(result):
    return "\n".join(PROOF_PREFIX.sub("", text) for text in result.stdout.splitlines() if PROOF_LINES.search(text))


def run_prove(check, top, work, files):
    """None if SymbiYosys proves the properties, or (reason, output)."""
    result = symbiyosys(check, top, work, files, "prove")
    if result.returncode == 0:
        return None
    reason = "the proof failed" if result.returncode == 2 else "SymbiYosys stopped with an error"
    return reason, proof_lines(result)


# implements: doc.proof-meaning
def run_meaning(check, top, work, files):
    """None if each assertion of a proof can apply and tests the design, or (reason, output)."""
    if not DUT.search(Path(check["file"]).read_text()):
        return "the harness has no instance dut", ""
    cover = symbiyosys(check, top, work.with_name(work.name + ".cover"), files, "cover",
                       steps="chformal -assert -coverenable\nchformal -assert -remove\n")
    if cover.returncode:
        lines = [PROOF_PREFIX.sub("", text) for text in cover.stdout.splitlines() if "nreached" in text]
        return "the condition of an assertion never holds", "\n".join(lines) or proof_lines(cover)
    harness = {place for place in REACHED.findall(cover.stdout) if place.startswith(str(Path(check["file"]).absolute()))}
    havoc = symbiyosys(check, top, work.with_name(work.name + ".havoc"), files, "bmc",
                       engine="smtbmc --keep-going yices", steps=f"cutpoint {top}/dut\n")
    held = sorted(harness - set(FAILED.findall(havoc.stdout)))
    if held:
        return "an assertion holds whatever dut does", "\n".join(f"{place}: holds with a free dut" for place in held)
    return None


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


def cut_points(inputs, terms):
    """The powers of two that the terms divide each integer input by, with 0 and its width: the cuts of each input."""
    cuts = {name: {0, size} for name, size in inputs.items()}
    seen, stack = set(), list(terms)
    while stack:
        term = stack.pop()
        if term.get_id() in seen:
            continue
        seen.add(term.get_id())
        stack.extend(term.children())
        if (z3.is_app_of(term, z3.Z3_OP_IDIV) or z3.is_app_of(term, z3.Z3_OP_MOD)) and z3.is_int_value(term.arg(1)):
            name, divisor = str(term.arg(0)), term.arg(1).as_long()
            if name in cuts and divisor & (divisor - 1) == 0 and 0 < divisor.bit_length() - 1 < inputs[name]:
                cuts[name].add(divisor.bit_length() - 1)
    return cuts


def pieces(inputs, terms):
    """(pairs, bounds) that write each integer input as a sum of pieces, cut where the terms divide it.

    Each x div 2^k and x mod 2^k of an input becomes a sum of its pieces, and so does the
    input itself. Each side is then a polynomial of the same pieces, whose identity z3 finds
    when it normalises the sums of products; with the div and mod in place, it does not.
    """
    divisions, wholes, bounds = [], [], []
    for name, points in cut_points(inputs, terms).items():
        var, points = z3.Int(name), sorted(points)
        chunks = [(low, z3.Int(f"{name}_{low}")) for low in points[:-1]]
        bounds += [z3.And(0 <= chunk, chunk < 2 ** (high - low)) for (low, chunk), high in zip(chunks, points[1:])]
        for cut in points[1:-1]:
            divisions.append((var % 2 ** cut, z3.Sum([chunk * 2 ** low for low, chunk in chunks if low < cut])))
            divisions.append((var / 2 ** cut, z3.Sum([chunk * 2 ** (low - cut) for low, chunk in chunks if low >= cut])))
        wholes.append((var, z3.Sum([chunk * 2 ** low for low, chunk in chunks])))
    return divisions, wholes, bounds


def same_integers(check, top, inputs):
    """None if z3 proves the twin function of the check equal to the function of the module over the integers.

    A check names another twin function where the module computes its outputs in steps
    that z3 cannot relate over bit-vectors, such as the partial products of a multiply. The
    function named after the module states the rule; this step proves that the steps give
    the same integers.
    """
    code, split = check["twin_code"], check["twin"]
    try:
        rule, _ = twin.integers(code, top, inputs, constants())
        steps, _ = twin.integers(code, split, inputs, constants())
    except twin.TwinError as error:
        return "the twin cannot be translated", f"{check['twin_path']}:{check['twin_line'] + error.line - 1}: {error}"
    if not (isinstance(rule, dict) and isinstance(steps, dict)) or sorted(rule) != sorted(steps):
        return f"the twin functions {split} and {top} give different outputs", ""
    differ = z3.Or([rule[name] != steps[name] for name in rule])
    divisions, wholes, bounds = pieces({str(term): term.size() for term in inputs.values()}, [differ])
    solver = z3.Solver()
    solver.add(bounds)
    solver.add(z3.simplify(z3.substitute(z3.substitute(differ, *divisions), *wholes), som=True))
    verdict = solver.check()
    if verdict == z3.unsat:
        return None
    if verdict == z3.unknown:
        return f"z3 could not decide that {split} equals {top} over the integers", ""
    model = solver.model()

    def number(term):
        return model.eval(z3.substitute(z3.substitute(term, *divisions), *wholes), model_completion=True).as_long()
    shown = ", ".join(f"{name}={number(z3.Int(str(term)))}" for name, term in inputs.items())
    return f"the twin functions {split} and {top} differ", "\n".join(
        f"{shown}: {top} {name}={number(rule[name])}, {split} {name}={number(steps[name])}"
        for name in rule if number(rule[name]) != number(steps[name]))


def run_equiv(check, top, work, files):
    """None if z3 proves that each output of the module equals the value of the twin, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    smt = work / "module.smt2"
    result = subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv {' '.join(files)}; prep -flatten -top {top}; "
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
    if check["twin"] != top:
        found = same_integers(check, top, inputs)
        if found:
            return found
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
    # Bit-blasting and SAT alone: the default solver of z3 took from 3 to more than 200 seconds on
    # the same partial products, as the order of its terms changed.
    solver = z3.Then("simplify", "solve-eqs", "bit-blast", "sat").solver()
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
        if failure is None and check["kind"] == "prove":
            failure = run_meaning(check, top, Path("build/run") / check["name"], files)
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
