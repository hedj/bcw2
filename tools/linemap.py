"""Map locations in tangled files back to the chapter lines that they came from.

As a filter, it rewrites every location in a tangled file, such as
build/rtl/core/core_rotate.v:9 or File "build/model/x.py", line 3, to the
chapter and line that hold that code:

    verilator --lint-only -Wall build/rtl/bcw_params.sv build/rtl/core/core_rotate.v 2>&1 | \
        python3 tools/linemap.py

It keeps the rest of each line. If it cannot map a location, it leaves the
location unchanged and adds a note.

The tangle of tools/bcw.py writes build/tangle.json, which holds the chapter
line of each line of each tangled file, by the path of the file in build/. A
line that no chapter line holds, such as the header of a file of constants,
maps to nothing.
"""

import functools
import json
import os
import re
import sys
from pathlib import Path

LOCATIONS = [
    re.compile(r'(?P<before>File ")(?P<path>[^"]*build/[^"]+)(?P<middle>", line )(?P<line>\d+)'),
    re.compile(r"(?P<before>)(?P<path>[^\s:\"'()]*build/[^\s:\"'()]+)(?P<middle>:)(?P<line>\d+)"),
]
NOTE = "  (linemap: no source for this location)"


@functools.cache
def load(record):
    """The chapter lines of each tangled file in the record, by path in the folder of the record."""
    return json.loads(Path(record).read_text())["files"]


def lookup(path, line):
    """Return (chapter path, line) for a line of a tangled file, or None.

    The record is the nearest tangle.json in a folder that holds the file.
    """
    path = Path(path).absolute()
    for folder in path.parents:
        record = folder / "tangle.json"
        if record.exists():
            lines = load(str(record)).get(path.relative_to(folder).as_posix(), {}).get("lines", [])
            place = lines[line - 1] if 1 <= line <= len(lines) else None
            return tuple(place) if place else None
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
