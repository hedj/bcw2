"""Probe: core_alu netlists bit-blasted by yosys techmap, translated bit by bit, against M0 of the ALU specification.

Usage: gen_bits.py ROOT NETLISTS, with the netlists of netlists.sh. Each project is one way to write the lowest
machine: one guard for all gates (BitsCtlXor, BitsAdd), or one guard per gate in the order of the cones of the
output bits, with a theorem after each cone (the others).
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))
import rodin_xml as rx
from bridge2 import ite, total

GATES = {   # z of a single-bit gate, as linear constraints on 0/1 values
    "$_AND_": lambda z, a, b: f"{z} ≤ {a} ∧ {z} ≤ {b} ∧ {a} + {b} ≤ 1 + {z}",
    "$_OR_": lambda z, a, b: f"{a} ≤ {z} ∧ {b} ≤ {z} ∧ {z} ≤ {a} + {b}",
    "$_XOR_": lambda z, a, b: f"{a} − {b} ≤ {z} ∧ {b} − {a} ≤ {z} ∧ {z} ≤ {a} + {b} ∧ {z} ≤ 2 − {a} − {b}",
}


def translate(path, top):
    """The parameters, guards and output bit names of a single-bit netlist with inputs a, b and output y."""
    m = json.load(open(path))["modules"][top]
    value = {"0": "0", "1": "1"}
    for port in ("a", "b"):
        for i, bit in enumerate(m["ports"][port]["bits"]):
            value[bit] = f"{port}{i}"
    out = {bit: f"r{i}" for i, bit in enumerate(m["ports"]["y"]["bits"])}
    params, guards, reads, inputs, pending, k = [], [], {}, {}, [c for c in m["cells"].values() if c["type"] != "$scopeinfo"], 0
    while pending:
        later = []
        for c in pending:
            x = c["connections"]
            ins = [x[p][0] for p in ("A", "B") if p in x]
            if any(i not in value for i in ins):
                later.append(c)
                continue
            y = x["Y"][0]
            if c["type"] == "$_NOT_":
                value[y] = f"(1 − {value[ins[0]]})"
                continue
            name = out.get(y, f"g{k}")
            k += 1
            params.append(name)
            guards.append(f"{name} ∈ 0 ‥ 1 ∧ " + GATES[c["type"]](name, value[ins[0]], value[ins[1]]))
            reads[name] = {w for i in ins for w in re.findall(r"\b[gr]\d+\b", value[i])}
            inputs[name] = (c["type"], [value[i] for i in ins])
            value[y] = name
        if len(later) == len(pending):
            raise SystemExit(f"{path}: cells with unknown inputs: {[c['type'] for c in later][:5]}")
        pending = later
    # An output bit that no gate drives (a constant, an input or a NOT) is named by an equation.
    for bit, name in out.items():
        if value.get(bit) != name:
            params.append(name)
            guards.append(f"{name} = {value[bit]}")
            reads[name] = set(re.findall(r"\b[gr]\d+\b", value[bit]))
    return params, guards, reads, inputs


W = 2 ** 32
A, B, Z = [f"a{i}" for i in range(32)], [f"b{i}" for i in range(32)], [f"r{i}" for i in range(32)]
R = total((i, f"r{i}") for i in range(32))
common = [("ranges", "f3 ∈ 0 ‥ 7 ∧ alt ∈ 0 ‥ 1"),
          ("abits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in A) + " ∧ a = " + total((i, f"a{i}") for i in range(32))),
          ("bbits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in B) + " ∧ b = " + total((i, f"b{i}") for i in range(32)))]
xor_bits = " ∧ ".join(f"{z} ∈ 0 ‥ 1 ∧ " + GATES["$_XOR_"](z, a, b) for z, a, b in zip(Z, A, B))
SPEC = {"xor": ("f3 = 4", Z, [("xor_bits", xor_bits)], R),
        "add": ("f3 = 0 ∧ alt = 0", [], [], ite(f"a + b < {W}", "a + b", f"a + b − {W}"))}
params = ["f3", "alt", "a", "b"] + A + B
init = ("INITIALISATION", [], [], [("act1", "y ≔ 0")], None)


def xor_theorem(i):
    return f"r{i} ∈ 0 ‥ 1 ∧ " + GATES["$_XOR_"](f"r{i}", f"a{i}", f"b{i}")


def add_theorem(i):
    """The low i + 1 bits of the sum are right, up to one carry out."""
    low = lambda x: total((j, f"{x}{j}") for j in range(i + 1))
    gap = f"{low('a')} + {low('b')} − ({low('r')})"
    return f"{gap} = 0 ∨ {gap} = {2 ** (i + 1)}"


def carry(inputs, i):
    """The carry into bit i: the input of r_i's XOR that is not a_i XOR b_i."""
    kind, ins = inputs[f"r{i}"]
    assert kind == "$_XOR_", (i, kind)
    rest = [x for x in ins if inputs.get(x) not in (("$_XOR_", [f"a{i}", f"b{i}"]), ("$_XOR_", [f"b{i}", f"a{i}"]))]
    assert len(rest) == 1, (i, ins)
    return rest[0]


