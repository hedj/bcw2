"""Map locations in tangled files back to the chapter lines that they came from.

As a filter, it rewrites every location in a tangled file, such as
build/rtl/core/core_rotate.v:9 or File "build/model/x.py", line 3, to the
chapter and line that hold that code:

    verilator --lint-only -Wall build/rtl/bcw_params.sv build/rtl/core/core_rotate.v 2>&1 | \
        python3 tools/linemap.py

It keeps the rest of each line. If it cannot map a location, it leaves the
location unchanged and adds a note.

The tangle of tools/bcw.py writes a marker comment before each block, such as
// bcw: book/core/core.rst:20, which names the chapter line of the block's
first line of code. A tangled line k lines after a marker maps to the chapter
line k - 1 lines after the named line. A marker line maps to nothing.
"""

import os
import re
import sys
from pathlib import Path

MARKER = re.compile(r"^\s*(?://|#) bcw: (?P<source>\S+):(?P<line>\d+)\s*$")
LOCATIONS = [
    re.compile(r'(?P<before>File ")(?P<path>[^"]*build/[^"]+)(?P<middle>", line )(?P<line>\d+)'),
    re.compile(r"(?P<before>)(?P<path>[^\s:\"'()]*build/[^\s:\"'()]+)(?P<middle>:)(?P<line>\d+)"),
]
NOTE = "  (linemap: no source for this location)"


def lookup(path, line):
    """Return (chapter path, line) for a line of a tangled file, or None."""
    try:
        tangled = Path(path).read_text().splitlines()
    except OSError:
        return None
    if not 1 <= line <= len(tangled):
        return None
    for number in range(line, 0, -1):
        match = MARKER.match(tangled[number - 1])
        if match:
            if number == line:
                return None
            return match["source"], int(match["line"]) + line - number - 1
    return None


def rewrite(text):
    """Rewrite every tangled-file location in one line of tool output."""
    unmapped = False

    def replace(match):
        nonlocal unmapped
        path = match.group("path")
        if os.path.isabs(path):
            path = os.path.relpath(path)
        result = lookup(path, int(match.group("line")))
        if result is None:
            unmapped = True
            return match.group(0)
        source, line = result
        return f"{match.group('before')}{source}{match.group('middle')}{line}"

    for pattern in LOCATIONS:
        text = pattern.sub(replace, text)
    return text + NOTE if unmapped else text


def main():
    for line in sys.stdin:
        print(rewrite(line.rstrip("\n")))


if __name__ == "__main__":
    main()
