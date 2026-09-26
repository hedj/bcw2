"""Run the checks of the book: each test with Verilator, and each prove with SymbiYosys.

make check runs it from the root of the repository, after the tangle. It reads
build/checks.json, which the tangle writes, and runs each check in the chapter
order. The first module in the code of a check is its top module. Each check
reads build/rtl/bcw_params.sv and each Verilog file of build/rtl.

A test passes when Verilator builds the testbench and the testbench exits 0. A
prove passes when SymbiYosys proves each assertion with the smtbmc engine and
Yices, to the depth of the check. The runner cannot run an equiv check yet, and
prints a note for it.

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

import linemap

MODULE = re.compile(r"^\s*module\s+(\w+)", re.MULTILINE)
# The lines of SymbiYosys that tell why a proof failed, and its last line.
PROOF_LINES = re.compile(r"Assert failed|ERROR|DONE")
PROOF_PREFIX = re.compile(r"^SBY\s+[\d:]+\s+\[[^\]]*\]\s+")


def sources():
    """The package of PARAMETERs, then each Verilog file of build/rtl."""
    return ["build/rtl/bcw_params.sv"] + sorted(str(path) for path in Path("build/rtl").rglob("*.v"))


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


RUNNERS = {"test": run_test, "prove": run_prove}


def main():
    checks = json.loads(Path("build/checks.json").read_text())
    passed = failed = skipped = 0
    for check in checks:
        place = f"{check['path']}:{check['line']}"
        if check["kind"] not in RUNNERS:
            print(f"{place}: NOTE: [check] {check['name']}: the runner cannot run an {check['kind']} check yet")
            skipped += 1
            continue
        module = MODULE.search(Path(check["file"]).read_text())
        if module is None:
            failure = "the code declares no module", ""
        else:
            failure = RUNNERS[check["kind"]](check, module.group(1), Path("build/run") / check["name"])
        if failure is None:
            print(f"{place}: PASS: [check] {check['name']}")
            passed += 1
            continue
        reason, output = failure
        print(f"{place}: FAIL: [check] {check['name']}: {reason}")
        for text in output.splitlines():
            print("    " + linemap.rewrite(text))
        failed += 1
    print(f"run_checks: {passed} passed, {failed} failed, {skipped} not run")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
