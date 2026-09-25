"""The Sphinx extension of the book: its directives, its checks and its tangle.

Each chunk of a chapter is a directive, such as

    .. requirement:: core.rotation
       :parent: design.timing-invariant

       The core shall give the turn after thread ``t`` to thread ``t + 1``.

       .. twin::
          :file: build/model/core_rotate.py
          :stamp: 0123abcd

          def core_rotate(turn): ...

At doctree-read, the extension turns each chapter into a Document of Chunks and
Blocks. At env-check-consistency, when every chapter is read, it runs each check
and logs each finding as a Sphinx warning, such as

    book/core/core.rst:12: WARNING: [stamps] core.rotation: message
        fix: what to do

Each check function names the rule of book/doc/doc.rst that it implements in an
"# implements:" comment. At build-finished, the extension writes each tangled
file, with a marker comment before each block that names its chapter line.

Configuration values, which tools/conf.py sets:
    bcw_tools            the files whose "# implements:" comments count
    bcw_general_words    the list of general words, or None to skip the checks
                         that need it
    bcw_retired_anchors  the list of retired anchors, or None
    bcw_tangle_root      the folder that tangled paths are relative to, or None
                         to tangle nothing
    bcw_summary          True to print a line of counts on standard output
"""

import hashlib
import heapq
import re
from dataclasses import dataclass, field
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective, SphinxRole

import ste_lint

RULES = {"REQUIREMENT", "PARAMETER", "DEFINITION"}
ANCHORED = RULES | {"GOAL"}
KINDS = ["tutorial", "how-to", "reference", "explanation"]
ANCHOR = re.compile(r"[a-z][a-z0-9-]*(\.[a-z0-9-]+)+")
SHALL = re.compile(r"\bshall\b", re.IGNORECASE)
# The prose of a chunk writes each quotation as this code span, which holds no
# word and which ste_lint skips.
PLACEHOLDER = "`§`"
EARS = re.compile(r"(?:[Ww]here [^,]+, )?(?:[Ww]hile [^,]+, )?(?:[Ww]hen [^,]+, |[Ii]f [^,]+, then )?"
                  r"(?P<actor>(?!(?:[Ww]here|[Ww]hile|[Ww]hen|[Ii]f) )[^,]+?) shall (?P<response>.+)\.")
