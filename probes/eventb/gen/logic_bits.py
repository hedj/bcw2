import sys
import rodin_xml as rx
root = sys.argv[1]
N = 33
TOP = str(2 ** N - 1)
BITS = range(N)
A, B, Z, T, O, NN = ([f"{p}{i}" for i in BITS] for p in ("a", "b", "z", "t", "o", "n"))


def total(term):
    return " + ".join(term(i) if i == 0 else f"({term(i)}) ∗ {2 ** i}" for i in BITS)


def ranged(names):
    return " ∧ ".join(f"{x} ∈ 0 ‥ 1" for x in names)


def each(form):
    return " ∧ ".join(form(i) for i in BITS)


split = [("abits", ranged(A) + " ∧ a = " + total(lambda i: f"a{i}")),
         ("bbits", ranged(B) + " ∧ b = " + total(lambda i: f"b{i}"))]
init = ("INITIALISATION", [], [], [("act1", "a, b, z ≔ 0, 0, 0")], None)
load = ("load", ["x", "y"], [("grd1", f"x ∈ 0 ‥ {TOP} ∧ y ∈ 0 ‥ {TOP}")], [("act1", "a, b ≔ x, y")])
words = [("words", f"a ∈ 0 ‥ {TOP} ∧ b ∈ 0 ‥ {TOP} ∧ z ∈ 0 ‥ {TOP}", False)]

# 2. Linear constraints on the result bits.
d = rx.project(root, "LogicLinBits")
AND = lambda z, x, y: f"{z} ≤ {x} ∧ {z} ≤ {y} ∧ {x} + {y} ≤ 1 + {z}"
OR = lambda z, x, y: f"{x} ≤ {z} ∧ {y} ≤ {z} ∧ {z} ≤ {x} + {y}"
result = [("act1", "z ≔ " + total(lambda i: f"z{i}"))]
lin = {"and": ([], lambda i: AND(f"z{i}", f"a{i}", f"b{i}")),
       "or": ([], lambda i: OR(f"z{i}", f"a{i}", f"b{i}")),
       "xor": (T, lambda i: AND(f"t{i}", f"a{i}", f"b{i}") + f" ∧ z{i} = a{i} + b{i} − 2 ∗ t{i}")}
rx.machine(d, "M0", ["a", "b", "z"], words,
           [init, load + (None,)] + [(op, A + B + Z + extra, split + [("zbits", ranged(Z + extra))] + [(f"bit{i}", f(i)) for i in BITS], result, None)
                                     for op, (extra, f) in lin.items()])
xor_gates = lambda i: (OR(f"o{i}", f"a{i}", f"b{i}") + " ∧ " + AND(f"t{i}", f"a{i}", f"b{i}") + f" ∧ n{i} = 1 − t{i} ∧ "
                       + AND(f"z{i}", f"o{i}", f"n{i}"))
rx.machine(d, "M1", ["a", "b", "z"], [],
           [init, load + ("load",)]
           + [(op, A + B + Z + extra, split + [("zbits", ranged(Z + extra))] + [(f"bit{i}", f(i)) for i in BITS], result, op)
              for op, (extra, f) in lin.items() if op != "xor"]
           + [("xor", A + B + Z + T + O + NN, split + [("zbits", ranged(Z + T + O + NN))] + [(f"gates{i}", xor_gates(i)) for i in BITS], result, "xor")],
           refines="M0")
print("ok")
