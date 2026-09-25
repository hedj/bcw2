"""The fast checks on the book: labels, one-shall, anchors and stamps.

Run it from the repository root: .venv/bin/python tools/check.py [FILE ...]
With no FILE, it checks every book/**/*.md. It prints each finding as

    book/core/core.md:12: [stamps] core.rotation: message
        fix: what to do

and exits 1 if it found anything.

A chunk is a top-level paragraph that starts with a bold label, such as
**REQUIREMENT.** or **OPEN — title.**, with the fenced blocks that follow it
directly. The labels are GOAL, REQUIREMENT, PARAMETER, DEFINITION, RATIONALE,
DISCUSSION, TARGET and OPEN. A GOAL and a rule (REQUIREMENT, PARAMETER or
DEFINITION) need an anchor. Only a rule can have a formal twin.

The last line of the paragraph can be an attribute line, such as
{rule=core.rotation parent=prop.x}. A fenced block carries pandoc-style
attributes, such as {.python .formal file=... stamp=...}.
"""

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

LABELS = {"GOAL", "REQUIREMENT", "PARAMETER", "DEFINITION", "RATIONALE", "DISCUSSION", "TARGET", "OPEN"}
RULES = {"REQUIREMENT", "PARAMETER", "DEFINITION"}
ANCHORED = RULES | {"GOAL"}
ATTRIBUTE_KEYS = {"rule", "parent", "impl"}
LABEL = re.compile(r"\*\*([A-Z][A-Z]+)(?: — [^*]+?)?\.\*\*")
ATTRIBUTES = re.compile(r"\{([^{}]*)\}\s*")
ANCHOR = re.compile(r"[a-z][a-z0-9-]*(\.[a-z0-9-]+)+")
SHALL = re.compile(r"\bshall\b", re.IGNORECASE)
CODE_SPAN = re.compile(r"`[^`]*`")
IMPLEMENTS = re.compile(r"^[ \t]*# implements: (\S+)[ \t]*$", re.MULTILINE)


@dataclass
class Finding:
    path: str
    line: int
    check: str
    anchor: str
    message: str
    fix: str

    def __str__(self):
        return (f"{self.path}:{self.line}: [{self.check}] {self.anchor or '-'}: "
                f"{self.message}\n    fix: {self.fix}")


@dataclass
class Document:
    path: str
    chunks: list
    findings: list  # the findings that parsing met
    blocks: list  # every fenced block at the top level


@dataclass
class Block:
    line: int
    classes: set
    attrs: dict


@dataclass
class Chunk:
    path: str
    line: int
    label: str
    lines: list  # the paragraph's source lines, without the attribute line
    attrs: dict
    blocks: list = field(default_factory=list)

    @property
    def english(self):
        text = " ".join(self.lines)
        return " ".join(LABEL.sub("", text, count=1).split())

    @property
    def anchor(self):
        return self.attrs.get("rule")


def stamp(chunk):
    """The review stamp: a hash of the chunk's label and English."""
    return hashlib.sha256((chunk.label + " " + chunk.english).encode()).hexdigest()[:8]


def fence_attributes(info):
    """Parse a pandoc-style info string, such as {.python .formal file=x stamp=y}."""
    match = re.fullmatch(r"\s*\{(.*)\}\s*", info)
    if not match:
        return set(), {}
    classes, attrs = set(), {}
    for word in match.group(1).split():
        if word.startswith("."):
            classes.add(word[1:])
        elif "=" in word:
            key, _, value = word.partition("=")
            attrs[key] = value
    return classes, attrs


def parse(path, text):
    """Parse one document into its chunks."""
    source = text.splitlines()
    chunks, findings, blocks, current = [], [], [], None
    for token in MarkdownIt("commonmark").parse(text):
        if token.level != 0 or token.type in ("paragraph_close", "inline"):
            continue
        if token.type == "fence":
            blocks.append(Block(token.map[0] + 1, *fence_attributes(token.info)))
        if token.type == "fence" and current is not None:
            current.blocks.append(blocks[-1])
            continue
        if token.type == "fence" and "formal" in fence_attributes(token.info)[0]:
            findings.append(Finding(path, token.map[0] + 1, "stamps", None,
                                    "a formal block stands outside any rule chunk",
                                    "move it directly after the rule that it states"))
        current = None
        if token.type != "paragraph_open":
            continue
        start, end = token.map
        lines = source[start:end]
        match = LABEL.match(lines[0])
        if not match:
            continue
        attrs = {}
        attribute_line = ATTRIBUTES.fullmatch(lines[-1])
        if attribute_line:
            lines = lines[:-1]
            for word in attribute_line.group(1).split():
                key, _, value = word.partition("=")
                attrs[key] = value
        current = Chunk(path, start + 1, match.group(1), lines, attrs)
        chunks.append(current)
    return Document(path, chunks, findings, blocks)


def read(paths):
    return [parse(str(path), Path(path).read_text()) for path in paths]