DETERMINER = re.compile(r"^(?:the|a|an|each|every|no)\s+", re.IGNORECASE)
DOTTED = re.compile(r"\b[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+\.?|\b(?:etc|vs|cf|approx|incl|esp|resp|ca)\.", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
NUMBERED = re.compile(r"\d+(?:\.\d+)*\.?(?:\s|$)")
WORD = re.compile(r"[^\W\d_][^\W_]*(?:['’-][^\W_]+)*")
ENDINGS = ("", "s", "es", "'s", "’s")
IMPLEMENTS = re.compile(r"^[ \t]*# implements: (\S+)[ \t]*$", re.MULTILINE)

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    path: str
    line: int
    check: str
    anchor: str
    message: str
    fix: str

    def __str__(self):
        return f"[{self.check}] {self.anchor or '-'}: {self.message}\n    fix: {self.fix}"


@dataclass
class Chunk:
    path: str
    chapter: str
    line: int  # the line of the directive
    label: str
    anchor: str
    options: dict
    option_lines: dict  # the line of each option
    lines: list  # (line, source text) of each line of its own paragraphs
    prose: list = field(default_factory=list)  # (line, text) of the same lines as docutils reads them
    term: str = None  # the first :dfn: text of a DEFINITION, normalised
    top: int = 0  # the number of the second-level section that holds it, or 0
    section: int = None  # the title line of the innermost section of level 2 to 4
    blocks: list = field(default_factory=list)

    @property
    def english(self):
        return " ".join(" ".join(text for _, text in self.lines).split())

    def option_line(self, name):
        return self.option_lines.get(name, self.line)


@dataclass
class Block:
    path: str
    line: int
    kind: str  # twin, source or check; None for any other literal block
    options: dict
    target: str  # the tangled file, or None
    first: int  # the line of the first line of code
    text: str
    chunk: Chunk = None


@dataclass
class Document:
    path: str
    name: str  # the name of the chapter: the name of its file without .rst
    docname: str
    kind: str
    chunks: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    citations: list = field(default_factory=list)  # (line, anchor)
    sections: list = field(default_factory=list)  # (title line, level, title)
    strays: list = field(default_factory=list)  # lines of text outside the title's section
    titles: list = field(default_factory=list)  # the line of each top-level title


# The directives and the role


class chunk(nodes.General, nodes.Element):
    """A labelled chunk. Its attributes are label, anchor, options and option_lines."""


class ChunkDirective(SphinxDirective):
    has_content = True
    label = None

    def run(self):
        node = chunk(label=self.label, anchor=self.arguments[0] if self.required_arguments else None,
                     options=dict(self.options))
        node.source, node.line = self.get_source_info()
        node["option_lines"] = {}
        for offset, text in enumerate(self.block_text.splitlines()[1:], 1):
            match = re.match(r"\s+:([\w-]+):", text)
            if not match:
                break
            node["option_lines"][match.group(1)] = self.lineno + offset
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


def chunk_directive(label, anchored, options, titled=False):
    """A directive class for a label: an anchored label takes its anchor, and OPEN takes a title."""
    return type(label.title() + "Directive", (ChunkDirective,), {
        "label": label,
        "required_arguments": 1 if anchored else 0,
        "optional_arguments": 1 if titled else 0,
        "final_argument_whitespace": titled,
        "option_spec": {name: directives.unchanged for name in options},
    })


# The registry is the list of labels and the options of each: docutils rejects
# any other directive and any other option.
# implements: doc.labels
# implements: doc.attribute-keys
CHUNK_DIRECTIVES = {
    "goal": chunk_directive("GOAL", True, ["parent"]),
    "requirement": chunk_directive("REQUIREMENT", True, ["parent", "impl"]),
    "parameter": chunk_directive("PARAMETER", True, ["parent"]),
    "definition": chunk_directive("DEFINITION", True, ["parent", "never"]),
    "rationale": chunk_directive("RATIONALE", False, []),
    "discussion": chunk_directive("DISCUSSION", False, []),
    "target": chunk_directive("TARGET", False, []),
    "open": chunk_directive("OPEN", False, [], titled=True),
}


class CodeDirective(SphinxDirective):
    has_content = True
    kind = None

    def run(self):
        text = "\n".join(self.content)
        node = nodes.literal_block(text, text)
        node.source, node.line = self.get_source_info()
        node["bcw"] = self.kind
        node["options"] = dict(self.options)
        node["target"] = self.arguments[0] if self.required_arguments else self.options.get("file")
        node["first"] = self.content_offset + 1
        return [node]


class TwinDirective(CodeDirective):
    kind = "twin"
    option_spec = {"file": directives.unchanged, "stamp": directives.unchanged}


class SourceDirective(CodeDirective):
    kind = "source"
    required_arguments = 1
    option_spec = {"implements": directives.unchanged}


class CheckDirective(CodeDirective):
    kind = "check"


class RuleRole(SphinxRole):
    """:rule:`anchor`, a citation. It shows as a literal until the weave links it."""

    def run(self):
        node = nodes.literal(self.rawtext, self.text, classes=["rule"])
        node["anchor"] = self.text
        node["line"] = self.lineno
        return [node], []


# Reading a chapter


def relative(app, docname):
    return str(Path(app.env.doc2path(docname)).relative_to(Path(app.srcdir).parent))


def normalise(text):
    return " ".join(re.sub(r"[*_]", "", text).lower().split())


def read_document(app, doctree):
    """Turn a chapter into a Document, and keep it in the environment."""
    docname = app.env.docname
    if docname == app.config.root_doc:
        return
    path = relative(app, docname)
    document = Document(path, docname.split("/")[-1], docname, app.env.metadata[docname].get("kind"))
    tops = [0]

    def walk(node, level, top, section, owner):
        for child in node.children:
            if isinstance(child, nodes.section):
                title = child.line - 1
                document.sections.append((title, level + 1, child[0].astext()))
                if level + 1 == 2:
                    tops[0] += 1
                walk(child, level + 1, tops[0] if level + 1 == 2 else top,
                     title if 2 <= level + 1 <= 4 else section, owner)
            elif isinstance(child, chunk):
                item = Chunk(path, document.name, child.line, child["label"], child["anchor"], child["options"],
                             child["option_lines"], [], top=top, section=section)
                for paragraph in child.children:
                    if isinstance(paragraph, nodes.paragraph):
                        item.lines += [(paragraph.line + offset, text)
                                       for offset, text in enumerate(paragraph.rawsource.splitlines())]
                        item.prose += paragraph_prose(paragraph)
                if item.label == "DEFINITION":
                    term = next((node for node in child.findall(nodes.emphasis) if "dfn" in node["classes"]), None)
                    item.term = normalise(term.astext()) if term is not None else None
                document.chunks.append(item)
                walk(child, level, top, section, item)
            elif isinstance(child, nodes.literal_block):
                block = Block(path, child.line, child.get("bcw"), child.get("options", {}), child.get("target"),
                              child.get("first", child.line), child.astext(), owner)
                document.blocks.append(block)
                if owner is not None:
                    owner.blocks.append(block)
            elif not isinstance(child, nodes.system_message):
                if isinstance(child, nodes.literal) and "rule" in child["classes"]:
                    document.citations.append((child["line"], child["anchor"]))
                if isinstance(child, nodes.Element):
                    walk(child, level, top, section, owner)

    walk(doctree, 0, 0, None, None)
    for child in doctree.children:
        if not isinstance(child, (nodes.section, nodes.comment, nodes.target)) and child.line is not None:
            document.strays.append(child.line)
    document.titles += [child.line - 1 for child in doctree.children if isinstance(child, nodes.section)]
    app.env.bcw_documents[docname] = document


def paragraph_prose(paragraph):
    """(line, text) of each line of a paragraph, as docutils reads it.

    Each quotation, which is a literal node, becomes PLACEHOLDER with the line
    breaks of its text, so that a quotation across a line break stays whole and
    each later word keeps its line. The text of emphasis, such as a :dfn: term,
    stays.
    """
    parts = []

    def walk(node):
        for child in node.children:
            if isinstance(child, nodes.literal):
                parts.append(PLACEHOLDER + "\n" * child.astext().count("\n"))
            elif isinstance(child, nodes.Text):
                parts.append(child.astext())
            else:
                walk(child)

    walk(paragraph)
    return [(paragraph.line + offset, text) for offset, text in enumerate("".join(parts).split("\n"))]


def purge_document(app, env, docname):
    env.bcw_documents.pop(docname, None)


# The checks on one chunk


# implements: doc.one-shall
def check_one_shall(chunk):
    allowed = 1 if chunk.label == "REQUIREMENT" else 0
    count = 0
    for number, text in chunk.prose:
        count += len(SHALL.findall(text))
        if count > allowed:
            message = ("the REQUIREMENT holds more than one \"shall\"" if allowed else
                       f"the {chunk.label} holds \"shall\", which only a REQUIREMENT can")
            yield Finding(chunk.path, number, "one-shall", chunk.anchor, message,
                          "split the REQUIREMENT at its second \"shall\"" if allowed else
                          "relabel it REQUIREMENT, or state it without \"shall\"")
            return
    if count < allowed:
        yield Finding(chunk.path, chunk.line, "one-shall", chunk.anchor,
                      "the REQUIREMENT holds no \"shall\"",
                      "state it with \"shall\", or relabel it DEFINITION")


# implements: doc.anchors
def check_anchors(chunk, seen, retired):
    anchor = chunk.anchor
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


def stamp(chunk):
    """The review stamp: a hash of the chunk's label and English."""
    return hashlib.sha256((chunk.label + " " + chunk.english).encode()).hexdigest()[:8]


# implements: doc.stamps
def check_stamps(document):
    for block in document.blocks:
        if block.kind != "twin":
            continue
        owner = block.chunk
        if owner is None:
            yield Finding(block.path, block.line, "stamps", None, "a twin stands outside any rule",
                          "move it inside the rule that it states")
        elif owner.label not in RULES:
            yield Finding(block.path, block.line, "stamps", owner.anchor,
                          f"a twin stands inside a {owner.label}, which is not a rule",
                          "move it inside the rule that it states")
        elif block.options.get("stamp") != stamp(owner):
            yield Finding(block.path, block.line, "stamps", owner.anchor,
                          "the rule's English changed since its twin was last read",
                          f"read the twin against the rule, then set :stamp: {stamp(owner)}")


def parents(chunk):
    return [entry.strip() for entry in chunk.options.get("parent", "").split(",") if entry.strip()]


# implements: doc.definition-parent
def check_definition_parent(chunk):
    if chunk.label == "DEFINITION" and len(parents(chunk)) > 1:
        yield Finding(chunk.path, chunk.option_line("parent"), "definition-parent", chunk.anchor,
                      "the DEFINITION names more than one parent",
                      "keep the one parent that the term serves")


# implements: doc.linter
def check_linter(chunk):
    if chunk.label not in ANCHORED or not chunk.prose:
        return
    first = chunk.prose[0][0]
    text = [""] * (chunk.prose[-1][0] - first + 1)
    for number, line in chunk.prose:
        text[number - first] = line
    for finding in ste_lint.lint("\n".join(text), chunk.path)[0]:
        if finding["level"] == "advisory-free":
            yield Finding(chunk.path, first + finding["line"] - 1, "linter", chunk.anchor,
                          f"{finding['rule']} [{finding['match']}]", finding["message"])


# implements: doc.dotted-words
def check_dotted_words(chunk):
    if chunk.label != "REQUIREMENT":
        return
    for number, text in chunk.prose:
        for match in DOTTED.finditer(text):
            yield Finding(chunk.path, number, "dotted-words", chunk.anchor,
                          f"the REQUIREMENT holds the dotted word {match.group(0)!r} outside a quotation",
                          "put it in an inline literal, such as ``Q8.4``")


# implements: doc.anchor-prefix
def check_anchor_prefix(chunk):
    if chunk.anchor is not None and ANCHOR.fullmatch(chunk.anchor) and chunk.anchor.split(".")[0] != chunk.chapter:
        yield Finding(chunk.path, chunk.line, "anchor-prefix", chunk.anchor,
                      f"the anchor does not start with {chunk.chapter}., the name of its chapter",
                      f"rename it to {chunk.chapter}.{chunk.anchor.split('.', 1)[1]}, "
                      "or move the chunk to its chapter")


# The checks on one chapter


# implements: doc.overview-first
def check_overview_first(document):
    for chunk in document.chunks:
        if chunk.top < 2:
            yield Finding(chunk.path, chunk.line, "overview-first", chunk.anchor,
                          "the chunk stands before the second section of its chapter",
                          "move it after the overview, which holds explanation only")


ARGUMENT = {"RATIONALE", "DISCUSSION"}


# implements: doc.argument-budget
def check_argument_budget(document):
    sections = {}
    for chunk in document.chunks:
        if chunk.section is not None:
            sections.setdefault(chunk.section, []).append(chunk)
    for chunks in sections.values():
        if not any(chunk.label in ANCHORED for chunk in chunks):
            continue
        arguments = [chunk for chunk in chunks if chunk.label in ARGUMENT]
        for chunk in arguments[1:]:
            yield Finding(chunk.path, chunk.line, "argument-budget", chunk.anchor,
                          "the section already holds a RATIONALE or DISCUSSION",
                          "merge the argument into the first one of the section")
        for chunk in arguments:
            if len(chunk.english.split()) > 40:
                yield Finding(chunk.path, chunk.line, "argument-budget", chunk.anchor,
                              f"the argument has {len(chunk.english.split())} words",
                              "cut it to 40 words, or move the explanation to the overview")


# implements: doc.code-kinds
def check_code_kinds(document):
    for block in document.blocks:
        if block.kind is None:
            yield Finding(document.path, block.line, "code-kinds", None,
                          "the code block is not a twin, a source or a check",
                          "write it in a twin, source or check directive")


# implements: doc.chapter-path
def check_chapter_path(document):
    if document.docname != f"{document.name}/{document.name}":
        yield Finding(document.path, 1, "chapter-path", None,
                      f"the chapter is not at book/{document.name}/{document.name}.rst",
                      f"move it to book/{document.name}/{document.name}.rst")


# implements: doc.chapter-title
def check_chapter_title(document):
    if not document.titles:
        yield Finding(document.path, 1, "chapter-title", None,
                      "the chapter has no title", "give it a title, with = above and below it")
    for number in document.titles[1:]:
        yield Finding(document.path, number, "chapter-title", None,
                      "the chapter has a second title",
                      "make it a section of the first title, or move its text to a chapter of its own")
    for number in document.strays:
        yield Finding(document.path, number, "chapter-title", None,
                      "the text stands outside the section of the title",
                      "move it under the title")


# implements: doc.chapter-kind
def check_chapter_kind(document):
    if document.kind not in KINDS:
        yield Finding(document.path, 1, "chapter-kind", None,
                      f"the chapter's :kind: is {document.kind!r}, not one of {', '.join(KINDS)}",
                      "start the chapter with a :kind: field, such as :kind: reference")


# implements: doc.heading-numbers
def check_heading_numbers(document):
    for number, _, text in document.sections:
        if NUMBERED.match(text):
            yield Finding(document.path, number, "heading-numbers", None,
                          f"the heading {text!r} starts with a number",
                          "remove the number, because the weave numbers the chapters and sections")


# The checks on the whole book


def tool_implements(paths):
    """(path, line, anchor) for each "# implements:" comment in the given files."""
    found = []
    for path in paths:
        text = Path(path).read_text()
        for match in IMPLEMENTS.finditer(text):
            found.append((str(path), text.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


def implements(block):
    return [entry.strip() for entry in block.options.get("implements", "").split(",")]


# implements: doc.implemented
def check_implemented(documents, tools):
    named = {anchor for _, _, anchor in tools}
    for document in documents:
        for block in document.blocks:
            if block.kind == "source":
                named.update(implements(block))
    for document in documents:
        for chunk in document.chunks:
            if (chunk.label == "REQUIREMENT" and chunk.anchor not in named
                    and chunk.options.get("impl") != "none"):
                yield Finding(chunk.path, chunk.line, "implemented", chunk.anchor,
                              "no source directive and no check implements the REQUIREMENT",
                              "name it in an :implements: list or an implements: comment, "
                              "or set :impl: none")


# implements: doc.references
def check_references(documents, anchors, tools):
    fix = "name an existing anchor, and separate the entries of a list with commas"
    for path, number, anchor in tools:
        if anchor not in anchors:
            yield Finding(path, number, "references", None, f"{anchor} is not an anchor in the book", fix)
    for document in documents:
        for chunk in document.chunks:
            if "parent" in chunk.options:
                for entry in chunk.options["parent"].split(","):
                    if entry.strip() not in anchors:
                        yield Finding(chunk.path, chunk.option_line("parent"), "references", chunk.anchor,
                                      f"the parent {entry.strip()!r} is not an anchor in the book", fix)
        for block in document.blocks:
            if block.kind == "source" and "implements" in block.options:
                for entry in implements(block):
                    if entry not in anchors:
                        yield Finding(document.path, block.line, "references", None,
                                      f"the :implements: entry {entry!r} is not an anchor in the book", fix)
        for number, anchor in document.citations:
            if anchor not in anchors:
                yield Finding(document.path, number, "references", None,
                              f"the citation {anchor} names no anchor in the book", fix)


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
            yield Finding(chunk.path, chunk.line, "reaches-goal", anchor,
                          "the chunk has no parent", "name the goal or rule that it serves in :parent:")
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
            yield Finding(chunk.path, chunk.option_line("parent"), "reaches-goal", anchor, message,
                          "name a parent that reaches a GOAL")


def defined_terms(documents):
    return {chunk.term for document in documents for chunk in document.chunks} - {None}


# implements: doc.ears
def check_ears(documents):
    terms = defined_terms(documents)
    fix = "write it as [Where F,] [While S,] [When T, | If C, then] X shall R., with X a defined term"
    for document in documents:
        for chunk in document.chunks:
            if chunk.label != "REQUIREMENT":
                continue
            number = next((number for number, text in chunk.prose if SHALL.search(text)), chunk.line)
            text = " ".join(" ".join(text for _, text in chunk.prose).split())
            for sentence in SENTENCE_END.split(text):
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


# implements: doc.vocabulary
def check_vocabulary(documents):
    never = {word.strip().lower(): chunk.anchor for document in documents for chunk in document.chunks
             for word in chunk.options.get("never", "").split(",") if word.strip()}
    if not never:
        return
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(never))) + r")\b", re.IGNORECASE)
    for document in documents:
        for chunk in document.chunks:
            if chunk.label not in ANCHORED:
                continue
            for number, text in chunk.prose:
                for match in pattern.finditer(text):
                    yield Finding(chunk.path, number, "vocabulary", chunk.anchor,
                                  f"{match.group(0)!r} is a never-word of {never[match.group(0).lower()]}",
                                  f"use the term that {never[match.group(0).lower()]} defines")


