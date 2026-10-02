import sys
from pathlib import Path
import bridge2
import rodin_xml as rx
from bridge2 import ite, total
root, netlist, name = sys.argv[1], sys.argv[2], sys.argv[3]
W = 2 ** 32
A, B = [f"a{i}" for i in range(32)], [f"b{i}" for i in range(32)]
k = total((i, f"b{i}") for i in range(5))


def table(shifted):
    out = shifted(31)
    for s in reversed(range(31)):
        out = ite(f"{k} = {s}", shifted(s), out)
    return out


Z = [f"r{i}" for i in range(32)]
R = total((i, f"r{i}") for i in range(32))
GATE = {op: (Z, [(f"{op}_bits", bridge2.gate_guard(op, A, B, Z))]) for op in ("and", "or", "xor")}
SPEC = {   # op: (guard, y)
    "add": ("f3 = 0 ∧ alt = 0", ite(f"a + b < {W}", "a + b", f"a + b − {W}")),
    "sub": ("f3 = 0 ∧ alt = 1", ite("a ≥ b", "a − b", f"a − b + {W}")),
    "sll": ("f3 = 1", table(lambda s: total((i, f"a{i - s}") for i in range(s, 32)))),
    "slt": ("f3 = 2", ite(f"a − {W} ∗ a31 < b − {W} ∗ b31", 1, 0)),
    "sltu": ("f3 = 3", ite("a < b", 1, 0)),
    "xor": ("f3 = 4", R),
    "srl": ("f3 = 5 ∧ alt = 0", table(lambda s: total((i, f"a{i + s}") for i in range(32 - s)))),
    "sra": ("f3 = 5 ∧ alt = 1", table(lambda s: total((i, f"a{i + s}") for i in range(32 - s)) + f" + a31 ∗ {W - 2 ** (32 - s)}")),
    "or": ("f3 = 6", R),
    "and": ("f3 = 7", R),
}
common = [("ranges", "f3 ∈ 0 ‥ 7 ∧ alt ∈ 0 ‥ 1"),
          ("abits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in A) + " ∧ a = " + total((i, f"a{i}") for i in range(32))),
          ("bbits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in B) + " ∧ b = " + total((i, f"b{i}") for i in range(32)))]
params = ["f3", "alt", "a", "b"] + A + B
init = ("INITIALISATION", [], [], [("act1", "y ≔ 0")], None)
d = rx.project(root, name)
rx.machine(d, "M0", ["y"], [("word", f"y ∈ 0 ‥ {W - 1}", False)],
           [init] + [(op, params + GATE.get(op, ([], []))[0], common + [("op", g)] + GATE.get(op, ([], []))[1],
                      [("act1", f"y ≔ {y}")], None) for op, (g, y) in SPEC.items()])
OP = {(0, 0): "add", (0, 1): "sub", (2, 0): "slt", (2, 1): "slt", (3, 0): "sltu", (3, 1): "sltu", (4, 0): "xor",
      (4, 1): "xor", (5, 0): "srl", (5, 1): "sra", (6, 0): "or", (6, 1): "or", (7, 0): "and", (7, 1): "and",
      (1, 0): "sll", (1, 1): "sll"}
events = [init]
for (f3, alt), op in sorted(OP.items()):
    n = bridge2.Netlist(f"{netlist}/alu_{f3}_{alt}.json", f"alu_{f3}_{alt}", ["a", "b"])
    rtl = n.translate()["y"]
    # Each parameter of the specification is a bit that the netlist names, so it needs no witness;
    # the bits of the output port of a gate are r0 … r31.
    missing = [x for x in GATE.get(op, ([], []))[0] if x not in n.params]
    if missing:
        raise SystemExit(f"{op}_{f3}_{alt}: the netlist has no bit {missing[0]} of the specification "
                         f"({len(missing)} missing): the output must come from a {op} gate")
    events.append((f"{op}_{f3}_{alt}", params + n.params, common + [("control", f"f3 = {f3} ∧ alt = {alt}")] + n.guards,
                   [("act1", f"y ≔ {rtl}")], op))
rx.machine(d, "M1", ["y"], [], events, refines="M0")
print(name, "ok:", {f.name: f.stat().st_size // 1024 for f in d.glob("*.bum")}, "KB")
