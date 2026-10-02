import sys
import rodin_xml as rx
from pathlib import Path
root = sys.argv[1]
N = 33
W, TOP = str(2 ** N), str(2 ** N - 1)
BITS = range(N)


def total(term):
    return " + ".join(term(i) if i == 0 else f"{term(i)} ∗ {2 ** i}" for i in BITS)


def spec(d):
    rx.machine(d, "M0", ["a", "b", "z"], [("words", f"a ∈ 0 ‥ {TOP} ∧ b ∈ 0 ‥ {TOP} ∧ z ∈ 0 ‥ {TOP}", False)],
               [("INITIALISATION", [], [], [("act1", "a, b, z ≔ 0, 0, 0")], None),
                ("load", ["x", "y"], [("grd1", f"x ∈ 0 ‥ {TOP} ∧ y ∈ 0 ‥ {TOP}")], [("act1", "a, b ≔ x, y")], None),
                ("add", ["c", "r"], [("grd1", f"c ∈ 0 ‥ 1 ∧ r ∈ 0 ‥ {TOP} ∧ a + b = c ∗ {W} + r")], [("act1", "z ≔ r")], None),
                ("sub", ["n", "r"], [("grd1", f"n ∈ 0 ‥ 1 ∧ r ∈ 0 ‥ {TOP} ∧ a − b = r − n ∗ {W}")], [("act1", "z ≔ r")], None)])


def ripple(bit_a, bit_b, carry_in):
    """Guards of a ripple-carry adder: carries c1 … c33 and sums s0 … s32, with the carry into bit 0 given."""
    carry = lambda i: carry_in if i == 0 else f"c{i}"
    return ([("sums", " ∧ ".join(f"s{i} ∈ 0 ‥ 1" for i in BITS)),
             ("carries", " ∧ ".join(f"c{i + 1} ∈ 0 ‥ 1" for i in BITS))]
            + [(f"fa{i}", f"{bit_a(i)} + {bit_b(i)} + {carry(i)} = s{i} + 2 ∗ c{i + 1}") for i in BITS])


sums = [f"s{i}" for i in BITS]
carries = [f"c{i + 1}" for i in BITS]
result = total(lambda i: f"s{i}")

# 1. Integer registers, each operand split into its bits by event parameters.
d = rx.project(root, "AddInt"); spec(d)
abits, bbits = [f"a{i}" for i in BITS], [f"b{i}" for i in BITS]
split = [("abits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in abits) + " ∧ a = " + total(lambda i: f"a{i}")),
         ("bbits", " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in bbits) + " ∧ b = " + total(lambda i: f"b{i}"))]
rx.machine(d, "M1", ["a", "b", "z"], [], [
    ("INITIALISATION", [], [], [("act1", "a, b, z ≔ 0, 0, 0")], None),
    ("load", ["x", "y"], [("grd1", f"x ∈ 0 ‥ {TOP} ∧ y ∈ 0 ‥ {TOP}")], [("act1", "a, b ≔ x, y")], "load"),
    ("add", abits + bbits + sums + carries, split + ripple(lambda i: f"a{i}", lambda i: f"b{i}", "0"),
     [("act1", f"z ≔ {result}")], "add", [("c", f"c = c{N}"), ("r", f"r = {result}")]),
    ("sub", abits + bbits + sums + carries, split + ripple(lambda i: f"a{i}", lambda i: f"(1 − b{i})", "1"),
     [("act1", f"z ≔ {result}")], "sub", [("n", f"n = 1 − c{N}"), ("r", f"r = {result}")])], refines="M0")

# 2. Bit-function registers, glued to the integers by explicit sums.
d = rx.project(root, "AddBits"); spec(d)
ctx = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
       '<org.eventb.core.contextFile org.eventb.core.configuration="org.eventb.core.fwd" version="3">',
       '<org.eventb.core.constant name="c1" org.eventb.core.identifier="b2i"/>',
       '<org.eventb.core.axiom name="a1" org.eventb.core.label="b2i" org.eventb.core.predicate="b2i = {TRUE ↦ 1, FALSE ↦ 0}"/>',
       '<org.eventb.core.axiom name="a2" org.eventb.core.label="b2i_type" org.eventb.core.theorem="true" org.eventb.core.predicate="b2i ∈ BOOL ⤖ 0 ‥ 1"/>',
       "</org.eventb.core.contextFile>"]
(d / "C0.buc").write_text("\n".join(ctx) + "\n")
word = f"0 ‥ {N - 1} → BOOL"
val = lambda w: total(lambda i: f"b2i({w}({i}))")
out = "{" + ", ".join(f"{i} ↦ b2i∼(s{i})" for i in BITS) + "}"
rx.machine(d, "M1", ["wa", "wb", "wz"],
           [("words", f"wa ∈ {word} ∧ wb ∈ {word} ∧ wz ∈ {word}", False),
            ("glue_a", f"a = {val('wa')}", False), ("glue_b", f"b = {val('wb')}", False), ("glue_z", f"z = {val('wz')}", False)],
           [("INITIALISATION", [], [], [("act1", f"wa, wb, wz ≔ (0 ‥ {N - 1}) × {{FALSE}}, (0 ‥ {N - 1}) × {{FALSE}}, (0 ‥ {N - 1}) × {{FALSE}}")], None),
            ("load", ["p", "q"], [("grd1", f"p ∈ {word} ∧ q ∈ {word}")], [("act1", "wa, wb ≔ p, q")], "load",
             [("x", f"x = {val('p')}"), ("y", f"y = {val('q')}")]),
            ("add", sums + carries, ripple(lambda i: f"b2i(wa({i}))", lambda i: f"b2i(wb({i}))", "0"),
             [("act1", f"wz ≔ {out}")], "add", [("c", f"c = c{N}"), ("r", f"r = {result}")]),
            ("sub", sums + carries, ripple(lambda i: f"b2i(wa({i}))", lambda i: f"(1 − b2i(wb({i})))", "1"),
             [("act1", f"wz ≔ {out}")], "sub", [("n", f"n = 1 − c{N}"), ("r", f"r = {result}")])],
           refines="M0", sees="C0")
print("ok")