def known(word, words):
    """Whether word is in words, as it stands or with one of ENDINGS."""
    return any(word.endswith(ending) and word[:len(word) - len(ending)] in words for ending in ENDINGS)


# implements: doc.known-words
def check_known_words(documents, general):
    terms = sorted((tuple(term.split()) for term in defined_terms(documents)), key=len, reverse=True)

    def term_at(words, index):
        """The number of words of the longest defined term at words[index], or 0."""
        for term in terms:
            found = [word for word, _ in words[index:index + len(term)]]
            if (len(found) == len(term) and found[:-1] == list(term[:-1])
                    and known(found[-1], {term[-1]})):
                return len(term)
        return 0

    for document in documents:
        for chunk in document.chunks:
            if chunk.label not in ANCHORED:
                continue
            words = [(match.group(0).lower(), number)
                     for number, text in chunk.prose for match in WORD.finditer(text)]
            index = 0
            while index < len(words):
                size = term_at(words, index)
                if size == 0 and not known(words[index][0], general):
                    yield Finding(chunk.path, words[index][1], "known-words", chunk.anchor,
                                  f"{words[index][0]!r} is not a known word",
                                  "define it in a DEFINITION, list it in book/general-words.txt, "
                                  "or put it in a quotation")
                index += max(size, 1)


