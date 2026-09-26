"""The twin language: the forms of Python that a twin can hold, and their translation to z3.

A twin states a rule as functions in Python syntax. The tools never run a twin. translate
reads its syntax tree and translates each form to a z3 bit-vector term, so Python never
asks a z3 value for its truth value or its hash. A form outside the language is a
TwinError at its line. tools/bcw.py reports these errors at the chapter lines of the
twin (doc.twin-forms), and tools/run_checks.py proves each equiv check with the terms.

The language:

- A twin holds only function definitions, without decorators, default values or
  keyword arguments. A body holds assignments to one name each, then one return.
- An integer is a literal, an argument, a local name or a PARAMETER constant, such as
  CORE_THREADS. The operators are + - * and unary -, ** by a constant of 0 or more,
  // and % by a positive constant, << and >> by a constant of 0 or more, and ~ & | ^.
  The functions are min, max and abs, and the other functions of the twin, which
  cannot call themselves. Each argument of a function is an integer.
- A truth value is a comparison (a chain too), and, or, not, True or False.
- "a if c else b" needs a truth value c. Each operator needs its kind of value.

Each integer carries an interval: its least and its greatest value. An input of n bits
starts at 0 up to 2^n - 1. After the walk, translate takes one width: the bits of the
widest interval, and a sign bit. It builds every term at that width. No value can then
overflow, so each two's-complement operation gives the exact integer that Python gives.
"""

import ast
import functools
import operator

import z3

# The widest bit-vector that a translation can use.
LIMIT = 256
COMPARISONS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
               ast.Gt: operator.gt, ast.GtE: operator.ge}
ARITHMETIC = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
BITWISE = {ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor}


class TwinError(Exception):
    """A form outside the twin language, with its line in the twin."""

    def __init__(self, line, message):
        super().__init__(message)
        self.line = line


class Integer:
    """An integer value: its interval, whether it is a constant, and its term at a width."""

    def __init__(self, low, high, constant, build):
        self.low, self.high, self.constant, self.build = low, high, constant, functools.cache(build)

    def bits(self):
        """The bits that hold the interval in two's complement."""
        return max(abs(self.low), abs(self.high)).bit_length() + 1


class Truth:
    """A truth value, with its term at a width."""

    def __init__(self, build):
        self.build = functools.cache(build)


def not_allowed(node):
    return TwinError(node.lineno, f"{ast.unparse(node)!r} is not in the twin language")


def functions(text):
    """The function definitions of a twin, by name, or a TwinError for its first form outside the language."""
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise TwinError(error.lineno, f"the twin is not Python: {error.msg}") from None
    for statement in tree.body:
        if not isinstance(statement, ast.FunctionDef):
            raise not_allowed(statement)
        arguments = statement.args
        for node in (statement.decorator_list + arguments.defaults + arguments.kw_defaults + arguments.posonlyargs
                     + arguments.kwonlyargs + [arguments.vararg, arguments.kwarg] + [statement.returns]
                     + [argument.annotation for argument in arguments.args]):
            if node is not None:
                raise not_allowed(node)
    return {statement.name: statement for statement in tree.body}


def translate(text, function, inputs, constants):
    """(width, outputs) of the function of a twin, with its arguments bound to the input terms.

    inputs maps each argument to a z3 bit-vector, and constants maps each PARAMETER
    constant to its integer. outputs is the dict of terms that the function returns, or
    its one term, at the width.
    """
    defined = functions(text)
    if function not in defined:
        raise TwinError(1, f"the twin defines no function {function}")
    node = defined[function]
    names = [argument.arg for argument in node.args.args]
    if names != list(inputs):
        raise TwinError(node.lineno, f"the function {function} takes {', '.join(names)}, "
                                     f"but the inputs are {', '.join(inputs)}")
    walk = Walk(defined, constants)
    result = walk.call(node, [walk.integer(0, 2 ** term.size() - 1, False,
                                           lambda width, term=term: z3.ZeroExt(width - term.size(), term))
                              for term in inputs.values()], ())
    width = max(value.bits() for value in walk.integers)
    if width > LIMIT:
        raise TwinError(node.lineno, f"the twin needs {width} bits, more than {LIMIT}")
    if isinstance(result, dict):
        return width, {name: value.build(width) for name, value in result.items()}
    return width, result.build(width)


