"""Measure the timing of the core: synthesise core_top once, then place and route it for each seed.

make timing runs it from the root of the repository, after the tangle. yosys synthesises the top
module core_top from each package and Verilog file of build/rtl into build/timing/top.json.
nextpnr-ecp5 then places it with the static placer and routes it once for each seed, at the
frequency of core.clock, several seeds at a time. Each run writes build/timing/seed-<n>.log. The
section Timing of readme.build gives the evidence for the static placer and the 32 seeds.

It prints the maximum frequency of each seed, then the minimum, the median and the mean. It exits
1 if a run fails, or if a seed does not reach core.clock, the value of core.timing-closure.
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from run_checks import sources

TOP = "core_top"
WORK = Path("build/timing")
DEVICE = ["--25k", "--package", "CABGA256"]
PLACER = "static"
SEEDS = 32
MAX_FREQUENCY = re.compile(r"Max frequency for clock[^:]*: ([0-9.]+) MHz")


def synthesise(files, top, netlist):
    """None if yosys synthesises the top module into netlist, or (the output of yosys)."""
    script = f"read_verilog -sv {' '.join(files)}; synth_ecp5 -top {top} -json {netlist}"
    result = subprocess.run(["yosys", "-q", "-p", script], capture_output=True, text=True)
    return None if result.returncode == 0 else result.stdout + result.stderr


def place(netlist, mhz, seed, log):
    """The maximum frequency in MHz after routing, or None if nextpnr fails. The output goes to log."""
    result = subprocess.run(["nextpnr-ecp5", *DEVICE, "--json", str(netlist), "--out-of-context",
                             "--freq", f"{mhz:g}", "--placer", PLACER, "--seed", str(seed), "--threads", "1"],
                            capture_output=True, text=True)
    output = result.stdout + result.stderr
    Path(log).write_text(output)
    found = MAX_FREQUENCY.findall(output)
    return float(found[-1]) if result.returncode == 0 and found else None


def clock_mhz():
    """The value of core.clock in MHz, from build/checks.json, which the tangle writes."""
    constants = json.loads(Path("build/checks.json").read_text())["constants"]
    if "CORE_CLOCK" not in constants:
        raise SystemExit("timing: build/checks.json has no CORE_CLOCK: run make tangle")
    return constants["CORE_CLOCK"] / 10 ** 6


def main():
    parser = argparse.ArgumentParser(description="Place and route core_top for each seed, and report its frequency.")
    parser.add_argument("--seeds", type=int, default=SEEDS, help=f"the number of seeds, from 1 (default {SEEDS})")
    arguments = parser.parse_args()
    if arguments.seeds < 1:
        parser.error("--seeds must be 1 or more")
    mhz = clock_mhz()
    WORK.mkdir(parents=True, exist_ok=True)
    netlist = WORK / "top.json"
    failure = synthesise(sources(), TOP, netlist)
    if failure is not None:
        print(f"timing: yosys could not synthesise {TOP}\n{failure}")
        return 1
    seeds = range(1, arguments.seeds + 1)
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        results = list(pool.map(lambda seed: place(netlist, mhz, seed, WORK / f"seed-{seed}.log"), seeds))
    for seed, fmax in zip(seeds, results):
        verdict = "FAIL: nextpnr failed" if fmax is None else "PASS" if fmax >= mhz else "FAIL"
        print(f"timing: seed {seed}: {'-' if fmax is None else f'{fmax:.2f} MHz'} {verdict}")
    reached = [fmax for fmax in results if fmax is not None]
    if reached:
        print(f"timing: {len(results)} seeds at {mhz:g} MHz, {PLACER} placer: minimum {min(reached):.2f}, "
              f"median {statistics.median(reached):.2f}, mean {statistics.mean(reached):.2f} MHz")
    return 0 if len(reached) == len(results) and min(reached) >= mhz else 1


if __name__ == "__main__":
    sys.exit(main())