# implements: doc.general-words
def check_general_words(documents, general):
    for document in documents:
        for chunk in document.chunks:
            for word in sorted(general):
                if known(word, {chunk.term}):
                    yield Finding(chunk.path, chunk.line, "general-words", chunk.anchor,
                                  f"the defined term {chunk.term!r} is also the general word {word!r}",
                                  f"remove {word!r} from book/general-words.txt")


def chapter_order(documents):
    """The chapter order of doc.chapter-order, and the sorted names of the chapters that it leaves out.

    The chapters of each kind come together, in the order of KINDS. Within a kind,
    each chapter comes after the chapters of that kind that hold its parents.
    """
    chapter = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.anchor is not None:
                chapter.setdefault(chunk.anchor, document)
    order = []
    part = {document.name: KINDS.index(document.kind) if document.kind in KINDS else len(KINDS)
            for document in documents}
    for kind in sorted(set(part.values())):
        names = {name for name in part if part[name] == kind}
        before = {name: set() for name in names}
        for document in documents:
            if document.name not in names:
                continue
            for chunk in document.chunks:
                for parent in parents(chunk):
                    owner = chapter.get(parent)
                    if owner is not None and owner.name != document.name and owner.name in names:
                        before[document.name].add(owner.name)
        free = sorted(name for name in names if not before[name])
        while free:
            name = heapq.heappop(free)
            order.append(name)
            for other in sorted(names):
                if name in before[other]:
                    before[other].discard(name)
                    if not before[other]:
                        heapq.heappush(free, other)
    return order, sorted(set(part) - set(order))