def errors(text, constants):
    """The (line, message) of each form outside the language in a twin, in the order found.

    Each function is translated on its own, with an input of 1 bit for each argument.
    The width of the inputs changes no error but the limit of LIMIT bits, which
    tools/run_checks.py applies with the real widths.
    """
    try:
        defined = functions(text)
    except TwinError as error:
        return [(error.line, str(error))]
    found = {}
    for name, function in defined.items():
        try:
            translate(text, name, {argument.arg: z3.BitVec(argument.arg, 1) for argument in function.args.args},
                      constants)
        except TwinError as error:
            found.setdefault((error.line, str(error)))
    return list(found)


class Walk:
    """The walk of one translation: the functions of the twin, the constants, and each integer that it made."""

    def __init__(self, defined, constants):
        self.defined, self.constants, self.integers = defined, constants, []

    def integer(self, low, high, constant, build):
        value = Integer(low, high, constant, build)
        self.integers.append(value)
        return value

    def literal(self, number):
        return self.integer(number, number, True, lambda width: z3.BitVecVal(number, width))

    def call(self, function, arguments, stack):
        """The value that a function of the twin returns: a dict of integers, or one value."""
        names = dict(zip([argument.arg for argument in function.args.args], arguments))
        stack = stack + (function.name,)
        for statement in function.body[:-1]:
            if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)):
                raise not_allowed(statement)
            names[statement.targets[0].id] = self.value(statement.value, names, stack)
        last = function.body[-1]
        if not isinstance(last, ast.Return) or last.value is None:
            raise TwinError(last.lineno, f"the function {function.name} does not end with a return")
        if isinstance(last.value, ast.Dict):
            result = {}
            for key, node in zip(last.value.keys, last.value.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    raise not_allowed(key if key is not None else node)
                result[key.value] = self.number(node, names, stack)
            return result
        return self.value(last.value, names, stack)

    def number(self, node, names, stack):
        value = self.value(node, names, stack)
        if not isinstance(value, Integer):
            raise TwinError(node.lineno, f"{ast.unparse(node)!r} is a truth value, where the twin language needs "
                                         "an integer")
        return value

    def truth(self, node, names, stack):
        value = self.value(node, names, stack)
        if not isinstance(value, Truth):
            raise TwinError(node.lineno, f"{ast.unparse(node)!r} is an integer, where the twin language needs "
                                         "a truth value")
        return value

    def constant(self, node, names, stack, least, what):
        """The integer of a constant expression of least or more."""
        value = self.number(node, names, stack)
        if not value.constant or value.low < least:
            raise TwinError(node.lineno, f"{what} must be a constant of {least} or more, not {ast.unparse(node)!r}")
        return value.low

    def value(self, node, names, stack):
        """The Integer or Truth of an expression."""
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return Truth(lambda width: z3.BoolVal(node.value))
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return self.literal(node.value)
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            if node.id in self.constants:
                return self.literal(self.constants[node.id])
            raise TwinError(node.lineno, f"{node.id} is not an argument, a local name or a PARAMETER constant")
        if isinstance(node, ast.BinOp):
            return self.binary(node, names, stack)
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                operand = self.truth(node.operand, names, stack)
                return Truth(lambda width: z3.Not(operand.build(width)))
            operand = self.number(node.operand, names, stack)
            if isinstance(node.op, ast.USub):
                return self.integer(-operand.high, -operand.low, operand.constant, lambda width: -operand.build(width))
            if isinstance(node.op, ast.Invert):
                return self.integer(-operand.high - 1, -operand.low - 1, operand.constant,
                                    lambda width: ~operand.build(width))
            return operand
        if isinstance(node, ast.Compare):
            if not all(type(op) in COMPARISONS for op in node.ops):
                raise not_allowed(node)
            values = [self.number(item, names, stack) for item in [node.left] + node.comparators]
            pairs = [(COMPARISONS[type(op)], left, right) for op, left, right in zip(node.ops, values, values[1:])]
            return Truth(lambda width: z3.And([compare(left.build(width), right.build(width))
                                               for compare, left, right in pairs]))
        if isinstance(node, ast.BoolOp):
            values = [self.truth(item, names, stack) for item in node.values]
            join = z3.And if isinstance(node.op, ast.And) else z3.Or
            return Truth(lambda width: join([value.build(width) for value in values]))
        if isinstance(node, ast.IfExp):
            test = self.truth(node.test, names, stack)
            body, other = self.value(node.body, names, stack), self.value(node.orelse, names, stack)
            if type(body) is not type(other):
                raise TwinError(node.lineno, f"{ast.unparse(node)!r} mixes an integer and a truth value")
            if isinstance(body, Truth):
                return Truth(lambda width: z3.If(test.build(width), body.build(width), other.build(width)))
            return self.integer(min(body.low, other.low), max(body.high, other.high), body.constant and other.constant,
                                lambda width: z3.If(test.build(width), body.build(width), other.build(width)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            return self.call_named(node, names, stack)
        raise not_allowed(node)

    def binary(self, node, names, stack):
        left, op = self.number(node.left, names, stack), type(node.op)
        if op in ARITHMETIC:
            right = self.number(node.right, names, stack)
            corners = [ARITHMETIC[op](a, b) for a in (left.low, left.high) for b in (right.low, right.high)]
            return self.integer(min(corners), max(corners), left.constant and right.constant,
                                lambda width: ARITHMETIC[op](left.build(width), right.build(width)))
        if op is ast.Pow:
            power = self.constant(node.right, names, stack, 0, "the exponent of **")
            candidates = [left.low ** power, left.high ** power] + ([0] if left.low < 0 < left.high else [])
            return self.integer(min(candidates), max(candidates), left.constant,
                                lambda width: functools.reduce(operator.mul, [left.build(width)] * power,
                                                               z3.BitVecVal(1, width)))
        if op in (ast.FloorDiv, ast.Mod):
            divisor = self.constant(node.right, names, stack, 1, f"the divisor of {'//' if op is ast.FloorDiv else '%'}")
            # z3 % on bit-vectors is bvsmod, whose result has the sign of the divisor, as in Python.
            modulo = self.integer(0, divisor - 1, left.constant, lambda width: left.build(width) % divisor)
            if op is ast.Mod:
                return modulo
            # a - a % divisor is a multiple of the divisor, so the division is exact.
            multiple = self.integer(left.low - divisor + 1, left.high, left.constant,
                                    lambda width: left.build(width) - modulo.build(width))
            return self.integer(left.low // divisor, left.high // divisor, left.constant,
                                lambda width: multiple.build(width) / divisor)
        if op in (ast.LShift, ast.RShift):
            shift = self.constant(node.right, names, stack, 0, "the shift of << and >>")
            if op is ast.LShift:
                return self.integer(left.low << shift, left.high << shift, left.constant,
                                    lambda width: left.build(width) << shift)
            # z3 >> on bit-vectors is the arithmetic shift, which rounds down, as in Python.
            return self.integer(left.low >> shift, left.high >> shift, left.constant,
                                lambda width: left.build(width) >> shift)
        if op in BITWISE:
            right = self.number(node.right, names, stack)
            bits = max(left.bits(), right.bits())
            if left.low >= 0 and right.low >= 0:
                low, high = 0, (min(left.high, right.high) if op is ast.BitAnd else 2 ** (bits - 1) - 1)
            else:
                low, high = -2 ** (bits - 1), 2 ** (bits - 1) - 1
            return self.integer(low, high, left.constant and right.constant,
                                lambda width: BITWISE[op](left.build(width), right.build(width)))
        raise not_allowed(node)

    def call_named(self, node, names, stack):
        name = node.func.id
        if any(isinstance(argument, ast.Starred) for argument in node.args):
            raise not_allowed(node)
        if name in self.defined:
            if name in stack:
                raise TwinError(node.lineno, f"{name} calls itself, which the twin language does not allow")
            function = self.defined[name]
            if len(node.args) != len(function.args.args):
                raise TwinError(node.lineno, f"{name} takes {len(function.args.args)} arguments, "
                                             f"not {len(node.args)}")
            return self.call(function, [self.number(argument, names, stack) for argument in node.args], stack)
        values = [self.number(argument, names, stack) for argument in node.args]
        if name in ("min", "max") and len(values) >= 2:
            return functools.reduce(lambda a, b: self.choose(a, b, operator.lt if name == "min" else operator.gt), values)
        if name == "abs" and len(values) == 1:
            [value] = values
            negative = self.integer(-value.high, -value.low, value.constant, lambda width: -value.build(width))
            high = max(abs(value.low), abs(value.high))
            low = 0 if value.low <= 0 <= value.high else min(abs(value.low), abs(value.high))
            return self.integer(low, high, value.constant,
                                lambda width: z3.If(value.build(width) < 0, negative.build(width), value.build(width)))
        raise TwinError(node.lineno, f"{name} is not a function of the twin, or min, max or abs")

    def choose(self, a, b, better):
        """a if a is better than b, else b: min or max of two integers."""
        low = min(a.low, b.low) if better is operator.lt else max(a.low, b.low)
        high = min(a.high, b.high) if better is operator.lt else max(a.high, b.high)
        return self.integer(low, high, a.constant and b.constant,
                            lambda width: z3.If(better(a.build(width), b.build(width)), a.build(width), b.build(width)))