# implements: doc.labels
def check_labels(chunk):
    if chunk.label not in LABELS:
        yield Finding(chunk.path, chunk.line, "labels", chunk.anchor,
                      f"{chunk.label} is not a label",
                      "use one of " + ", ".join(sorted(LABELS)))
    elif chunk.label == "REQUIREMENT" and not SHALL.search(CODE_SPAN.sub("", chunk.english)):
        yield Finding(chunk.path, chunk.line, "labels", chunk.anchor,
                      "the REQUIREMENT contains no \"shall\"",
                      "state it with \"shall\", or relabel it DEFINITION")


def check_one_shall(chunk):
    count = 0
    for offset, line in enumerate(chunk.lines):
        count += len(SHALL.findall(CODE_SPAN.sub("", line)))
        if count > 1:
            yield Finding(chunk.path, chunk.line + offset, "one-shall", chunk.anchor,
                          "the chunk holds more than one \"shall\"",
                          "split the chunk at the sentence with the second \"shall\"")
            return


# implements: doc.anchors
def check_anchor(chunk, seen, retired):
    for key in chunk.attrs:
        if key not in ATTRIBUTE_KEYS:
            yield Finding(chunk.path, chunk.line, "anchors", chunk.anchor,
                          f"unknown attribute {key}",
                          "use only " + ", ".join(sorted(ATTRIBUTE_KEYS)))
    anchor = chunk.anchor
    if chunk.label in ANCHORED and anchor is None:
        yield Finding(chunk.path, chunk.line, "anchors", None,
                      f"the {chunk.label} has no anchor",
                      "end the paragraph with an attribute line such as {rule=core.name}")
    if anchor is None:
        return
    if not ANCHOR.fullmatch(anchor):
        yield Finding(chunk.path, chunk.line, "anchors", anchor,
                      "the anchor is not lower-case words joined by dots",
                      "write it as chapter.name, for example core.rotation")
    elif anchor in retired:
        yield Finding(chunk.path, chunk.line, "anchors", anchor,
                      "the anchor is retired", "choose a new anchor")
    elif anchor in seen:
        yield Finding(chunk.path, chunk.line, "anchors", anchor,
                      f"the anchor is also at {seen[anchor]}", "choose a new anchor")
    else:
        seen[anchor] = f"{chunk.path}:{chunk.line}"


# implements: doc.stamps
def check_stamps(chunk):
    for block in chunk.blocks:
        if "formal" not in block.classes:
            continue
        expected = stamp(chunk)
        if chunk.label not in RULES:
            yield Finding(chunk.path, block.line, "stamps", chunk.anchor,
                          f"a formal block follows a {chunk.label}, which is not a rule",
                          "move it directly after the rule that it states")
        elif block.attrs.get("stamp") != expected:
            yield Finding(chunk.path, block.line, "stamps", chunk.anchor,
                          "the rule's English changed since its twin was last read",
                          f"read the twin against the rule, then set stamp={expected}")


def tool_implements(paths):
    """The anchors that the "# implements:" comments in the given files name."""
    return {anchor for path in paths for anchor in IMPLEMENTS.findall(Path(path).read_text())}


# implements: doc.implemented
def check_implemented(documents, tools):
    named = set(tools)
    for document in documents:
        for block in document.blocks:
            if "verilog" in block.classes and "implements" in block.attrs:
                named.update(block.attrs["implements"].split(","))
    for document in documents:
        for chunk in document.chunks:
            if (chunk.label == "REQUIREMENT" and chunk.anchor is not None
                    and chunk.anchor not in named and chunk.attrs.get("impl") != "none"):
                yield Finding(chunk.path, chunk.line, "implemented", chunk.anchor,
                              "no Verilog block and no check implements the REQUIREMENT",
                              "name it in an implements= list or an implements: comment, "
                              "or set impl=none")


def check(paths, retired, implemented=()):
    """Return every finding in the given documents.

    implemented holds the anchors that the tools name in "# implements:" comments.
    The first pass checks each chunk on its own. The second pass runs the checks
    that need the whole book.
    """
    documents = read(paths)
    findings, seen = [], {}
    for document in documents:
        findings += document.findings
        for chunk in document.chunks:
            findings += check_labels(chunk)
            findings += check_one_shall(chunk)
            findings += check_anchor(chunk, seen, retired)
            findings += check_stamps(chunk)
    findings += check_implemented(documents, implemented)
    return sorted(findings, key=lambda f: (f.path, f.line, f.check))


def main(argv):
    paths = argv or sorted(str(p) for p in Path("book").glob("**/*.md"))
    retired_file = Path("book/retired-anchors.txt")
    retired = set()
    if retired_file.exists():
        retired = {line.strip() for line in retired_file.read_text().splitlines()
                   if line.strip() and not line.startswith("#")}
    findings = check(paths, retired, tool_implements(sorted(Path("tools").glob("*.py"))))
    for finding in findings:
        print(finding)
    print(f"check: {len(paths)} documents, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
