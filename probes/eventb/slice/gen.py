"""Writes the slice: M0 and M1 from spec.py, and M2 generated from a netlist of ring.v.

M2 keeps M1's variables, which the RTL names alike. It has one event for each value of the reset
input: with rst_n = 0 it refines reset, with rst_n = 1 it refines clock. Each assigns every register
its next value from the netlist. Every register powers up in any value of its width.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))
import rodin_xml as rx
from bridge_seq import Sequential
import spec

root, netlist, name = sys.argv[1], sys.argv[2], sys.argv[3]
n = Sequential(netlist, "ring", [])
after, widths = n.next_state(), n.widths()
if set(widths) != set(spec.M1["variables"]):
    raise SystemExit(f"the registers {sorted(widths)} are not M1's variables {sorted(spec.M1['variables'])}")
d = rx.project(root, name)
if hasattr(spec, "C0"):
    rx.context(d, "C0", **spec.C0)
rx.machine(d, "M0", **spec.M0)
rx.machine(d, "M1", **spec.M1, refines="M0")
types = [(f"{v}_width", f"{v} ∈ 0 ‥ {2 ** w - 1}", False) for v, w in widths.items()]
inputs = [("in_type", "in ∈ 0 ‥ 255")]
clock = lambda rst: [(v, f"{v} ≔ {e}".replace("rst_n", str(rst))) for v, e in after.items()]
events = [("INITIALISATION", [], [], [(f"init_{v}", f"{v} :∈ 0 ‥ {2 ** w - 1}") for v, w in widths.items()], None),
          ("reset", ["in"], inputs, clock(0), "reset"),
          ("clock", ["in"], inputs, clock(1), "clock")]
rx.machine(d, "M2", list(widths), types, events, refines="M1", sees="C0" if hasattr(spec, "C0") else None)
print(name, "ok:", {f.name: f.stat().st_size for f in d.glob("*.bum")}, "bytes")
