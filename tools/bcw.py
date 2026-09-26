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
Blocks. When every chapter is read, model() builds the Model of the whole book
once: the chapter order and its parts, the fragments, the files, the uses of
each fragment, and the values. The checks, the tangle and tools/weave.py read
the Model. At env-check-consistency, the extension runs each check and logs
each finding as a Sphinx warning, such as

    book/core/core.rst:12: WARNING: [stamps] core.rotation: message
        fix: what to do

Each check function names the rule of book/doc/doc.rst that it implements in an
"# implements:" comment. At build-finished, the extension writes each tangled
file, and build/tangle.json, which names the chapter line of each tangled line.

Configuration values, which tools/conf.py sets:
    bcw_tools            the files whose "# implements:" comments count
    bcw_general_words    the list of general words, or None to skip the checks
                         that need it
    bcw_retired_anchors  the list of retired anchors, or None
    bcw_tangle_root      the folder that tangled paths are relative to, or None
                         to tangle nothing
    bcw_summary          True to print a line of counts on standard output
"""

import ast
import hashlib
import heapq
import json
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective, SphinxRole
from sphinx.util.nodes import make_refnode

import ste_lint

RULES = {"REQUIREMENT", "PARAMETER", "DEFINITION"}
ANCHORED = RULES | {"GOAL", "TARGET"}
# The labels whose chunks carry a value.
VALUED = {"PARAMETER", "TARGET"}
KINDS = ["tutorial", "how-to", "reference", "explanation"]
ANCHOR = re.compile(r"[a-z][a-z0-9-]*(\.[a-z0-9-]+)+")
# A fragment use: a line of a source directive that holds only a fragment name
# between << and >>, after its indentation. A fragment name is a colon followed by
# the form of an anchor, so that a reader tells it from an anchor.
USE = re.compile(r"^(?P<indent>[ \t]*)<<(?P<name>:[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+)>>\s*$")
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
# The ends of a word after which an English plural takes es, not s.
SIBILANTS = ("s", "x", "z", "ch", "sh")
CITATIONS = ["rule", "param"]
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
    title: str = None  # the title of an OPEN

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
    citations: list = field(default_factory=list)  # (line, anchor, role)
    sections: list = field(default_factory=list)  # (title line, level, title)
    strays: list = field(default_factory=list)  # lines of text outside the title's section
    titles: list = field(default_factory=list)  # the line of each top-level title
    errors: int = 0  # the number of messages of level ERROR or above in the doctree


# The directives and the role


class chunk(nodes.General, nodes.Element):
    """A labelled chunk. Its attributes are label, anchor, options and option_lines."""


def option_lines(directive):
    """The line of each option under the directive, by name.

    Docutils rejects an unknown option only for a directive that allows some
    options, and an argument only for a directive that takes some. For any other
    directive, it reads them as text. This raises the error for both.
    """
    lines = {}
    for offset, text in enumerate(directive.block_text.splitlines()[1:], 1):
        match = re.match(r"\s+:([\w-]+):(\s|$)", text)
        if not match:
            break
        lines[match.group(1)] = directive.lineno + offset
    # implements: doc.attribute-keys
    for name in lines:
        if name not in (directive.option_spec or {}):
            raise directive.error(f'unknown option: "{name}".')
    # implements: doc.labels
    argument = directive.block_text.split("\n")[0].split("::", 1)[1].strip()
    if argument and not (directive.required_arguments or directive.optional_arguments):
        raise directive.error(f"the {directive.name} directive takes no argument.")
    return lines


class ChunkDirective(SphinxDirective):
    has_content = True
    label = None

    def run(self):
        node = chunk(label=self.label, anchor=self.arguments[0] if self.required_arguments else None,
                     options=dict(self.options),
                     title=self.arguments[0] if self.optional_arguments and self.arguments else None)
        node.source, node.line = self.get_source_info()
        node["option_lines"] = option_lines(self)
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
    "parameter": chunk_directive("PARAMETER", True, ["parent", "value", "unit"]),
    "definition": chunk_directive("DEFINITION", True, ["parent", "never"]),
    "rationale": chunk_directive("RATIONALE", False, []),
    "discussion": chunk_directive("DISCUSSION", False, []),
    "target": chunk_directive("TARGET", True, ["parent", "value", "unit"]),
    "open": chunk_directive("OPEN", False, [], titled=True),
}


class CodeDirective(SphinxDirective):
    has_content = True
    kind = None

    def run(self):
        option_lines(self)
        text = "\n".join(self.content)
        node = nodes.literal_block(text, text)
        node.source, node.line = self.get_source_info()
        node["bcw"] = self.kind
        node["options"] = dict(self.options)
        node["target"] = self.arguments[0] if self.required_arguments else self.options.get("file")
        node["first"] = self.content_offset + 1
        node["language"] = language(node["target"], self.kind)
        return [node]


def language(target, kind):
    """The language that Sphinx highlights a code block in: a twin is Python."""
    if kind == "twin" or (target or "").endswith(".py"):
        return "python"
    if (target or "").endswith((".v", ".sv")):
        return "verilog"
    return "none"


class TwinDirective(CodeDirective):
    kind = "twin"
    option_spec = {"file": directives.unchanged, "stamp": directives.unchanged}


class SourceDirective(CodeDirective):
    kind = "source"
    required_arguments = 1
    option_spec = {"implements": directives.unchanged}


class CheckDirective(CodeDirective):
    kind = "check"


class CitationRole(SphinxRole):
    """A citation: a link to the label of an anchor, around a literal.

    :rule:`anchor` cites a chunk, and :param:`anchor` cites the value of a
    PARAMETER, which the weave shows. The literal carries the name of the role
    as its class. The link does not warn when it finds no label, because
    doc.references reports each citation of an anchor that is not in the book.
    """

    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def run(self):
        literal = nodes.literal(self.rawtext, self.text, classes=[self.kind])
        literal["anchor"] = self.text
        literal["line"] = self.lineno
        return [citation_link(self.rawtext, literal, self.text, self.env.docname)], []


def citation_link(rawtext, content, anchor, docname):
    """A link from content to the chunk with the anchor, which resolve_citation resolves.

    It has no domain, so that Sphinx passes it to resolve_citation, which keeps
    content. Sphinx's own std ref would replace content with plain text.
    """
    return addnodes.pending_xref(rawtext, content, refdomain="", reftype="bcw", reftarget=anchor,
                                 refwarn=False, refdoc=docname)


def resolve_citation(app, env, node, content):
    """Resolve a citation link to the chunk that carries the anchor, or leave it unresolved."""
    if node.get("reftype") != "bcw":
        return None
    target = env.domains.standard_domain.anonlabels.get(node["reftarget"])
    if target is None:
        return None
    return make_refnode(app.builder, node["refdoc"], target[0], target[1], content)


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
    document = Document(path, docname.split("/")[-1], docname, None)
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
                label(app, docname, child, child["anchor"])
                item = Chunk(path, document.name, child.line, child["label"], child["anchor"], child["options"],
                             child["option_lines"], [], top=top, section=section, title=child.get("title"))
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
                if is_fragment(block):
                    label(app, docname, child, fragment_id(block.target))
                elif named(block):
                    label(app, docname, child, file_id(block.target))
                if owner is not None:
                    owner.blocks.append(block)
            elif not isinstance(child, nodes.system_message):
                if isinstance(child, nodes.literal) and set(child["classes"]) & set(CITATIONS):
                    document.citations.append((child["line"], child["anchor"], child["classes"][0]))
                if isinstance(child, nodes.Element):
                    walk(child, level, top, section, owner)

    walk(doctree, 0, 0, None, None)
    document.errors = sum(1 for message in doctree.findall(nodes.system_message) if message["level"] >= 3)
    for child in doctree.children:
        if not isinstance(child, (nodes.section, nodes.comment, nodes.target)) and child.line is not None:
            document.strays.append(child.line)
    document.titles += [child.line - 1 for child in doctree.children if isinstance(child, nodes.section)]
    app.env.bcw_documents[docname] = document
    app.env.bcw_model = None


def label(app, docname, node, name):
    """Make name the id of node, and a label that a citation can link to.

    name is the anchor of a chunk, fragment-<name> for the block of the fragment
    :<name>, or file-<path> for the block of a file. Only the first node with a name
    gets it: doc.anchors and doc.one-block report the others.
    """
    std = app.env.domains.standard_domain
    if name is not None and name not in std.anonlabels:
        node["ids"].append(name)
        std.note_hyperlink_target(name, docname, name, name)


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


def read_kind(app, doctree):
    """Take the kind of a chapter from its metadata, which Sphinx collects after read_document."""
    document = app.env.bcw_documents.get(app.env.docname)
    if document is not None:
        document.kind = app.env.metadata[app.env.docname].get("kind")


def purge_document(app, env, docname):
    env.bcw_documents.pop(docname, None)
    env.bcw_model = None


# The model


@dataclass
class Model:
    """What the checks, the tangle and the weave read about the whole book, built once from the Documents."""
    documents: list  # the Documents, by name
    ordered: list  # the Documents in the chapter order, then the chapters that it leaves out, by name
    left: list  # the names of the chapters that the chapter order leaves out
    parts: list  # (kind, [Document]) for each kind that has chapters, in the order of KINDS, then (None, the rest)
    fragments: dict  # the Block of each fragment name: its first block in the chapter order
    files: dict  # the Block of each file that a twin or a source writes: its first block in the chapter order
    uses: dict  # (Block, chapter line) of each use of each fragment name, in the chapter order
    values: dict  # the value of each PARAMETER and TARGET that evaluates
    failures: dict  # (Chunk, reason) of each PARAMETER and TARGET whose value does not evaluate
    units: dict  # the unit of each PARAMETER and TARGET, or None


def build_model(documents):
    documents = sorted(documents, key=lambda document: document.name)
    order, left = chapter_order(documents)
    by_name = {document.name: document for document in documents}
    ordered = [by_name[name] for name in order + left]
    parts = [(kind, [document for document in ordered if document.kind == kind and document.name not in left])
             for kind in KINDS]
    parts = [(kind, members) for kind, members in parts if members]
    placed = {document.name for _, members in parts for document in members}
    rest = [document for document in documents if document.name not in placed]
    if rest:
        parts.append((None, rest))
    fragments, files, uses = {}, {}, {}
    for document in ordered:
        for block in document.blocks:
            if is_fragment(block):
                fragments.setdefault(block.target, block)
            elif (block.kind == "twin" and block.target) or writes_file(block):
                files.setdefault(block.target, block)
            for number, name, _ in fragment_uses(block):
                uses.setdefault(name, []).append((block, number))
    values, failures = parameter_values(documents)
    units = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.label in VALUED and chunk.anchor is not None:
                units.setdefault(chunk.anchor, chunk.options.get("unit"))
    return Model(documents, ordered, left, parts, fragments, files, uses, values, failures, units)


def model(env):
    """The model of the book, built again after a chapter is read or removed."""
    if getattr(env, "bcw_model", None) is None:
        env.bcw_model = build_model(env.bcw_documents.values())
    return env.bcw_model


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


def section_number(heading):
    """Whether the heading starts with a section number, such as 2., 4.2 or the 1 of 1 Core.

    A number without a full stop that a word in lower case follows is a count,
    such as the 8 of 8 threads.
    """
    match = NUMBERED.match(heading)
    return bool(match) and ("." in match.group(0) or not heading[match.end():][:1].islower())


# implements: doc.heading-numbers
def check_heading_numbers(document):
    for number, _, text in document.sections:
        if section_number(text):
            yield Finding(document.path, number, "heading-numbers", None,
                          f"the heading {text!r} starts with a section number",
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
        for number, anchor, _ in document.citations:
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


def bases(word):
    """The words that word can be, with the ending of an English plural or of 's taken off."""
    result = {word}
    for mark in ("'s", "’s"):
        if word.endswith(mark):
            result.add(word[:-2])
    if word.endswith("ies"):
        result.add(word[:-3] + "y")
    if word.endswith("es") and word[:-2].endswith(SIBILANTS):
        result.add(word[:-2])
    if word.endswith("s") and not word[:-1].endswith(SIBILANTS):
        result.add(word[:-1])
    return result


