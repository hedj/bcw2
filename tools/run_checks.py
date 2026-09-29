"""Run the checks of the book: each test with Verilator, each prove with SymbiYosys, and each equiv with z3.

make check runs it from the root of the repository, after the tangle. It reads
build/checks.json, which the tangle writes, runs the checks in parallel, and
prints their results in the chapter order. The top module of a test or a prove
is the first module in its code, and the top module of an equiv is its module
option. Each check reads build/rtl/bcw_params.sv and each Verilog file of
build/rtl.

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
point, whose outputs are free. That run leaves out the assertions of the other
modules, which hold for their own inputs whatever dut does. An assertion whose condition never holds passes
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

The runner runs each test or prove once more for each mutant that names it in
its kills option, with the mutated copy of the file in place of the file. The
check must fail: a mutant passes when the check fails, and fails when the check
passes or the mutated file does not build. Only the base case of a proof can
fail, so a mutant of a prove runs SymbiYosys in bmc mode, through
tools/smtbmc_blocks.py, which checks the steps 4 at a time: one query finds a
failure in any of 4 steps, where a query for each step first proves the earlier
steps clean. The runner reports each mutant of a check that passes, at the
chapter line of its directive:

    book/core/core.rst:95: FAIL: [mutant] core.rotation.test: the check passes with the mutant

Each schedule of build/schedules.json, which the weave writes, lists the rows of a
module with the prefix of the names of their registers, and each shared register that
no row holds, with its reason. The runner flattens the module with yosys and finds
the scope of each of its flip-flops: the instance that declares it. A register in a
scope of the private option, such as threads[3], belongs to one thread. Each other
register must have the prefix of a row, or stand on a line of the schedule. Each
name on a line must be such a register, and each prefix must match one. The runner
reports each schedule after the checks, at the chapter line of its directive:

    book/core/core.rst:1095: FAIL: [schedule] core
        the register spare of core is in no private scope, no row and no line of the schedule

It exits 1 if a check, a mutant or a schedule fails. Every run starts at once, the proves
first, since they take longest: a mutant, the cover or the cut point does not
wait for its check, and counts only if the check passes. The work of each check
is in build/run/<name>, of the cover and the cut point of a prove in
build/run/<name>.cover and build/run/<name>.havoc, and of each mutant in
build/run/<name>.mutant-<n>.
"""

import concurrent.futures
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
# The widest input that an equiv splits into one goal for each of its values.
SPLIT_WIDTH = 3
MODELS = Path("build/model")
OBJECTS = Path("build/run/model")
COMPILE = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-c"]
BLOCKS = Path(__file__).resolve().parent / "smtbmc_blocks.py"
SCHEDULES = Path("build/schedules.json")


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


def symbiyosys(check, top, work, files, mode, engine="smtbmc yices", steps="", smtbmc=()):
    """The result of SymbiYosys in the mode on the harness, after the extra yosys steps and
    with the options that name its smtbmc."""
    work.parent.mkdir(parents=True, exist_ok=True)
    job = work.parent / f"{work.name}.sby"
    reads = "".join(f"read -formal {Path(path).absolute()}\n" for path in files + [check["file"]])
    job.write_text(f"[options]\nmode {mode}\ndepth {check['depth']}\n\n[engines]\n{engine}\n\n"
                   f"[script]\n{reads}prep -top {top}\n{steps}")
    return subprocess.run(["sby", *smtbmc, "-f", "-d", str(work), str(job)], capture_output=True, text=True)


def proof_lines(result):
    return "\n".join(PROOF_PREFIX.sub("", text) for text in result.stdout.splitlines() if PROOF_LINES.search(text))


def run_prove(check, top, work, files, mode="prove", smtbmc=()):
    """None if SymbiYosys proves the properties in the mode, or (reason, output)."""
    result = symbiyosys(check, top, work, files, mode, smtbmc=smtbmc)
    if result.returncode == 0:
        return None
    reason = "the proof failed" if result.returncode == 2 else "SymbiYosys stopped with an error"
    return reason, proof_lines(result)


def run_base_case(check, top, work, files):
    """None if no assertion fails within the depth of the check, or (reason, output)."""
    return run_prove(check, top, work, files, "bmc", ("--smtbmc", str(BLOCKS)))


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
                       engine="smtbmc --keep-going yices",
                       steps=f"cutpoint {top}/dut\nchformal -assert -remove =A:top %n\n")
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
    blast = z3.Then("simplify", "solve-eqs", "bit-blast", "sat")
    solver = blast.solver()
    # With the narrowest input fixed, simplify removes each branch on it. split-clause makes a goal
    # for each value, and ParThen solves the goals in parallel: 63 s to 8 s for the multiply.
    narrowest = min(inputs.values(), key=lambda term: term.size(), default=None)
    if narrowest is not None and narrowest.size() <= SPLIT_WIDTH:
        solver = z3.ParThen("split-clause", blast).solver()
        solver.add(z3.Or([narrowest == value for value in range(2 ** narrowest.size())]))
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
def netlist(module, files, work):
    """The flattened module, as the JSON of yosys, or (reason, output)."""
    work.mkdir(parents=True, exist_ok=True)
    path = work / "netlist.json"
    result = subprocess.run(["yosys", "-q", "-p", f"read_verilog -sv {' '.join(files)}; hierarchy -top {module}; "
                             f"proc; flatten; write_json {path}"], capture_output=True, text=True)
    if result.returncode:
        return None, ("yosys could not read the module", result.stdout + result.stderr)
    return json.loads(path.read_text())["modules"][module], None


def instance(name, net):
    """The instance that declares a net: the path in its hdlname before its own name, or "" for the module."""
    path = net.get("attributes", {}).get("hdlname", "").split(" ")[:-1]
    return ".".join(path)