def inc_theorem(i, c):
    """The low i + 1 bits of the sum are right, and c is the carry out of them."""
    low = lambda x: total((j, f"{x}{j}") for j in range(i + 1))
    return f"{low('a')} + {low('b')} − ({low('r')}) = {2 ** (i + 1)} ∗ {c}"


def cone_guards(params, guards, reads, theorem, inputs=None):
    """One guard per gate: the gates of the cone of r0, then a theorem for bit 0, then those of r1 not yet given, …"""
    guard, done, out = dict(zip(params, guards)), set(), []
    def visit(n):
        if n in done or n not in guard:
            return
        done.add(n)
        for m in sorted(reads.get(n, ())):
            visit(m)
        out.append((f"gate_{n}", guard[n]))
    for i in range(32):
        visit(f"r{i}")
        if theorem is inc_theorem and i < 31:
            c = carry(inputs, i + 1)
            visit(c)
            out.append((f"bit{i}", inc_theorem(i, c), True))
        else:
            out.append((f"bit{i}", (add_theorem if theorem is inc_theorem else theorem)(i), True))
    assert done == set(params), "a gate outside every cone"
    return out


root, net = sys.argv[1], sys.argv[2]
CONES = {"BitsCone": xor_theorem, "BitsAddCone": add_theorem, "BitsRippleCone": add_theorem, "BitsRippleInc": inc_theorem}
for name, op, nets in [("BitsCtlXor", "xor", ["ctl_xor_4_0", "ctl_xor_4_1"]), ("BitsCone", "xor", ["ctl_xor_4_0", "ctl_xor_4_1"]),
                       ("BitsAdd", "add", ["book_0_0"]),
                       ("BitsAddCone", "add", ["book_0_0"]), ("BitsRippleCone", "add", ["ripple_0_0"]),
                       ("BitsRippleInc", "add", ["ripple_0_0"])]:
    g, extra, guards, y = SPEC[op]
    d = rx.project(root, name)
    rx.machine(d, "M0", ["y"], [("word", f"y ∈ 0 ‥ {W - 1}", False)],
               [init, (op, params + extra, common + [("op", g)] + guards, [("act1", f"y ≔ {y}")], None)])
    events = [init]
    for n in nets:
        f3, alt = n.split("_")[-2:]
        p, gs, reads, inputs = translate(f"{net}/{n}.json", f"alu_{f3}_{alt}")
        body = cone_guards(p, gs, reads, CONES[name], inputs) if name in CONES else [("gates", " ∧ ".join(gs))]
        events.append((f"{op}_{f3}_{alt}", params + p, common + [("control", f"f3 = {f3} ∧ alt = {alt}")] + body,
                       [("act1", f"y ≔ {R}")], op))
        print(name, n, "parameters", len(p), "gate guards", len(gs))
    rx.machine(d, "M1", ["y"], [], events, refines="M0")
