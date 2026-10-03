"""Writes a synchronous Verilog module from an Event-B machine in a small implementable subset.

Usage: eventb2v.py MACHINE.bum TOP > TOP.v

The subset:
  * each variable has an invariant "x ∈ 0 ‥ 2^w − 1" (or any 0 ‥ n); it becomes a register of w bits;
  * INITIALISATION gives each variable "x :∈ <its range>": the register powers up in any value;
  * an event "reset", without parameters, fires when the input rst_n is 0;
  * one other event, the step, fires when rst_n is 1; each of its parameters has a guard "p ∈ 0 ‥ n"
    and becomes an input port; it has no other guard;
  * actions are "x ≔ e", where e is built from integer literals, variables, parameters, +, −, ∗ by a
    literal, and the choice ({TRUE ↦ e1, FALSE ↦ e2})(bool(c)); c is built from =, ≠, <, ≤, >, ≥,
    ∧, ∨ and ¬.
A next value is computed modulo 2^w, w the width of its register: exact for +, −, ∗ and choice,
since the machine's invariants prove that the value lies in the register's range. The operands of a
comparison are computed unsigned and wide enough for their whole interval, so that the comparison
sees the integers themselves; an operand that may be negative is outside the subset. Each
subexpression is a wire of its own width, so that yosys makes cells of exactly those widths.
Anything outside the subset stops the generator with a message that names it.
"""
import re
import sys
import xml.etree.ElementTree as ET

NS = "org.eventb.core."
RANGE = re.compile(r"^\s*(\w+)\s*∈\s*(\d+)\s*‥\s*(\d+)\s*$")


def attr(element, name):
    return element.get(NS + name, "")


class Parser:
    """Recursive descent over the subset into a tree: ("lit", n), ("var", x), ("+"|"−"|"∗", a, b),
    ("choice", condition, a, b); conditions are ("rel", op, a, b), ("and"|"or", c, d), ("not", c)."""
    TOKEN = re.compile(r"\s*(\d+|[A-Za-z_]\w*|↦|‥|≔|[{}(),]|[=≠<≤>≥∧∨¬+−∗])")

    def __init__(self, text, names):
        self.tokens, self.names, self.i, position = [], names, 0, 0
        while position < len(text.rstrip()):
            match = self.TOKEN.match(text, position)
            if not match:
                raise SystemExit(f"outside the subset: {text[position:position + 20]!r} in {text!r}")
            self.tokens.append(match.group(1))
            position = match.end()

    def peek(self, k=0):
        return self.tokens[self.i + k] if self.i + k < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if expected is not None and token != expected:
            raise SystemExit(f"expected {expected!r}, found {token!r} in {' '.join(self.tokens)}")
        self.i += 1
        return token

    def whole(self):
        tree = self.expression()
        if self.peek() is not None:
            raise SystemExit(f"outside the subset after {' '.join(self.tokens[:self.i])}: {self.peek()!r}")
        return tree

    def expression(self):
        tree = self.term()
        while self.peek() in ("+", "−"):
            op = self.take()
            tree = (op, tree, self.term())
        return tree

    def term(self):
        tree = self.factor()
        while self.peek() == "∗":
            self.take()
            right = self.factor()
            if tree[0] != "lit" and right[0] != "lit":
                raise SystemExit("outside the subset: a product of two variables")
            tree = ("∗", tree, right)
        return tree

    def factor(self):
        token = self.peek()
        if token is not None and token.isdigit():
            self.take()
            return ("lit", int(token))
        if token == "(" and self.peek(1) == "{":
            for t in ("(", "{", "TRUE", "↦"):
                self.take(t)
            yes = self.expression()
            for t in (",", "FALSE", "↦"):
                self.take(t)
            no = self.expression()
            for t in ("}", ")", "(", "bool", "("):
                self.take(t)
            condition = self.disjunction()
            self.take(")")
            self.take(")")
            return ("choice", condition, yes, no)
        if token == "(":
            self.take()
            tree = self.expression()
            self.take(")")
            return tree
        if token in self.names:
            self.take()
            return ("var", token)
        raise SystemExit(f"outside the subset: {token!r}")

    def disjunction(self):
        tree = self.conjunction()
        while self.peek() == "∨":
            self.take()
            tree = ("or", tree, self.conjunction())
        return tree

    def conjunction(self):
        tree = self.negation()
        while self.peek() == "∧":
            self.take()
            tree = ("and", tree, self.negation())
        return tree

    def negation(self):
        if self.peek() == "¬":
            self.take()
            return ("not", self.negation())
        start = self.i
        if self.peek() == "(":   # a bracketed predicate, else the bracketed left side of a comparison
            self.take()
            try:
                tree = self.disjunction()
                if self.peek() == ")":
                    self.take()
                    return tree
            except SystemExit:
                pass
            self.i = start
        left = self.expression()
        op = self.take()
        if op not in ("=", "≠", "<", "≤", ">", "≥"):
            raise SystemExit(f"outside the subset: comparison {op!r}")
        return ("rel", op, left, self.expression())


