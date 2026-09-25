"""Map locations in tangled files back to the Markdown that they came from.

As a filter, it rewrites every location in a tangled file, such as
build/rtl/core/core_rotate.v:9 or File "build/model/x.py", line 3, to the
chapter and line that hold that code:

    verilator --lint-only -Wall build/rtl/core/core_rotate.v 2>&1 | \
        .venv/bin/python tools/linemap.py

It keeps the rest of each line. If it cannot map a location, it leaves the
location unchanged and adds a note.

Entangled marks each block in a tangled file with a line such as
// ~/~ begin <<book/core/core.md#build/rtl/core/core_rotate.v>>[1]. The name
after "#" is the block's #id, or else its file= path. [init] is the first
block with that name, and [n] is block number n + 1. A tangled line k lines
after a begin marker is k lines after that block's opening fence. The begin
marker therefore maps to the opening fence, and the end marker to the
closing fence. Entangled's noweb references (nested blocks) are not used in
this repository, so the mapper does not handle them.
"""

import os
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

BEGIN = re.compile(r"~/~ begin <<(?P<source>[^#<>]+)#(?P<name>[^#<>]+)>>\[(?P<count>init|\d+)\]")
END = re.compile(r"~/~ end")
LOCATIONS = [
    re.compile(r'(?P<before>File ")(?P<path>[^"]*build/[^"]+)(?P<middle>", line )(?P<line>\d+)'),
    re.compile(r"(?P<before>)(?P<path>[^\s:\"'()]*build/[^\s:\"'()]+)(?P<middle>:)(?P<line>\d+)"),
]
NOTE = "  (linemap: no source for this location)"


def block_name(info):
    """Entangled's name for a fenced block: its #id, or else its file= path."""
    match = re.fullmatch(r"\s*\{(.*)\}\s*", info)
    if not match:
        return None
    words = match.group(1).split()
    for word in words:
        if word.startswith("#"):
            return word[1:]
    for word in words:
        if word.startswith("file="):
            return word[len("file="):]
    return None


def fence_lines(markdown):
    """Map each block name to the 1-based lines of its opening fences, in order."""
    fences = {}
    for token in MarkdownIt("commonmark").parse(markdown):
        if token.type == "fence":
            name = block_name(token.info)
            if name:
                fences.setdefault(name, []).append(token.map[0] + 1)
    return fences


def lookup(path, line):
    """Return (markdown path, line) for a line of a tangled file, or None."""
    try:
        tangled = Path(path).read_text().splitlines()
    except OSError:
        return None
    if not 1 <= line <= len(tangled):
        return None
    for number in range(line, 0, -1):
        text = tangled[number - 1]
        if match := BEGIN.search(text):
            break
        if END.search(text) and number != line:
            return None
    else:
        return None
    source = match.group("source")
    try:
        fences = fence_lines(Path(source).read_text()).get(match.group("name"), [])
    except OSError:
        return None
    index = 0 if match.group("count") == "init" else int(match.group("count"))
    if index >= len(fences):
        return None
    return source, fences[index] + (line - number)


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
