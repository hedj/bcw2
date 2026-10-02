"""The Shift probe: 32-bit logical shifts, with shifts as offsets in indexed bit sums.

M0 states each shift as a table over the amount k: case k is the sum of the bits of a, each moved k
places. M1 refines it with a five-stage barrel: stage j moves every bit 2^j places when bit j of k
is 1. Every relation is linear over 0/1 bits; nothing divides or takes a remainder.
"""
import sys
import rodin_xml as rx
from bridge2 import ite, total

root = sys.argv[1]
N = 32
TOP = 2 ** N - 1
A = [f"a{i}" for i in range(N)]
K = [f"k{j}" for j in range(5)]
STAGES = [A] + [[f"t{j + 1}_{i}" for i in range(N)] for j in range(5)]


def moved(bits, op, s):
    """The word whose bit i is bits[i - s] (sll) or bits[i + s] (srl), and 0 where that is outside."""
    if op == "sll":
        return total((i, bits[i - s]) for i in range(s, N))
    return total((i, bits[i + s]) for i in range(N - s))


def table(op):
    out = moved(A, op, 31)
    for s in reversed(range(31)):
        out = ite(f"k = {s}", moved(A, op, s), out)
    return out


def stage(op, j):
    """Stage j: bit i of the next stage is bit i of this one, or bit i ∓ 2^j when k_j = 1."""
    s, here, nxt = 2 ** j, STAGES[j], STAGES[j + 1]
    src = (lambda i: here[i - s] if i >= s else "0") if op == "sll" else (lambda i: here[i + s] if i + s < N else "0")
    return " ∧ ".join(f"({K[j]} = 0 ⇒ {nxt[i]} = {here[i]}) ∧ ({K[j]} = 1 ⇒ {nxt[i]} = {src(i)})" for i in range(N))


bits = lambda names: " ∧ ".join(f"{b} ∈ 0 ‥ 1" for b in names)
common = [("amount", "k ∈ 0 ‥ 31"), ("abits", bits(A) + " ∧ a = " + total(enumerate(A)))]
d = rx.project(root, "Shift")
init = ("INITIALISATION", [], [], [("act1", "a, z ≔ 0, 0")], None)
load = ("load", ["y"], [("grd1", f"y ∈ 0 ‥ {TOP}")], [("act1", "a ≔ y")])
rx.machine(d, "M0", ["a", "z"], [("words", f"a ∈ 0 ‥ {TOP} ∧ z ∈ 0 ‥ {TOP}", False)],
           [init, load + (None,)] + [(op, ["k"] + A, common, [("act1", f"z ≔ {table(op)}")], None)
                                     for op in ("sll", "srl")])
events = [init, load + ("load",)]
for op in ("sll", "srl"):
    wires = [b for stage_bits in STAGES[1:] for b in stage_bits]
    guards = common + [("kbits", bits(K) + " ∧ k = " + total(enumerate(K))), ("wires", bits(wires))]
    guards += [(f"stage{j}", stage(op, j)) for j in range(5)]
    events.append((op, ["k"] + A + K + wires, guards, [("act1", f"z ≔ {total(enumerate(STAGES[5]))}")], op))
rx.machine(d, "M1", ["a", "z"], [], events, refines="M0")
print("ok")
