import sys
import rodin_xml as rx
root = sys.argv[1]
N = 33
W, TOP = 2 ** N, 2 ** N - 1
AMOUNTS = range(32)          # k ∈ 0 ‥ 31
K = [f"k{j}" for j in range(5)]
T = ["a"] + [f"t{j + 1}" for j in range(5)]


def case_sll(k):
    return f"k = {k} ∧ a ∗ {2 ** k} = hi ∗ {W} + r ∧ r ∈ 0 ‥ {TOP}"


def case_srl(k):
    return f"k = {k} ∧ a = hi ∗ {2 ** k} + lo ∧ lo ∈ 0 ‥ {2 ** k - 1} ∧ r = hi"


def stage_sll(j):
    s = 2 ** (2 ** j)
    return (f"({K[j]} = 0 ⇒ {T[j + 1]} = {T[j]} ∧ x{j} = 0) ∧ "
            f"({K[j]} = 1 ⇒ {T[j]} ∗ {s} = x{j} ∗ {W} + {T[j + 1]} ∧ x{j} ∈ 0 ‥ {s - 1})")


def stage_srl(j):
    s = 2 ** (2 ** j)
    return (f"({K[j]} = 0 ⇒ {T[j + 1]} = {T[j]} ∧ x{j} = 0) ∧ "
            f"({K[j]} = 1 ⇒ {T[j]} = {T[j + 1]} ∗ {s} + x{j} ∧ x{j} ∈ 0 ‥ {s - 1})")


d = rx.project(root, "Shift")
spec = {"sll": case_sll, "srl": case_srl}
common = lambda case: [("amount", "k ∈ 0 ‥ 31"), ("parts", "hi ∈ ℕ ∧ lo ∈ ℕ"),
                       ("table", " ∨ ".join(f"({case(k)})" for k in AMOUNTS))]
init = ("INITIALISATION", [], [], [("act1", "a, z ≔ 0, 0")], None)
load = ("load", ["y"], [("grd1", f"y ∈ 0 ‥ {TOP}")], [("act1", "a ≔ y")])
rx.machine(d, "M0", ["a", "z"], [("words", f"a ∈ 0 ‥ {TOP} ∧ z ∈ 0 ‥ {TOP}", False)],
           [init, load + (None,)] + [(op, ["k", "hi", "lo", "r"], common(case), [("act1", "z ≔ r")], None)
                                     for op, case in spec.items()])
barrel = {"sll": stage_sll, "srl": stage_srl}
events = [init, load + ("load",)]
for op, case in spec.items():
    guards = common(case) + [
        ("bits", " ∧ ".join(f"{b} ∈ 0 ‥ 1" for b in K) + " ∧ k = " + " + ".join(f"{2 ** j} ∗ {b}" if j else b for j, b in enumerate(K))),
        ("wires", " ∧ ".join(f"{t} ∈ 0 ‥ {TOP}" for t in T[1:]))]
    guards += [(f"stage{j}", barrel[op](j)) for j in range(5)]
    events.append((op, ["k", "hi", "lo", "r"] + K + T[1:] + [f"x{j}" for j in range(5)], guards, [("act1", "z ≔ t5")], op))
rx.machine(d, "M1", ["a", "z"], [], events, refines="M0")
print("ok")