# implements: doc.chapters-ordered
def check_chapters_ordered(documents):
    left = chapter_order(documents)[1]
    for document in documents:
        if document.name in left:
            yield Finding(document.path, 1, "chapters-ordered", None,
                          f"the chapter order leaves out {', '.join(left)}, because their parents form a cycle "
                          "or depend on one", "change a parent so that the parents between chapters run one way")


def crowded(documents):
    """The number of rules with more than two parents."""
    return sum(1 for document in documents for chunk in document.chunks
               if chunk.label in RULES and len(parents(chunk)) > 2)


def check(documents, retired=(), tools=(), general=None):
    """Return every finding in the given documents, in order of path, line and check.

    tools holds the (path, line, anchor) of each "# implements:" comment. With
    general=None, doc.known-words and doc.general-words are not checked, so that a
    test of another rule can use words that no list holds.
    """
    findings, seen = [], {}
    for document in documents:
        for function in [check_overview_first, check_argument_budget, check_code_kinds, check_chapter_path,
                         check_chapter_title, check_chapter_kind, check_heading_numbers, check_stamps]:
            findings += function(document)
        for chunk in document.chunks:
            findings += check_one_shall(chunk)
            findings += check_anchors(chunk, seen, retired)
            findings += check_definition_parent(chunk)
            findings += check_linter(chunk)
            findings += check_dotted_words(chunk)
            findings += check_anchor_prefix(chunk)
    findings += check_implemented(documents, tools)
    findings += check_references(documents, set(seen), tools)
    findings += check_reaches_goal(documents)
    findings += check_ears(documents)
    findings += check_vocabulary(documents)
    findings += check_chapters_ordered(documents)
    if general is not None:
        findings += check_known_words(documents, general)
        findings += check_general_words(documents, general)
    return sorted(findings, key=lambda f: (f.path, f.line, f.check))


