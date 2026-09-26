"""Tests of tools/twin.py, which translates a twin in the twin language to z3 bit-vectors.

The differential test holds the core property of the language: for each form, the term
equals the value that Python computes from the same text, on every input. Python may run
a twin here, because its arguments are integers.
"""

import itertools

import pytest
import z3

import twin

# Each expression is the value of the output r of a twin with the arguments x and y.
EXPRESSIONS = [
    "x + y", "x - y", "x * y", "-x", "x ** 3", "(x - y) ** 2",
    "x // 3", "x % 3", "(x - y) // 3", "(x - y) % 3", "(x - 20) // 7",
    "x << 2", "(x - y) >> 1", "x >> 3", "~x", "~(x - y) ^ y",
    "x & y", "x | y", "x ^ y", "(x - y) & 5", "((x - y) * (x - y)) & 15", "(x - y) | (y - x)",
    "min(x, y)", "max(x - y, 2)", "abs(x - y)", "min(x, y, 3)",
    "0 if x == y else 1", "x if x != 3 else 99", "x if x < y <= 9 else y",
    "1 if (x > 2 and y < 5) or not x == y else 2", "x if True else y", "y if x >= y > 3 else x - 1",
    "x % LIMIT", "(x * y) // (LIMIT + 1)",
    # Each value below is larger than every other value of its twin, so only a sound
    # interval gives a width that holds it.
    "((x - y) ** 2 - 200) * 1000", "(y - x * 16) * (y - x * 16)", "(x - 15) // 9",
    "((x - 16) & (y - 16)) * ((x - 16) & (y - 16))", "((~(x - 16)) & y) * ((~(x - 16)) & y) * 100",
    "(x if x > 5 else x - 30) * (x if x > 5 else x - 30)", "min(x - 30, y) * min(x - 30, y)",
    "127 - ((x - 16) & (y - 16))",
]
CONSTANTS = {"LIMIT": 5}


def source(expression):
    return f"def f(x, y):\n    return {{'r': {expression}}}\n"


def value(term, x, y, inputs):
    """The integer that term gives for the inputs x and y."""
    return z3.simplify(z3.substitute(term, (inputs["x"], z3.BitVecVal(x, 4)),
                                     (inputs["y"], z3.BitVecVal(y, 4)))).as_signed_long()


@pytest.mark.parametrize("expression", EXPRESSIONS)
def test_each_form_equals_python_on_every_input(expression):
    inputs = {"x": z3.BitVec("x", 4), "y": z3.BitVec("y", 4)}
    _, outputs = twin.translate(source(expression), "f", inputs, CONSTANTS)
    namespace = dict(CONSTANTS)
    exec(source(expression), namespace)
    for x, y in itertools.product(range(16), repeat=2):
        assert value(outputs["r"], x, y, inputs) == namespace["f"](x, y)["r"], (x, y)


def test_helpers_and_local_names_equal_python():
    text = ("def double(a):\n    return a + a\n\n\n"
            "def f(x, y):\n    total = double(x) - y\n    total = total * total\n    return {'r': total, 's': double(y)}\n")
    inputs = {"x": z3.BitVec("x", 4), "y": z3.BitVec("y", 4)}
    _, outputs = twin.translate(text, "f", inputs, {})
    namespace = {}
    exec(text, namespace)
    for x, y in itertools.product(range(16), repeat=2):
        assert {name: value(term, x, y, inputs) for name, term in outputs.items()} == namespace["f"](x, y)


def test_the_width_holds_the_widest_value_and_a_sign_bit():
    inputs = {"x": z3.BitVec("x", 8), "y": z3.BitVec("y", 8)}
    width, _ = twin.translate(source("x * y"), "f", inputs, {})
    assert width == (255 * 255).bit_length() + 1


def test_a_twin_wider_than_the_limit_is_an_error():
    inputs = {"x": z3.BitVec("x", 64), "y": z3.BitVec("y", 64)}
    with pytest.raises(twin.TwinError) as error:
        twin.translate(source("x ** 5"), "f", inputs, {})
    assert (error.value.line, str(error.value)) == (1, f"the twin needs {((2 ** 64 - 1) ** 5).bit_length() + 1} bits, "
                                                       "more than 256")


@pytest.mark.parametrize("text, line, message", [
    ("def g(x):\n    return {'r': x}\n", 1, "the twin defines no function f"),
    ("def f(x, z):\n    return {'r': x}\n", 1, "the function f takes x, z, but the inputs are x, y"),
    ("def f(x, y):\n    return {'r': x ==}\n", 2, "the twin is not Python: invalid syntax"),
])
def test_errors_name_their_line(text, line, message):
    inputs = {"x": z3.BitVec("x", 4), "y": z3.BitVec("y", 4)}
    with pytest.raises(twin.TwinError) as error:
        twin.translate(text, "f", inputs, {})
    assert (error.value.line, str(error.value)) == (line, message)