def known(word, words):
    """Whether word is in words, as it stands or with the ending of a plural or of 's."""
    return not bases(word).isdisjoint(words)


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
def check_chapters_ordered(model):
    for document in model.documents:
        if document.name in model.left:
            yield Finding(document.path, 1, "chapters-ordered", None,
                          f"the chapter order leaves out {', '.join(model.left)}, because their parents form a cycle "
                          "or depend on one", "change a parent so that the parents between chapters run one way")


# Parameters


OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
FUNCTIONS = {"clog2": lambda number: max(0, number - 1).bit_length(), "min": min, "max": max}


class NoValue(Exception):
    """A value that does not evaluate, with the reason as its message."""


def constant_name(anchor):
    """The name of a PARAMETER in the tangled code: its anchor in upper case, with underscores."""
    return re.sub(r"[.-]", "_", anchor).upper()


def compute(node, names):
    """The integer that an expression node gives, with names mapped to values."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = compute(node.left, names), compute(node.right, names)
        if isinstance(node.op, ast.Pow) and abs(right) > 1024:
            raise NoValue("the exponent is larger than 1024")
        return OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = compute(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS
            and not node.keywords):
        return FUNCTIONS[node.func.id](*[compute(argument, names) for argument in node.args])
    raise NoValue(f"{ast.unparse(node)!r} is not allowed in a value")


def parameter_values(documents):
    """The value of each PARAMETER and TARGET that evaluates, and the reason for each that does not.

    A value names a PARAMETER by its anchor, and never a TARGET. The anchors become Python
    names before the parse, because Python would read a hyphen as a minus sign.
    """
    chunks = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.label in VALUED and chunk.anchor is not None:
                chunks.setdefault(chunk.anchor, chunk)
    values, failures = {}, {}

    def evaluate(anchor, path):
        if anchor in values or anchor in failures:
            return
        text = chunks[anchor].options.get("value")
        try:
            if text is None:
                raise NoValue("the PARAMETER has no value")
            names = {}

            def placeholder(match):
                names[f"_{len(names)}"] = match.group(0)
                return f"_{len(names) - 1}"

            source = ANCHOR.sub(placeholder, text)
            tree = ast.parse(source, mode="eval")
            for other in names.values():
                if other not in chunks:
                    raise NoValue(f"{other} is not a PARAMETER in the book")
                if chunks[other].label == "TARGET":
                    raise NoValue(f"{other} is a TARGET, and a value names only PARAMETERs")
                if other in path + [anchor]:
                    cycle = (path + [anchor])[(path + [anchor]).index(other):]
                    for member in cycle:
                        failures.setdefault(member, f"the values of {', '.join(cycle)} form a cycle")
                    raise NoValue(failures[anchor])
                evaluate(other, path + [anchor])
                if other in failures:
                    raise NoValue(f"the value names {other}, which has no value")
            result = compute(tree.body, {name: values[other] for name, other in names.items()})
            if type(result) is not int:
                raise NoValue(f"the value is {result!r}, which is not an integer")
            values[anchor] = result
        except SyntaxError:
            failures.setdefault(anchor, "the value is not an expression")
        except NoValue as error:
            failures.setdefault(anchor, str(error))
        except (ArithmeticError, TypeError, ValueError) as error:
            failures.setdefault(anchor, f"the value does not evaluate: {error}")

    for anchor in chunks:
        evaluate(anchor, [])
    return values, {anchor: (chunks[anchor], reason) for anchor, reason in failures.items()}


# implements: doc.parameter-values
# implements: doc.target-values
def check_parameter_values(model):
    for anchor, (chunk, reason) in model.failures.items():
        name = "target-values" if chunk.label == "TARGET" else "parameter-values"
        yield Finding(chunk.path, chunk.option_line("value"), name, anchor, reason,
                      "write the value as an integer, or an expression of integers, PARAMETER anchors, "
                      "+ - * // % ** and clog2, min and max, with a space on each side of a minus sign")


# implements: doc.constant-names
def check_constant_names(documents):
    seen = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.label != "PARAMETER" or chunk.anchor is None:
                continue
            other = seen.setdefault(constant_name(chunk.anchor), chunk.anchor)
            if other != chunk.anchor:
                yield Finding(chunk.path, chunk.line, "constant-names", chunk.anchor,
                              f"the constant name {constant_name(chunk.anchor)} is also the name of {other}",
                              "choose an anchor whose constant name no other PARAMETER has")


def anchor_labels(documents):
    """The label of the first chunk with each anchor."""
    labels = {}
    for document in documents:
        for chunk in document.chunks:
            if chunk.anchor is not None:
                labels.setdefault(chunk.anchor, chunk.label)
    return labels


# implements: doc.target-parents
def check_target_parents(documents):
    labels = anchor_labels(documents)
    for document in documents:
        for chunk in document.chunks:
            for parent in parents(chunk):
                if labels.get(parent) == "TARGET":
                    yield Finding(chunk.path, chunk.option_line("parent"), "target-parents", chunk.anchor,
                                  f"the parent {parent} is a TARGET, which a measurement of the finished "
                                  "hardware decides", "name the rule or GOAL that the chunk serves")


# implements: doc.param-citations
def check_param_citations(documents):
    labels = anchor_labels(documents)
    for document in documents:
        for number, anchor, kind in document.citations:
            if kind == "param" and anchor in labels and labels[anchor] not in VALUED:
                yield Finding(document.path, number, "param-citations", None,
                              f"the param citation names {anchor}, which is a {labels[anchor]}, "
                              "not a PARAMETER or a TARGET",
                              "cite it with the role rule, or name a PARAMETER or a TARGET")


# Fragments


def is_fragment_name(target):
    """Whether the argument of a source directive is a fragment name: a colon and the form of an anchor."""
    return target.startswith(":") and bool(ANCHOR.fullmatch(target[1:]))


def is_fragment(block):
    """Whether the block is a source directive that defines a fragment."""
    return block.kind == "source" and is_fragment_name(block.target)


def fragment_id(name):
    """The id and label of the block of the fragment name: fragment-<name without its colon>."""
    return "fragment-" + name[1:]


def file_id(target):
    """The id and label of the block of a file: file-<its path>."""
    return "file-" + target


def writes_file(block):
    """Whether the block is a source directive that writes a file: its argument holds a slash."""
    return block.kind == "source" and "/" in block.target


def fragment_uses(block):
    """(chapter line, fragment name, indentation) of each fragment use in a source directive."""
    if block.kind != "source":
        return []
    return [(block.first + offset, match["name"], match["indent"])
            for offset, text in enumerate(block.text.splitlines()) if (match := USE.match(text))]


def named(block):
    """The file or the fragment name that the block defines, or None."""
    return block.target if block.kind == "source" or (block.kind == "twin" and block.target) else None


def fragment_graph(model):
    """The fragments that the block of each fragment uses, and the fragments that a file uses."""
    graph = {name: {used for _, used, _ in fragment_uses(block)} for name, block in model.fragments.items()}
    roots = {name for name, places in model.uses.items() for block, _ in places if writes_file(block)}
    return graph, roots


def reached(graph, start):
    """The fragments that the fragments in start reach through their uses, start included."""
    seen, stack = set(), list(start)
    while stack:
        name = stack.pop()
        if name not in seen:
            seen.add(name)
            stack.extend(graph.get(name, ()))
    return seen


# implements: doc.source-targets
def check_source_targets(documents):
    for document in documents:
        for block in document.blocks:
            if block.kind == "source" and not (block.target.startswith("build/") or is_fragment(block)):
                yield Finding(document.path, block.line, "source-targets", None,
                              f"{block.target!r} is not a file under build/ and not a fragment name",
                              "name a file such as build/rtl/core/x.v, or a fragment such as :core.rotation-logic")


# implements: doc.fragment-uses
def check_fragment_uses(model):
    for document in model.documents:
        for block in document.blocks:
            for number, name, _ in fragment_uses(block):
                if name not in model.fragments:
                    yield Finding(document.path, number, "fragment-uses", None,
                                  f"no source directive defines the fragment {name}",
                                  f"define it with .. source:: {name}, or name a fragment that exists")


# implements: doc.fragments-used
def check_fragments_used(model):
    graph, roots = fragment_graph(model)
    used = reached(graph, roots)
    for name, block in model.fragments.items():
        if name not in used:
            yield Finding(block.path, block.line, "fragments-used", None,
                          f"the fragment {name} reaches no file",
                          f"use it with a line <<{name}>> in a source directive that writes a file")


# implements: doc.fragment-cycles
def check_fragment_cycles(model):
    graph = fragment_graph(model)[0]
    for name, block in model.fragments.items():
        if name in reached(graph, graph[name]):
            yield Finding(block.path, block.line, "fragment-cycles", None,
                          f"the fragment {name} reaches itself through its uses",
                          "remove a use from the cycle")


# implements: doc.one-block
def check_one_block(model):
    first = {}
    for document in model.ordered:
        for block in document.blocks:
            name = named(block)
            if name is None:
                continue
            if name in first:
                yield Finding(document.path, block.line, "one-block", block.chunk.anchor if block.chunk else None,
                              f"{name} already has a code block, at {first[name].path}:{first[name].line}",
                              "move this code into that block, or into a fragment that that block uses")
            else:
                first[name] = block


# implements: doc.whole-twins
def check_whole_twins(documents):
    for document in documents:
        for block in document.blocks:
            if block.kind != "twin":
                continue
            for offset, text in enumerate(block.text.splitlines()):
                if USE.match(text):
                    yield Finding(document.path, block.first + offset, "whole-twins",
                                  block.chunk.anchor if block.chunk else None,
                                  "the twin holds a line with the form of a fragment use",
                                  "put the code of the fragment in the twin, because a twin stays whole")


def crowded(documents):
    """The number of rules with more than two parents."""
    return sum(1 for document in documents for chunk in document.chunks
               if chunk.label in RULES and len(parents(chunk)) > 2)


def check(model, retired=(), tools=(), general=None):
    """Return every finding in the book of the model, in order of path, line and check.

    tools holds the (path, line, anchor) of each "# implements:" comment. With
    general=None, doc.known-words and doc.general-words are not checked, so that a
    test of another rule can use words that no list holds.
    """
    documents = model.documents
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
    findings += check_chapters_ordered(model)
    findings += check_parameter_values(model)
    findings += check_constant_names(documents)
    findings += check_param_citations(documents)
    findings += check_target_parents(documents)
    findings += check_source_targets(documents)
    findings += check_fragment_uses(model)
    findings += check_fragments_used(model)
    findings += check_fragment_cycles(model)
    findings += check_whole_twins(documents)
    findings += check_one_block(model)
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
    """Run every check on the book, and log each finding as a warning.

    If docutils could not read some of the chapters, no check runs and the tangle
    writes nothing: a directive with an error is missing from the Documents, so the
    findings would follow from the error and not from the book.
    """
    config = app.config
    book = model(env)
    errors = sum(document.errors for document in book.documents)
    env.bcw_stopped = errors > 0
    if env.bcw_stopped:
        env.bcw_findings, env.bcw_values = [], {}
        logger.warning(f"bcw: {errors} error{'s' if errors > 1 else ''} in the chapters, so no check ran: "
                       "correct the errors first", type="bcw", subtype="stopped")
        return
    general = None
    if config.bcw_general_words is not None:
        general = {word.lower() for word in listed(config.bcw_general_words)}
    retired = listed(config.bcw_retired_anchors) if config.bcw_retired_anchors is not None else set()
    env.bcw_findings = check(book, retired, tool_implements(config.bcw_tools), general)
    env.bcw_values = book.values
    for finding in env.bcw_findings:
        logger.warning(str(finding), location=f"{finding.path}:{finding.line}", type="bcw", subtype=finding.check)
    if config.bcw_summary:
        print(f"bcw: {len(book.documents)} chapters, {len(env.bcw_findings)} findings, "
              f"{crowded(book.documents)} rules with more than 2 parents")


# The tangle


def expand(blocks, defined, indent="", active=()):
    """(text, chapter path, chapter line) of each tangled line of blocks, each after indent.

    Each fragment use is replaced by the lines of its fragment, with the indentation
    of the use added. A use of a fragment that no source defines, or that is already
    being expanded, stays as it is: the checks report it.
    """
    lines = []
    for block in blocks:
        for offset, text in enumerate(block.text.splitlines()):
            match = USE.match(text) if block.kind == "source" else None
            if match and match["name"] in defined and match["name"] not in active:
                lines += expand([defined[match["name"]]], defined, indent + match["indent"],
                                active + (match["name"],))
            else:
                lines.append((indent + text if text else text, block.path, block.first + offset))
    return lines


def write(path, text):
    """Write text to path, unless the file already holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def tangle(app, exception):
    """Write each tangled file with its fragments in place, the constants, and build/tangle.json.

    build/tangle.json holds the chapter line of each line of each tangled file, by
    the path of the file in build/. tools/linemap.py reads it.
    """
    root = app.config.bcw_tangle_root
    if exception is not None or root is None or app.env.bcw_stopped:
        return
    book = model(app.env)
    record = tangle_parameters(book, root)
    for target, block in book.files.items():
        lines = expand([block], book.fragments)
        write(Path(root) / target, "".join(text + "\n" for text, _, _ in lines))
        record[target.removeprefix("build/")] = [[path, number] for _, path, number in lines]
    # One line for each tangled line, so that a reader can follow the file.
    files = [f' {json.dumps(name)}: {{"lines": [\n' + ",\n".join(f"  {json.dumps(place)}" for place in lines) + "\n ]}"
             for name, lines in sorted(record.items())]
    write(Path(root) / "build" / "tangle.json", '{"files": {\n' + ",\n".join(files) + "\n}}\n")


