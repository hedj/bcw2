import sys
import rodin_xml as rx
root = sys.argv[1]
W, TOP = "4294967296", "4294967295"

# 1. A wrapping add, then a split of the sum into its high bits and its low two bits.
for name, keep in (("AddSplit", True), ("AddWitness", False)):
    d = rx.project(root, name)
    rx.machine(d, "M0", ["a", "b", "s_hi", "s_lo"],
               [("regs", f"a ∈ 0 ‥ {TOP} ∧ b ∈ 0 ‥ {TOP}", False), ("sum", "s_hi ∈ 0 ‥ 1073741823 ∧ s_lo ∈ 0 ‥ 3", False)],
               [("INITIALISATION", [], [], [("act1", "a, b, s_hi, s_lo ≔ 0, 0, 0, 0")], None),
                ("add", ["c", "hi", "lo"], [("grd1", f"c ∈ 0 ‥ 1 ∧ hi ∈ 0 ‥ 1073741823 ∧ lo ∈ 0 ‥ 3 ∧ a + b = c ∗ {W} + hi ∗ 4 + lo")],
                 [("act1", "s_hi, s_lo ≔ hi, lo")], None),
                ("check", ["bad"], [("grd1", "bad = bool(s_lo ≠ 0)")], [], None)])
    split = "hi ∈ 0 ‥ 1073741823 ∧ lo ∈ 0 ‥ 3 ∧ r = hi ∗ 4 + lo"
    add = (("add", ["c", "r", "hi", "lo"], [("grd1", f"c ∈ 0 ‥ 1 ∧ r ∈ 0 ‥ {TOP} ∧ a + b = c ∗ {W} + r"), ("split", split)],
            [("act1", "s ≔ r")], "add") if keep else
           ("add", ["c", "r"], [("grd1", f"c ∈ 0 ‥ 1 ∧ r ∈ 0 ‥ {TOP} ∧ a + b = c ∗ {W} + r")],
            [("act1", "s ≔ r")], "add", [("hi", "hi ∈ 0 ‥ 1073741823 ∧ r = hi ∗ 4 + lo"), ("lo", "lo ∈ 0 ‥ 3 ∧ r = hi ∗ 4 + lo")]))
    rx.machine(d, "M1", ["a", "b", "s"],
               [("word", f"s ∈ 0 ‥ {TOP}", False), ("glue", "s = s_hi ∗ 4 + s_lo", False)],
               [("INITIALISATION", [], [], [("act1", "a, b, s ≔ 0, 0, 0")], None), add,
                ("check", ["bad", "h", "l"], [("split", "h ∈ 0 ‥ 1073741823 ∧ l ∈ 0 ‥ 3 ∧ s = h ∗ 4 + l"),
                                                ("grd1", "bad = bool(l ≠ 0)")], [], "check")], refines="M0")

# 2. An R-type word: funct7 rs2 rs1 funct3 rd opcode.
FIELDS = [("f7", 7, 25), ("rs2", 5, 20), ("rs1", 5, 15), ("f3", 3, 12), ("rd", 5, 7), ("op", 7, 0)]
CAP = {f: f.upper() for f, _, _ in FIELDS}

d = rx.project(root, "DecodeInt")
ranges = " ∧ ".join(f"{f} ∈ 0 ‥ {2 ** n - 1}" for f, n, _ in FIELDS)
rx.machine(d, "M0", [f for f, _, _ in FIELDS], [("fields", ranges, False)],
           [("INITIALISATION", [], [], [("act1", ", ".join(f for f, _, _ in FIELDS) + " ≔ " + ", ".join("0" for _ in FIELDS))], None),
            ("decode", list(CAP.values()), [("grd1", " ∧ ".join(f"{CAP[f]} = {f}" for f, _, _ in FIELDS))], [], None),
            ("set_rd", ["v"], [("grd1", "v ∈ 0 ‥ 31")], [("act1", "rd ≔ v")], None)])
pack = lambda names: " + ".join(f"{names[f]} ∗ {2 ** lo}" if lo else names[f] for f, _, lo in FIELDS)
rx.machine(d, "M1", ["w"],
           [("word", f"w ∈ 0 ‥ {TOP}", False), ("glue", "w = " + pack({f: f for f, _, _ in FIELDS}), False)],
           [("INITIALISATION", [], [], [("act1", "w ≔ 0")], None),
            ("decode", list(CAP.values()), [("split", " ∧ ".join(f"{CAP[f]} ∈ 0 ‥ {2 ** n - 1}" for f, n, _ in FIELDS)
                                               + " ∧ w = " + pack(CAP))], [], "decode"),
            ("set_rd", ["v", "h", "f", "l"], [("grd1", "v ∈ 0 ‥ 31"),
                                             ("split", "h ∈ 0 ‥ 1048575 ∧ f ∈ 0 ‥ 31 ∧ l ∈ 0 ‥ 127 ∧ w = h ∗ 4096 + f ∗ 128 + l")],
             [("act1", "w ≔ h ∗ 4096 + v ∗ 128 + l")], "set_rd")], refines="M0")

d = rx.project(root, "DecodeBits")
rx.machine(d, "M0", [f for f, _, _ in FIELDS], [("fields", " ∧ ".join(f"{f} ∈ 0 ‥ {n - 1} → 0 ‥ 1" for f, n, _ in FIELDS), False)],
           [("INITIALISATION", [], [], [("act1", ", ".join(f for f, _, _ in FIELDS) + " ≔ "
                                         + ", ".join(f"(0 ‥ {n - 1}) × {{0}}" for _, n, _ in FIELDS))], None),
            ("decode", list(CAP.values()), [("grd1", " ∧ ".join(f"{CAP[f]} = {f}" for f, _, _ in FIELDS))], [], None),
            ("set_rd", ["v"], [("grd1", "v ∈ 0 ‥ 4 → 0 ‥ 1")], [("act1", "rd ≔ v")], None)])
shift = lambda lo: f"i − {lo}" if lo else "i"
glue = " ∪ ".join(f"(λi·i ∈ {lo} ‥ {lo + n - 1} ∣ {f}({shift(lo)}))" for f, n, lo in FIELDS)
rx.machine(d, "M1", ["w"], [("word", "w ∈ 0 ‥ 31 → 0 ‥ 1", False), ("glue", "w = " + glue, False)],
           [("INITIALISATION", [], [], [("act1", "w ≔ (0 ‥ 31) × {0}")], None),
            ("decode", list(CAP.values()), [("grd1", " ∧ ".join(f"{CAP[f]} = (λi·i ∈ 0 ‥ {n - 1} ∣ w(i + {lo}))" for f, n, lo in FIELDS))], [], "decode"),
            ("set_rd", ["v"], [("grd1", "v ∈ 0 ‥ 4 → 0 ‥ 1")], [("act1", f"w ≔ w {rx.OV} (λi·i ∈ 7 ‥ 11 ∣ v(i − 7))")], "set_rd")],
           refines="M0")
print("ok")
