"""The option --update-golden, with which the reference tests of the weave rewrite their reference outputs."""


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true",
                     help="rewrite the reference outputs in tools/tests/golden from the current weave")