def registers(module):
    """The names of each register of the flattened module: of each flip-flop bit and each memory.

    flatten names a net after each port that it drives too, so the names of a bit are the names of the
    nets of the instance that declares the flip-flop, such as divide.units[3].unit.r, and of the wires
    that the module assigns from it. A register of a generate block keeps its block in its name, such
    as threads[0].own.
    """
    names = {}
    for name, net in module["netnames"].items():
        for bit in net["bits"]:
            names.setdefault(bit, []).append((instance(name, net), name))
    found = set()
    for name, cell in module["cells"].items():
        if cell["type"].startswith("$mem"):
            found.add(frozenset([cell["parameters"]["MEMID"].lstrip("\\")]))
        if "dff" not in cell["type"]:
            continue
        parts = re.sub(r"^\$flatten", "", name).replace("\\", "").split(".")
        scope = ".".join(parts[:-1])
        for bit in cell["connections"]["Q"]:
            own = frozenset(net for path, net in names.get(bit, []) if path == scope and not net.startswith("$"))
            found.add(own or frozenset([name]))
    return found


# implements: doc.schedule-registers
# implements: doc.schedule-names
def run_schedule(schedule, files):
    """None if each shared register of the module has a row or a line of the schedule, or (reason, output)."""
    module, failure = netlist(schedule["module"], files, Path("build/run") / f"schedule-{schedule['line']}")
    if failure:
        return failure
    private = [re.compile(rf"(^|\.){re.escape(name)}\[\d+\](\.|$)") for name in schedule["private"]]
    prefixes = [prefix for prefix in schedule["prefixes"] if prefix]
    listed = {name for names, _ in schedule["shared"] for name in names}
    problems, seen, used = [], set(), set()
    for names in registers(module):
        if any(pattern.search(name) for pattern in private for name in names):
            continue
        matched = {prefix for prefix in prefixes for name in names if name.startswith(prefix)}
        used |= matched
        seen |= names & listed
        if not matched and not names & listed:
            problems.append(f"the register {min(names, key=len)} of {schedule['module']} is in no private scope, "
                            "no row and no line of the schedule")
    problems += [f"the schedule lists {name}, which is no shared register of {schedule['module']}"
                 for name in sorted(listed - seen)]
    problems += [f"no register of {schedule['module']} has the prefix {prefix} of a row"
                 for prefix in prefixes if prefix not in used]
    return ("a register of the module is not in the schedule", "\n".join(sorted(set(problems)))) if problems else None


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


def top_of(check):
    """The top module of the check: its module option, or the first module of its code."""
    if check["kind"] == "equiv":
        return check["module"]
    module = MODULE.search(Path(check["file"]).read_text())
    return module.group(1) if module else None


def submit(pool, check, mutants, runners, files):
    """(the run of the check, the run of its meaning or None, its mutants, the run of each)."""
    top = top_of(check)
    if top is None:
        return None, None, [], []
    work = Path("build/run") / check["name"]
    run = pool.submit(runners[check["kind"]], check, top, work, files)
    meaning = pool.submit(run_meaning, check, top, work, files) if check["kind"] == "prove" else None
    killers = [mutant for mutant in mutants if check["name"] in mutant["kills"]]
    runner = run_base_case if check["kind"] == "prove" else runners[check["kind"]]
    return run, meaning, killers, [
        pool.submit(run_mutant, mutant, runner, check, top, work.with_name(f"{work.name}.mutant-{number}"), files)
        for number, mutant in enumerate(killers, 1)]


def outcome(run, meaning, killers, survivals):
    """(the failure of the check or None, the mutants that count, their runs)."""
    if run is None:
        return ("the code declares no module", ""), [], []
    failure = run.result() or (meaning.result() if meaning else None)
    return (failure, [], []) if failure else (None, killers, survivals)


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
    # Each run has its own work directory, so every run starts at once, the proves first, since
    # they take longest. The results print in the chapter order.
    with concurrent.futures.ProcessPoolExecutor() as pool:
        runs = {check["name"]: submit(pool, check, mutants, runners, files)
                for check in sorted(checks, key=lambda check: check["kind"] != "prove")}
        schedules = [schedule for schedule in (json.loads(SCHEDULES.read_text()) if SCHEDULES.exists() else [])
                     if schedule["module"]]
        inventories = [pool.submit(run_schedule, schedule, files) for schedule in schedules]
        results = [(check, *outcome(*runs[check["name"]])) for check in checks]
        for check, failure, killers, survivals in results:
            place = f"{check['path']}:{check['line']}"
            if failure:
                print(f"{place}: FAIL: [check] {check['name']}: {failure[0]}")
                for text in failure[1].splitlines():
                    print("    " + linemap.rewrite(text))
                failed += 1
                continue
            print(f"{place}: PASS: [check] {check['name']}")
            passed += 1
            for mutant, survival in zip(killers, survivals):
                survived = survival.result()
                where = f"{mutant['path']}:{mutant['line']}: "
                if survived is None:
                    print(f"{where}PASS: [mutant] {check['name']}")
                    passed += 1
                    continue
                print(f"{where}FAIL: [mutant] {check['name']}: {survived[0]}")
                for text in survived[1].splitlines():
                    print("    " + linemap.rewrite(text))
                failed += 1
        for schedule, inventory in zip(schedules, inventories):
            place, failure = f"{schedule['path']}:{schedule['line']}", inventory.result()
            if failure is None:
                print(f"{place}: PASS: [schedule] {schedule['module']}")
                passed += 1
                continue
            print(f"{place}: FAIL: [schedule] {schedule['module']}: {failure[0]}")
            for text in failure[1].splitlines():
                print("    " + linemap.rewrite(text))
            failed += 1
    print(f"run_checks: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