def tangle_parameters(book, root):
    """Write each PARAMETER that has a value as a constant, in SystemVerilog and in Python.

    It returns the chapter line of each line of the two files, by their paths in
    build/: the value line of a constant, and None for any other line.
    """
    constants = [(chunk, constant_name(chunk.anchor), book.values[chunk.anchor]) for document in book.documents
                 for chunk in document.chunks if chunk.label == "PARAMETER" and chunk.anchor in book.values]
    header = "The PARAMETERs of the book, which tools/bcw.py writes."
    # A module that reads some of the constants is correct, so the package turns off
    # Verilator's warning on an unused parameter for its own constants only.
    verilog = [(f"// {header}", None), ("package bcw_params;", None), ("/* verilator lint_off UNUSEDPARAM */", None)]
    python = [(f"# {header}", None)]
    for chunk, name, value in constants:
        place = [chunk.path, chunk.option_line("value")]
        verilog.append((f"localparam int {name} = {value};", place))
        python.append((f"{name} = {value}", place))
    verilog += [("/* verilator lint_on UNUSEDPARAM */", None), ("endpackage", None)]
    record = {}
    for target, lines in [("build/rtl/bcw_params.sv", verilog), ("build/model/bcw_params.py", python)]:
        write(Path(root) / target, "".join(text + "\n" for text, _ in lines))
        record[target.removeprefix("build/")] = [place for _, place in lines]
    return record


def init_environment(app):
    if not hasattr(app.env, "bcw_documents"):
        app.env.bcw_documents = {}
    app.env.bcw_values = {}
    app.env.bcw_stopped = False
    app.env.bcw_model = None


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
    for kind in CITATIONS:
        app.add_role(kind, CitationRole(kind))
    app.connect("missing-reference", resolve_citation)
    app.connect("builder-inited", init_environment)
    # Before Sphinx's own collectors at 500, so that the weave can add sections that
    # the table of contents then holds.
    app.connect("doctree-read", read_document, priority=400)
    app.connect("doctree-read", read_kind, priority=600)
    app.connect("env-purge-doc", purge_document)
    app.connect("env-check-consistency", check_book)
    app.connect("build-finished", tangle)
    return {"parallel_read_safe": False, "env_version": 1}