def bounds(tree, ranges):
    """The interval of an expression's integer value."""
    kind = tree[0]
    if kind == "lit":
        return tree[1], tree[1]
    if kind == "var":
        return ranges[tree[1]]
    if kind == "choice":
        (alow, ahigh), (blow, bhigh) = bounds(tree[2], ranges), bounds(tree[3], ranges)
        return min(alow, blow), max(ahigh, bhigh)
    (alow, ahigh), (blow, bhigh) = bounds(tree[1], ranges), bounds(tree[2], ranges)
    if kind == "+":
        return alow + blow, ahigh + bhigh
    if kind == "−":
        return alow - bhigh, ahigh - blow
    products = [alow * blow, alow * bhigh, ahigh * blow, ahigh * bhigh]
    return min(products), max(products)


class Emitter:
    """Each subexpression becomes a wire of a stated width. A value is computed modulo 2^width,
    which is exact for +, −, ∗ and choice once the result is known to lie in 0 ‥ 2^width − 1; the
    operands of a comparison are computed wide enough to hold their whole interval, so that the
    comparison sees the integers themselves."""

    def __init__(self, ranges):
        self.ranges, self.lines, self.count = ranges, [], 0

    def wire(self, width, code):
        self.count += 1
        name = f"t{self.count}"
        self.lines.append(f"    wire [{width - 1}:0] {name} = {code};")
        return name

    def value(self, tree, width):
        kind = tree[0]
        if kind == "lit":
            return f"{width}'d{tree[1] % 2 ** width}"
        if kind == "var":
            return tree[1]
        if kind == "choice":
            return self.wire(width, f"{self.condition(tree[1])} ? {self.value(tree[2], width)} : {self.value(tree[3], width)}")
        op = {"+": "+", "−": "-", "∗": "*"}[kind]
        return self.wire(width, f"{self.value(tree[1], width)} {op} {self.value(tree[2], width)}")

    def condition(self, tree):
        kind = tree[0]
        if kind == "not":
            return self.wire(1, f"!{self.condition(tree[1])}")
        if kind in ("and", "or"):
            op = "&&" if kind == "and" else "||"
            return self.wire(1, f"{self.condition(tree[1])} {op} {self.condition(tree[2])}")
        _, op, left, right = tree
        (llow, lhigh), (rlow, rhigh) = bounds(left, self.ranges), bounds(right, self.ranges)
        if min(llow, rlow) < 0:
            raise SystemExit(f"outside the subset: a comparison operand may be negative ({llow} ‥ {lhigh}, {rlow} ‥ {rhigh})")
        width = bits(max(lhigh, rhigh))
        relation = {"=": "==", "≠": "!=", "<": "<", "≤": "<=", ">": ">", "≥": ">="}[op]
        return self.wire(1, f"{self.value(left, width)} {relation} {self.value(right, width)}")


def bits(n):
    return max(1, n.bit_length())


