"""The complexity metrics of the system, counted with radon.

The code of the system is each Python file under tools/, without tools/tests/. The
metrics are:

- lines: the lines of code of each file, without blank lines, comments and
  docstrings, summed;
- mccabe: the McCabe complexity (the number of independent paths) of each function,
  method and nested function, summed;
- halstead_volume and halstead_effort: the Halstead volume and effort of each file,
  summed. radon counts only the operators of arithmetic, comparisons and logic,
  so a call or an assignment adds nothing to them, but it adds to lines.

Run it from the root of the repository: ./dev python3 tools/metrics.py
"""

import json
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import h_visit
from radon.raw import analyze
from radon.visitors import Function


def mccabe(blocks):
    """The McCabe complexity of each function in blocks and of each function nested in it, summed.

    radon lists each method as a function too, so a class adds nothing of its own.
    """
    return sum(block.complexity + mccabe(block.closures) for block in blocks if isinstance(block, Function))


def main():
    metrics = {"lines": 0, "mccabe": 0, "halstead_volume": 0, "halstead_effort": 0}
    for path in sorted(Path("tools").rglob("*.py")):
        if path.relative_to("tools").parts[0] == "tests":
            continue
        text = path.read_text()
        halstead = h_visit(text).total
        metrics["lines"] += analyze(text).sloc
        metrics["mccabe"] += mccabe(cc_visit(text))
        metrics["halstead_volume"] += halstead.volume
        metrics["halstead_effort"] += halstead.effort
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
