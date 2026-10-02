"""Translates a yosys netlist into Event-B expressions, with chosen input ports split into bits.

Each split input port p of width w has parameters p0 … p(w-1) in 0 ‥ 1, with p = Σ pi ∗ 2^i.
Every signal is an expression of the inputs, so the translation is functional. A slice of an
internal signal, a slice of an input that is not split, or a cell outside RULES is an error.
"""
import json


def ite(c, x, y):
    return f"({{TRUE ↦ {x}, FALSE ↦ {y}}})(bool({c}))"


def total(terms):
    """Σ term_i ∗ 2^i over (i, term) pairs, without the zero terms."""
    parts = [str(int(t) * 2 ** i) if t.isdigit() else t if i == 0 else f"{t} ∗ {2 ** i}" for i, t in terms if t != "0"]
    return " + ".join(parts) if parts else "0"


GATES = {
    "and": lambda z, a, b, t: f"{z} ≤ {a} ∧ {z} ≤ {b} ∧ {a} + {b} ≤ 1 + {z}",
    "or": lambda z, a, b, t: f"{a} ≤ {z} ∧ {b} ≤ {z} ∧ {z} ≤ {a} + {b}",
    "xor": lambda z, a, b, t: f"{GATES['and'](t, a, b, None)} ∧ {z} = {a} + {b} − 2 ∗ {t}",
}


def gate_guard(kind, a, b, z, t):
    """The guard that fixes the result bits z (and, for xor, the carry bits t) of a bitwise gate."""
    names = z + (t if kind == "xor" else [])
    ranges = " ∧ ".join(f"{n} ∈ 0 ‥ 1" for n in names)
    return ranges + " ∧ " + " ∧ ".join(GATES[kind](zi, ai, bi, ti) for zi, ai, bi, ti in zip(z, a, b, t))


class Netlist:
    def __init__(self, path, top, split):
        module = json.load(open(path))["modules"][top]
        self.ports = {n: p for n, p in module["ports"].items()}
        self.split = set(split)
        self.where = {}
        for name, port in self.ports.items():
            for i, b in enumerate(port["bits"]):
                self.where[b] = (name, i)
        # A $scopeinfo cell records a flattened instance for debugging; it has no logic.
        self.cells = [c for c in module["cells"].values() if c["type"] != "$scopeinfo"]
        self.expression, self.side, self.params, self.guards = {}, [], [], []

    # --- values of bit lists ---
    def bit(self, b):
        """The expression of one bit, 0 or 1, if it is a constant or a bit of a split input."""
        if b in ("0", "1"):
            return b
        if b in self.where and self.where[b][0] in self.split and self.ports[self.where[b][0]]["direction"] == "input":
            name, i = self.where[b]
            return f"{name}{i}"
        raise ValueError(f"the bit {b} is not a bit of a split input")

    def bits(self, bits):
        return [self.bit(b) for b in bits]

    def value(self, bits):
        """The integer of a bit list: runs of constants, of input bits, and whole internal signals."""
        terms, i = [], 0
        while i < len(bits):
            for j in range(len(bits), i, -1):
                run = tuple(bits[i:j])
                if run in self.expression:
                    terms.append((i, f"({self.expression[run]})"))
                    break
                port = [n for n, p in self.ports.items() if tuple(p["bits"]) == run and p["direction"] == "input"]
                if port:
                    terms.append((i, port[0]))
                    break
            else:
                terms.append((i, self.bit(bits[i])))
                j = i + 1
            i = j
        return total(terms)

    def signed(self, bits):
        return f"{self.value(bits)} − {2 ** len(bits)} ∗ {self.bit(bits[-1])}"

    # --- cells ---
    def cell(self, c):
        t, x, p = c["type"], c["connections"], {k: int(v, 2) for k, v in c["parameters"].items()}
        signed = p.get("A_SIGNED", 0) and p.get("B_SIGNED", p.get("A_SIGNED", 0))
        v = lambda port: (self.signed(x[port]) if signed else self.value(x[port]))
        if t in ("$add", "$sub"):
            w, a, b = p["Y_WIDTH"], v("A"), v("B")
            if t == "$add":
                return ite(f"{a} + {b} < {2 ** w}", f"{a} + {b}", f"{a} + {b} − {2 ** w}")
            return ite(f"{a} ≥ {b}", f"{a} − {b}", f"{a} − {b} + {2 ** w}")
        if t == "$neg":
            a = v("A")
            return ite(f"{a} = 0", "0", f"{2 ** p['Y_WIDTH']} − {a}")
        compare = {"$eq": "=", "$ne": "≠", "$lt": "<", "$le": "≤", "$gt": ">", "$ge": "≥"}
        if t in compare:
            return ite(f"{v('A')} {compare[t]} {v('B')}", "1", "0")
        if t == "$logic_not":
            return ite(f"{self.value(x['A'])} = 0", "1", "0")
        if t in ("$and", "$or", "$xor"):
            out = [n for n, q in self.ports.items() if tuple(q["bits"]) == tuple(x["Y"])]
            prefix = "r" if out else f"w{len(self.guards)}_"
            w = len(x["Y"])
            z, carry = [f"{prefix}{i}" for i in range(w)], [f"t{i}" if out else f"{prefix}t{i}" for i in range(w)]
            self.guards.append((f"{t[1:]}_bits", gate_guard(t[1:], self.bits(x["A"]), self.bits(x["B"]), z, carry)))
            self.params += z + (carry if t == "$xor" else [])
            return total(enumerate(z))
        if t == "$mux":
            return ite(f"{self.value(x['S'])} = 1", self.value(x["B"]), self.value(x["A"]))
        if t == "$pmux":
            w, n = p["WIDTH"], p["S_WIDTH"]
            selects = [self.value([s]) for s in x["S"]]
            self.side.append(" + ".join(selects) + " ≤ 1")
            out = self.value(x["A"])
            for j in reversed(range(n)):
                out = ite(f"{selects[j]} = 1", self.value(x["B"][j * w:(j + 1) * w]), out)
            return out
        if t in ("$shl", "$shr", "$sshr"):
            a, w, k = self.bits(x["A"]), p["Y_WIDTH"], self.value(x["B"])
            fill = a[-1] if t == "$sshr" else "0"
            def shifted(s):
                if t == "$shl":
                    return total((i, a[i - s] if i >= s else "0") for i in range(w))
                return total((i, a[i + s] if i + s < len(a) else fill) for i in range(w))
            out = shifted(2 ** len(x["B"]) - 1)
            for s in reversed(range(2 ** len(x["B"]) - 1)):
                out = ite(f"{k} = {s}", shifted(s), out)
            return out
        raise ValueError(f"no rule for {t}")

    def translate(self):
        pending = self.cells
        while pending:
            done = []
            for c in pending:
                try:
                    self.expression[tuple(c["connections"]["Y"])] = self.cell(c)
                    done.append(c)
                except (KeyError, ValueError):
                    pass
            if not done:
                raise ValueError("cells that no rule can translate: " + ", ".join(c["type"] for c in pending))
            pending = [c for c in pending if c not in done]
        return {n: self.value(p["bits"]) for n, p in self.ports.items() if p["direction"] == "output"}
