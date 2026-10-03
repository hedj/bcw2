"""mutate.py KIND IN.json OUT.json: seed one fault in an ECP5 netlist, as synthesis or place and
route could make it. KIND is one of:
  synth-lut    the first LUT4 (by name) of a synth_ecp5 netlist, its INIT bit 0 inverted
  routed-carry the first adder cell (TRELLIS_COMB in mode CCU2 with A and B connected, by name) of a
               routed netlist, its INITVAL bit 3 inverted: the carry-generate half (LUT2)
  routed-swap  the inputs M of the first two flip-flops (by name) that take M, exchanged
"""
import json
import sys

kind, source, target = sys.argv[1:]
design = json.load(open(source))
cells = next(m for m in design["modules"].values() if not m["attributes"].get("blackbox"))["cells"]


def invert(cell, parameter, bit):
    value = cell["parameters"][parameter]
    i = len(value) - 1 - bit
    cell["parameters"][parameter] = value[:i] + ("1" if value[i] == "0" else "0") + value[i + 1:]


if kind == "synth-lut":
    invert(cells[min(n for n, c in cells.items() if c["type"] == "LUT4")], "INIT", 0)
elif kind == "routed-carry":
    adders = [n for n, c in cells.items() if c["type"] == "TRELLIS_COMB" and c["parameters"].get("MODE") == "CCU2"
              and c["connections"].get("A") and c["connections"].get("B")]
    invert(cells[min(adders)], "INITVAL", 3)
elif kind == "routed-swap":
    a, b = sorted(n for n, c in cells.items() if c["type"] == "TRELLIS_FF" and c["parameters"]["SD"].strip() == "0")[:2]
    cells[a]["connections"]["M"], cells[b]["connections"]["M"] = cells[b]["connections"]["M"], cells[a]["connections"]["M"]
else:
    raise SystemExit(f"unknown kind {kind}")
json.dump(design, open(target, "w"))