def generate(path, top):
    machine = ET.parse(path).getroot()
    variables = [attr(v, "identifier") for v in machine.findall(NS + "variable")]
    ranges = {}
    for invariant in machine.findall(NS + "invariant"):
        match = RANGE.match(attr(invariant, "predicate"))
        if match and match.group(1) in variables:
            ranges[match.group(1)] = (int(match.group(2)), int(match.group(3)))
    for v in variables:
        if v not in ranges or ranges[v][0] != 0:
            raise SystemExit(f"the variable {v} has no invariant {v} ∈ 0 ‥ n")
    events = {attr(e, "label"): e for e in machine.findall(NS + "event")}
    steps = [label for label in events if label not in ("INITIALISATION", "reset")]
    if set(events) - set(steps) != {"INITIALISATION", "reset"} or len(steps) != 1:
        raise SystemExit(f"the events must be INITIALISATION, reset and one step event, not {sorted(events)}")
    step = events[steps[0]]
    for action in events["INITIALISATION"].findall(NS + "action"):
        text = attr(action, "assignment")
        match = re.match(r"^\s*(\w+)\s*:∈\s*(\d+)\s*‥\s*(\d+)\s*$", text)
        if not match or (int(match.group(2)), int(match.group(3))) != ranges.get(match.group(1)):
            raise SystemExit(f"INITIALISATION: {text!r} is not the power-up 'x :∈ <its range>'")
    inputs = {}
    for guard in step.findall(NS + "guard"):
        match = RANGE.match(attr(guard, "predicate"))
        if not match:
            raise SystemExit(f"{steps[0]}: the guard {attr(guard, 'predicate')!r} is not 'p ∈ 0 ‥ n'")
        inputs[match.group(1)] = (int(match.group(2)), int(match.group(3)))
    parameters = [attr(p, "identifier") for p in step.findall(NS + "parameter")]
    if set(parameters) != set(inputs):
        raise SystemExit(f"{steps[0]}: each parameter needs one guard 'p ∈ 0 ‥ n'")
    if events["reset"].findall(NS + "parameter") or events["reset"].findall(NS + "guard"):
        raise SystemExit("reset has parameters or guards")
    scope = {**ranges, **inputs}

    def actions(event, names):
        parsed = {}
        for action in event.findall(NS + "action"):
            match = re.match(r"^\s*(\w+)\s*≔\s*(.*)$", attr(action, "assignment"), re.S)
            if not match or match.group(1) not in variables:
                raise SystemExit(f"{attr(event, 'label')}: {attr(action, 'assignment')!r} is not 'x ≔ e'")
            parsed[match.group(1)] = match.group(2)
        missing = [v for v in variables if v not in parsed]
        if missing:
            raise SystemExit(f"{attr(event, 'label')} does not assign {missing}: every register needs its next value")
        return parsed

    reset, run = actions(events["reset"], ranges), actions(step, scope)
    ports = ["input wire clk, rst_n"] + [f"input wire [{bits(hi) - 1}:0] {p}" for p, (_, hi) in inputs.items()]
    ports += [f"output wire [{bits(ranges[v][1]) - 1}:0] {v}_q" for v in variables]
    lines = [f"// Generated by eventb2v.py from {path.split('/')[-1]}: do not edit.",
             f"module {top} (" + ",\n    ".join(ports) + ");"]
    lines += [f"    logic [{bits(ranges[v][1]) - 1}:0] {v};" for v in variables]
    lines += [f"    assign {v}_q = {v};" for v in variables]
    emitter = Emitter(scope)
    nexts, resets = {}, {}
    for v in variables:
        width = bits(ranges[v][1])
        nexts[v] = emitter.value(Parser(run[v], scope).whole(), width)
        resets[v] = emitter.value(Parser(reset[v], ranges).whole(), width)
    lines += emitter.lines
    lines.append("    always_ff @(posedge clk)")
    lines.append("        if (!rst_n) begin")
    lines += [f"            {v} <= {resets[v]};" for v in variables]
    lines.append("        end else begin")
    lines += [f"            {v} <= {nexts[v]};" for v in variables]
    lines.append("        end")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(generate(sys.argv[1], sys.argv[2]))
