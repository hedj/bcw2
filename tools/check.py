"""The fast checks on the book: one check for each rule of book/conventions/conventions.md.

Each check function names the rule that it implements in an "# implements:"
comment. The function name follows the rule: check_labels implements
doc.labels, check_ears implements doc.ears, and so on.

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

import ste_lint

LABELS = {"GOAL", "REQUIREMENT", "PARAMETER", "DEFINITION", "RATIONALE", "DISCUSSION", "TARGET", "OPEN"}
RULES = {"REQUIREMENT", "PARAMETER", "DEFINITION"}
ANCHORED = RULES | {"GOAL"}
ATTRIBUTE_KEYS = {"rule", "parent", "impl", "never"}
LABEL = re.compile(r"\*\*([A-Z][A-Z]+)(?: — [^*]+?)?\.\*\*")
ATTRIBUTES = re.compile(r"\{([^{}]*)\}\s*")
ANCHOR = re.compile(r"[a-z][a-z0-9-]*(\.[a-z0-9-]+)+")
SHALL = re.compile(r"\bshall\b", re.IGNORECASE)
CODE_SPAN = re.compile(r"`[^`]*`")
EARS = re.compile(r"(?:[Ww]here [^,]+, )?(?:[Ww]hile [^,]+, )?(?:[Ww]hen [^,]+, |[Ii]f [^,]+, then )?"
                  r"(?P<actor>(?!(?:[Ww]here|[Ww]hile|[Ww]hen|[Ii]f) )[^,]+?) shall (?P<response>.+)\.")
DETERMINER = re.compile(r"^(?:the|a|an|each|every|no)\s+", re.IGNORECASE)
BOLD = re.compile(r"\*\*(.+?)\*\*")
DOTTED = re.compile(r"\b[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+\.?|\b(?:etc|vs|cf|approx|incl|esp|resp|ca)\.", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
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
    blocks: list  # every fenced or indented code block, at any depth
    spans: list  # (line, text) of every inline code span
    headings: list  # (line, level) of every heading at the top level


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

    @property
    def attribute_line(self):
        return self.line + len(self.lines)


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
    chunks, findings, blocks, spans, headings, current = [], [], [], [], [], None
    for token in MarkdownIt("commonmark").parse(text):
        if token.type == "inline":
            start, end = token.map
            for child in token.children:
                if child.type == "code_inline":
                    number = next((start + offset + 1 for offset, content in enumerate(source[start:end])
                                   if child.content in content), start + 1)
                    spans.append((number, child.content))
        if token.type in ("fence", "code_block"):
            blocks.append(Block(token.map[0] + 1, *fence_attributes(token.info)))
        if token.level != 0 or token.type in ("paragraph_close", "inline"):
            continue
        if token.type == "fence" and current is not None:
            current.blocks.append(blocks[-1])
            continue
        if token.type == "fence" and "formal" in fence_attributes(token.info)[0]:
            findings.append(Finding(path, token.map[0] + 1, "stamps", None,
                                    "a formal block stands outside any rule chunk",
                                    "move it directly after the rule that it states"))
        if token.type == "heading_open":
            headings.append((token.map[0] + 1, int(token.tag[1])))
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
    return Document(path, chunks, findings, blocks, spans, headings)


def read(paths):
    return [parse(str(path), Path(path).read_text()) for path in paths]


# implements: doc.labels
def check_labels(chunk):
    if chunk.label not in LABELS:
        yield Finding(chunk.path, chunk.line, "labels", chunk.anchor,
                      f"{chunk.label} is not a label",
                      "use one of " + ", ".join(sorted(LABELS)))


# implements: doc.one-shall
def check_one_shall(chunk):
    allowed = 1 if chunk.label == "REQUIREMENT" else 0
    count = 0
    for offset, line in enumerate(chunk.lines):
        count += len(SHALL.findall(CODE_SPAN.sub("", line)))
        if count > allowed:
            message = ("the REQUIREMENT holds more than one \"shall\"" if allowed else
                       f"the {chunk.label} holds \"shall\", which only a REQUIREMENT can")
            yield Finding(chunk.path, chunk.line + offset, "one-shall", chunk.anchor, message,
                          "split the REQUIREMENT at its second \"shall\"" if allowed else
                          "relabel it REQUIREMENT, or state it without \"shall\"")
            return
    if count < allowed:
        yield Finding(chunk.path, chunk.line, "one-shall", chunk.anchor,
                      "the REQUIREMENT holds no \"shall\"",
                      "state it with \"shall\", or relabel it DEFINITION")


# implements: doc.attribute-keys
def check_attribute_keys(chunk):
    for key in chunk.attrs:
        if key not in ATTRIBUTE_KEYS:
            yield Finding(chunk.path, chunk.attribute_line, "attribute-keys", chunk.anchor,
                          f"unknown attribute {key}",
                          "use only " + ", ".join(sorted(ATTRIBUTE_KEYS)))


# implements: doc.never-on-definition
def check_never_on_definition(chunk):
    if "never" in chunk.attrs and chunk.label != "DEFINITION":
        yield Finding(chunk.path, chunk.attribute_line, "never-on-definition", chunk.anchor,
                      "only a DEFINITION can carry never=", "move never= to the DEFINITION of the term")


# implements: doc.anchors
def check_anchors(chunk, seen, retired):
    anchor = chunk.anchor
    if chunk.label in ANCHORED and anchor is None:
        yield Finding(chunk.path, chunk.line, "anchors", None,
                      f"the {chunk.label} has no anchor",
                      "end the paragraph with an attribute line such as {rule=core.name}")
    if anchor is None:
        return
    if not ANCHOR.fullmatch(anchor):
        yield Finding(chunk.path, chunk.line, "anchors", anchor,
                      "the anchor is not two or more parts of lower-case letters, digits "
                      "and hyphens, joined by dots",
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
    """(path, line, anchor) for each "# implements:" comment in the given files."""
    found = []
    for path in paths:
        text = Path(path).read_text()
        for match in IMPLEMENTS.finditer(text):
            found.append((str(path), text.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


# implements: doc.implemented
def check_implemented(documents, tools):
    named = {anchor for _, _, anchor in tools}
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


# implements: doc.references
def check_references(documents, anchors, tools):
    fix = "name an existing anchor, and separate the entries of a list with commas only"
    for path, number, anchor in tools:
        if anchor not in anchors:
            yield Finding(path, number, "references", None, f"{anchor} is not an anchor in the book", fix)
    prefixes = {anchor.split(".")[0] for anchor in anchors}
    for document in documents:
        for chunk in document.chunks:
            if "parent" in chunk.attrs:
                for entry in chunk.attrs["parent"].split(","):
                    if entry not in anchors:
                        yield Finding(chunk.path, chunk.attribute_line, "references", chunk.anchor,
                                      f"the parent {entry!r} is not an anchor in the book", fix)
        for block in document.blocks:
            if "implements" in block.attrs:
                for entry in block.attrs["implements"].split(","):
                    if entry not in anchors:
                        yield Finding(document.path, block.line, "references", None,
                                      f"the implements= entry {entry!r} is not an anchor in the book", fix)
        for number, text in document.spans:
            if ANCHOR.fullmatch(text) and text.split(".")[0] in prefixes and text not in anchors:
                yield Finding(document.path, number, "references", None,
                              f"the citation {text} names no anchor in the book", fix)


def parents(chunk):
    return [entry for entry in chunk.attrs.get("parent", "").split(",") if entry]


# implements: doc.reaches-goal
def check_reaches_goal(documents):
    first = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.anchor is not None:
                first.setdefault(chunk.anchor, chunk)
    for anchor, chunk in first.items():
        if chunk.label == "GOAL":
            continue
        if not parents(chunk):
            yield Finding(chunk.path, chunk.attribute_line, "reaches-goal", anchor,
                          "the chunk has no parent", "name the goal or rule that it serves in parent=")
            continue
        seen, stack, reached, unknown, cycle = set(), parents(chunk), False, False, False
        while stack and not reached:
            name = stack.pop()
            if name == anchor:
                cycle = True
            elif name not in seen:
                seen.add(name)
                node = first.get(name)
                if node is None:
                    unknown = True
                elif node.label == "GOAL":
                    reached = True
                else:
                    stack.extend(parents(node))
        if not reached and not unknown:
            message = "the chunk reaches itself through its parents" if cycle else \
                "the chunk reaches no GOAL through its parents"
            yield Finding(chunk.path, chunk.attribute_line, "reaches-goal", anchor, message,
                          "name a parent that reaches a GOAL")


# implements: doc.definition-parent
def check_definition_parent(chunk):
    if chunk.label == "DEFINITION" and len(parents(chunk)) > 1:
        yield Finding(chunk.path, chunk.attribute_line, "definition-parent", chunk.anchor,
                      "the DEFINITION names more than one parent",
                      "keep the one parent that the term serves")


def crowded(documents):
    """The number of rules with more than two parents."""
    return sum(1 for document in documents for chunk in document.chunks
               if chunk.label in RULES and len(parents(chunk)) > 2)


def normalise(text):
    return " ".join(re.sub(r"[*_]", "", text).lower().split())


def defined_terms(documents):
    """The first bold text of each DEFINITION, outside code spans, normalised."""
    terms = set()
    for document in documents:
        for chunk in document.chunks:
            match = BOLD.search(CODE_SPAN.sub("", chunk.english)) if chunk.label == "DEFINITION" else None
            if match:
                terms.add(normalise(match.group(1)))
    return terms


# implements: doc.ears
def check_ears(documents):
    terms = defined_terms(documents)
    fix = "write it as [Where F,] [While S,] [When T, | If C, then] X shall R., with X a defined term"
    for document in documents:
        for chunk in document.chunks:
            if chunk.label != "REQUIREMENT":
                continue
            number = next((chunk.line + offset for offset, text in enumerate(chunk.lines)
                           if SHALL.search(CODE_SPAN.sub("", text))), chunk.line)
            for sentence in SENTENCE_END.split(CODE_SPAN.sub("CODE", chunk.english)):
                if not SHALL.search(sentence):
                    continue
                match = EARS.fullmatch(sentence)
                if match is None:
                    yield Finding(chunk.path, number, "ears", chunk.anchor,
                                  "the sentence does not have the EARS form", fix)
                    continue
                actor = normalise(DETERMINER.sub("", match.group("actor")))
                if actor not in terms:
                    yield Finding(chunk.path, number, "ears", chunk.anchor,
                                  f"the actor {actor!r} is not a defined term", fix)


# implements: doc.linter
def check_linter(chunk):
    if chunk.label not in RULES:
        return
    for finding in ste_lint.lint(chunk.english, chunk.path)[0]:
        if finding["level"] == "advisory-free":
            number = next((chunk.line + offset for offset, text in enumerate(chunk.lines)
                           if finding["match"] in text), chunk.line)
            yield Finding(chunk.path, number, "linter", chunk.anchor,
                          f"{finding['rule']} [{finding['match']}]", finding["message"])


# implements: doc.vocabulary
def check_vocabulary(documents):
    never = {word.lower(): chunk.anchor for document in documents for chunk in document.chunks
             if chunk.label == "DEFINITION" for word in chunk.attrs.get("never", "").split(",") if word}
    if not never:
        return
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(never))) + r")\b", re.IGNORECASE)
    for document in documents:
        for chunk in document.chunks:
            if chunk.label not in RULES:
                continue
            for offset, text in enumerate(chunk.lines):
                for match in pattern.finditer(CODE_SPAN.sub("", text)):
                    yield Finding(chunk.path, chunk.line + offset, "vocabulary", chunk.anchor,
                                  f"{match.group(0)!r} is a never-word of {never[match.group(0).lower()]}",
                                  f"use the term that {never[match.group(0).lower()]} defines")


# implements: doc.overview-first
def check_overview_first(document):
    second = [number for number, level in document.headings if level == 2][1:2]
    limit = second[0] if second else float("inf")
    for chunk in document.chunks:
        if chunk.line < limit:
            yield Finding(chunk.path, chunk.line, "overview-first", chunk.anchor,
                          "the chunk stands before the second ## heading of its chapter",
                          "move it after the overview, which holds explanation only")


ARGUMENT = {"RATIONALE", "DISCUSSION"}


# implements: doc.argument-budget
def check_argument_budget(document):
    starts = [number for number, level in document.headings if 2 <= level <= 4]
    sections = {}
    for chunk in document.chunks:
        above = [number for number in starts if number < chunk.line]
        if above:
            sections.setdefault(above[-1], []).append(chunk)
    for chunks in sections.values():
        if not any(chunk.label in RULES for chunk in chunks):
            continue
        arguments = [chunk for chunk in chunks if chunk.label in ARGUMENT]
        for chunk in arguments[1:]:
            yield Finding(chunk.path, chunk.line, "argument-budget", chunk.anchor,
                          "the section already holds a RATIONALE or DISCUSSION",
                          "merge the argument into the first block of the section")
        for chunk in arguments:
            if len(chunk.english.split()) > 40:
                yield Finding(chunk.path, chunk.line, "argument-budget", chunk.anchor,
                              f"the argument has {len(chunk.english.split())} words",
                              "cut it to 40 words, or move the explanation to the overview")


# implements: doc.code-kinds
def check_code_kinds(document):
    for block in document.blocks:
        if "file" not in block.attrs and not block.classes & {"formal", "check"}:
            yield Finding(document.path, block.line, "code-kinds", None,
                          "the code block is not tangled, and is not a twin or a check",
                          "give it file=, or the class .formal or .check")


# implements: doc.dotted-words
def check_dotted_words(chunk):
    if chunk.label != "REQUIREMENT":
        return
    for offset, text in enumerate(chunk.lines):
        for match in DOTTED.finditer(CODE_SPAN.sub("", text)):
            yield Finding(chunk.path, chunk.line + offset, "dotted-words", chunk.anchor,
                          f"the REQUIREMENT holds the dotted word {match.group(0)!r} outside a quotation",
                          "put it in a code span, such as `Q8.4`")


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
        findings += check_overview_first(document)
        findings += check_argument_budget(document)
        findings += check_code_kinds(document)
        for chunk in document.chunks:
            findings += check_labels(chunk)
            findings += check_one_shall(chunk)
            findings += check_attribute_keys(chunk)
            findings += check_never_on_definition(chunk)
            findings += check_anchors(chunk, seen, retired)
            findings += check_stamps(chunk)
            findings += check_definition_parent(chunk)
            findings += check_linter(chunk)
            findings += check_dotted_words(chunk)
    findings += check_implemented(documents, implemented)
    findings += check_references(documents, set(seen), implemented)
    findings += check_reaches_goal(documents)
    findings += check_ears(documents)
    findings += check_vocabulary(documents)
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
    print(f"check: {len(paths)} documents, {len(findings)} findings, "
          f"{crowded(read(paths))} rules with more than 2 parents")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
