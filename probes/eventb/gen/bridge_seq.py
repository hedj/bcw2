"""Extends the functional translation to a netlist with registers.

Each named wire that a $dff drives is a state variable. The translation gives, for each state
variable, its next value as an expression of the state variables and the inputs, so that one clock
edge is one Event-B event whose actions assign every register at once.
"""
import json
from bridge2 import Netlist, ite


class Sequential(Netlist):
    def __init__(self, path, top, split):
        super().__init__(path, top, split)
        module = json.load(open(path))["modules"][top]
        dffs = [c for c in self.cells if c["type"] == "$dff"]
        self.cells = [c for c in self.cells if c["type"] != "$dff"]
        d_of = {q: d for c in dffs for q, d in zip(c["connections"]["Q"], c["connections"]["D"])}
        self.state = {}   # name: (Q bits, D bits)
        # A flattened instance names the same bits again (rotate.turn for rot): keep the top-level name.
        for name, net in sorted(module["netnames"].items(), key=lambda n: ("." in n[0], n[0])):
            if net["hide_name"] or name in self.ports or not all(b in d_of for b in net["bits"]):
                continue
            if tuple(net["bits"]) in self.expression:
                continue
            self.state[name] = (net["bits"], [d_of[b] for b in net["bits"]])
            self.expression[tuple(net["bits"])] = name
        covered = {b for q, _ in self.state.values() for b in q}
        if covered != set(d_of):
            raise ValueError("a register bit that no named wire holds whole")

    def cell(self, c):
        t, x = c["type"], c["connections"]
        if t == "$not" and len(x["Y"]) == 1:
            return ite(f"{self.value(x['A'])} = 0", "1", "0")
        if t in ("$reduce_or", "$reduce_bool"):
            return ite(" + ".join(f"({self.value([b])})" for b in x["A"]) + " ≥ 1", "1", "0")
        if t == "$reduce_and":
            return ite(" + ".join(f"({self.value([b])})" for b in x["A"]) + f" = {len(x['A'])}", "1", "0")
        return super().cell(c)

    def next_state(self):
        """{state variable: the expression of its value after the clock edge}."""
        self.translate()
        return {name: self.value(d) for name, (_, d) in self.state.items()}

    def widths(self):
        return {name: len(q) for name, (q, _) in self.state.items()}