def listed(path):
    """The lines of a list file, without blank lines and # comments. No file is an empty list."""
    if not Path(path).exists():
        return set()
    return {line.strip() for line in Path(path).read_text().splitlines()
            if line.strip() and not line.startswith("#")}


def check_book(app, env):
    """Run every check on the book, and log each finding as a warning."""
    config = app.config
    documents = [env.bcw_documents[name] for name in sorted(env.bcw_documents)]
    general = None
    if config.bcw_general_words is not None:
        general = {word.lower() for word in listed(config.bcw_general_words)}
    retired = listed(config.bcw_retired_anchors) if config.bcw_retired_anchors is not None else set()
    env.bcw_findings = check(documents, retired, tool_implements(config.bcw_tools), general)
    for finding in env.bcw_findings:
        logger.warning(str(finding), location=f"{finding.path}:{finding.line}", type="bcw", subtype=finding.check)
    if config.bcw_summary:
        print(f"bcw: {len(documents)} chapters, {len(env.bcw_findings)} findings, "
              f"{crowded(documents)} rules with more than 2 parents")


# The tangle


def tangle(app, exception):
    """Write each tangled file, with a marker comment before each block."""
    root = app.config.bcw_tangle_root
    if exception is not None or root is None:
        return
    files = {}
    for name in sorted(app.env.bcw_documents):
        for block in app.env.bcw_documents[name].blocks:
            if block.kind in ("twin", "source") and block.target:
                files.setdefault(block.target, []).append(block)
    for target, blocks in files.items():
        comment = "#" if target.endswith(".py") else "//"
        lines = []
        for block in blocks:
            lines.append(f"{comment} bcw: {block.path}:{block.first}")
            lines += block.text.splitlines()
        path = Path(root) / target
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines) + "\n"
        if not path.exists() or path.read_text() != text:
            path.write_text(text)


def init_environment(app):
    if not hasattr(app.env, "bcw_documents"):
        app.env.bcw_documents = {}


def setup(app):
    app.add_config_value("bcw_tools", [], "env")
    app.add_config_value("bcw_general_words", None, "env")
    app.add_config_value("bcw_retired_anchors", None, "env")
    app.add_config_value("bcw_tangle_root", None, "env")
    app.add_config_value("bcw_summary", False, "env")
    app.add_node(chunk)
    for name, directive in CHUNK_DIRECTIVES.items():
        app.add_directive(name, directive)
    app.add_directive("twin", TwinDirective)
    app.add_directive("source", SourceDirective)
    app.add_directive("check", CheckDirective)
    app.add_role("rule", RuleRole())
    app.connect("builder-inited", init_environment)
    app.connect("doctree-read", read_document)
    app.connect("env-purge-doc", purge_document)
    app.connect("env-check-consistency", check_book)
    app.connect("build-finished", tangle)
    return {"parallel_read_safe": False, "env_version": 1}
