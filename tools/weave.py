"""The weave: the reader edition of the book, as HTML and as LaTeX for the PDF.

make weave runs Sphinx with this extension and tools/bcw.py. The weave reads
nothing itself, and checks only that a schedule fits. It orders and reshapes
what bcw.py reads:

- The index holds the directive chapters. It lists the chapters in the parts
  of bcw.model: one numbered toctree for each kind, with the kind as its
  caption. Sphinx reads the index last, so that the order is known.
- At doctree-read, after bcw.py reads a chapter, each chunk becomes a container
  whose id is its anchor. Its first line shows its label and its anchor, and a
  "Serves:" line links to each parent.
- Each RATIONALE and DISCUSSION moves to a last section, Explanation, under a
  link back to the section that it came from. A "Why:" line links to it from
  its old place.
- At doctree-resolved, the HTML shows each twin and each source in a closed
  <details>. The LaTeX prints each twin in small text, moves each source to a
  last section, Implementation, and starts each kind with an unnumbered part.
- The HTML numbers the chapters through the whole book, as LaTeX does.
- A source block that uses fragments gets a line Uses: with a link to each
  fragment, and the first block of each fragment is its target.
- A check gets a line Verifies: with a link to each REQUIREMENT that it
  verifies. The HTML shows its code in a closed <details>, and the LaTeX prints
  it in small text. An equiv check has no code, so a paragraph names its module
  and its twin in place of the empty block.
- The HTML links static/weave.css, which sets each chunk apart. The LaTeX
  gives each chunk a box with the bar colour and background of its label in
  weave.css, so the PDF shows the same colours.
- Each :param: citation shows the value and unit of its PARAMETER or TARGET,
  and each PARAMETER and TARGET shows its value on its first line.
- The directive code-index lists each file and each fragment, with a link to
  the block that defines it and to each block that uses it.
- Each section of level 2 to 4 starts with a line Uses: that links each chunk
  of another section that the section needs (doc.live-set): the interface of
  the section, which its reader holds while reading it.
- The directive schedule draws a table of the thread whose instruction each
  stage holds in each cycle of one rotation. Its lines name the stages in order,
  and its option threads names the PARAMETER of the number of threads. Stage s
  holds, in cycle c, the thread (c - s) mod that number: the thread that
  fetched s cycles earlier, with thread 0 fetching in cycle 0. A schedule with
  more stages than threads gives a warning and no table, since a thread would
  then hold two stages in one cycle. The HTML lets the reader choose a thread to
  follow; the LaTeX sets thread 0 in bold. Under the table, the weave lists the
  shared registers that no stage holds, with what each holds. The weave writes
  each schedule to build/schedules.json, and tools/run_checks.py checks it
  against its module (doc.schedule-registers).
"""

import html
import json
import re
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx import addnodes
from sphinx.builders.latex.nodes import captioned_literal_block
from sphinx.errors import NoUri
from sphinx.util import logging
from sphinx.util.nodes import make_refnode
from sphinx.util.docutils import SphinxDirective

import bcw

CAPTIONS = {"tutorial": "Tutorials", "how-to": "How-to guides", "reference": "Reference",
            "explanation": "Explanation"}
LEFT_OUT = "Unordered"
logger = logging.getLogger(__name__)
MOVED = {"RATIONALE", "DISCUSSION"}


def read_index_last(app, env, docnames):
    """Read the index after every chapter, so that the chapters directive knows the order."""
    if app.config.root_doc in docnames:
        docnames.remove(app.config.root_doc)
        docnames.append(app.config.root_doc)


def parts(env):
    """(caption, [docname]) for each part of the book, in order, from the parts of the model.

    A chapter that the chapter order leaves out, or whose kind is not known,
    goes in a last part.
    """
    return [(CAPTIONS.get(kind, LEFT_OUT), [document.docname for document in documents])
            for kind, documents in bcw.model(env).parts]


def number_through(app, env):
    """Number the chapters of each part after those of the parts before it, as LaTeX does.

    Sphinx numbers each toctree from 1, and the chapters directive writes one
    toctree for each part. After Sphinx assigns the numbers, this adds to the
    first number of each heading in a later part the count of the chapters
    before its part. It returns the chapters that it renumbers, so that Sphinx
    writes them again.
    """
    changed, offset = [], 0
    for _, docnames in parts(env):
        for docname in docnames:
            if offset:
                shift(env, docname, offset)
                changed.append(docname)
        offset += len(docnames)
    return changed


def shift(env, docname, offset):
    def moved(number):
        return [number[0] + offset, *number[1:]] if number else number

    env.toc_secnumbers[docname] = {anchor: tuple(moved(number))
                                   for anchor, number in env.toc_secnumbers.get(docname, {}).items()}
    for node in [*env.tocs[docname].findall(nodes.reference), env.titles.get(docname)]:
        if node is not None and node.get("secnumber"):
            node["secnumber"] = moved(node["secnumber"])


class ChaptersDirective(SphinxDirective):
    """The chapters of the book: one numbered toctree for each part."""

    def run(self):
        lines = []
        for caption, docnames in parts(self.env):
            lines += [".. toctree::", "   :numbered:", f"   :caption: {caption}", ""]
            lines += [f"   {docname}" for docname in docnames] + [""]
        node = nodes.Element()
        self.state.nested_parse(StringList(lines, self.get_source_info()[0]), self.content_offset, node)
        return node.children


class CodeIndexDirective(SphinxDirective):
    """The index of code: each file and each fragment, the chapter that defines it and the blocks that use it.

    Sphinx reads the index after every chapter, so the model holds the whole book.
    """

    def run(self):
        book = bcw.model(self.env)
        docname = self.env.docname
        chapters = {document.path: document.docname for document in book.documents}
        entries = nodes.bullet_list()
        for name, block in [*sorted(book.files.items()), *sorted(book.fragments.items())]:
            item = nodes.paragraph()
            item += [nodes.literal(text=name), nodes.Text(": defined in ")]
            home = chapters[block.path]
            identity = bcw.fragment_id(name) if bcw.is_fragment(block) else bcw.file_id(name)
            item += bcw.citation_link("", nodes.Text(self.env.titles[home].astext()), identity, docname)
            users = dict.fromkeys(user.target for user, _ in book.uses.get(name, []))
            for number, user in enumerate(users):
                item += nodes.Text(", used in " if number == 0 else ", ")
                target = bcw.fragment_id(user) if bcw.is_fragment_name(user) else bcw.file_id(user)
                item += bcw.citation_link("", nodes.literal(text=user), target, docname)
            item += nodes.Text(".")
            entries += nodes.list_item("", item)
        return [nodes.rubric(text="Index of code"), entries]


class ScheduleDirective(SphinxDirective):
    """A schedule: its caption, its stages and shared registers, and its options, drawn once the values are known.

    Its first lines name the stages in order, each as "stage: prefix" with the prefix of the names of the
    registers of the stage, or as "stage" alone. After a blank line, each line names shared registers of the
    module, as "name name: reason".
    """

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {"threads": directives.unchanged_required, "module": directives.unchanged,
                   "private": directives.unchanged}

    def run(self):
        text = "\n".join(self.content).strip()
        stage_lines, _, shared_lines = text.partition("\n\n")
        stages = [line.rpartition(":")[::2] if ":" in line else (line, "") for line in stage_lines.splitlines()]
        shared = [(names.split(), reason.strip()) for names, _, reason in
                  (line.partition(":") for line in shared_lines.splitlines() if line.strip())]
        node = nodes.container(classes=["schedule"], stages=[name.strip() for name, _ in stages],
                               prefixes=[prefix.strip() for _, prefix in stages], shared=shared,
                               threads=self.options.get("threads", ""), module=self.options.get("module", ""),
                               private=self.options.get("private", "").split(), caption=" ".join(self.arguments))
        node.source, node.line = self.get_source_info()
        return [node]


def cell(text, classes=(), strong=False):
    paragraph = nodes.paragraph()
    paragraph += nodes.strong(text=text) if strong else nodes.Text(text)
    return nodes.entry("", paragraph, classes=list(classes))


def schedule_table(identity, stages, threads, caption, bold):
    """The table of the owner of each stage in each cycle, with the owner bold where bold(owner)."""
    table = nodes.table(classes=["schedule"], ids=[f"{identity}-table"])
    table += nodes.title(text=caption)
    group = nodes.tgroup(cols=threads + 1)
    table += group
    group += [nodes.colspec(colwidth=4 if column == 0 else 1) for column in range(threads + 1)]
    group += nodes.thead("", nodes.row("", cell("stage"), *[cell(f"cycle {c}") for c in range(threads)]))
    body = nodes.tbody()
    for s, stage in enumerate(stages):
        owners = [(c - s) % threads for c in range(threads)]
        body += nodes.row("", cell(stage), *[cell(str(o), [f"t{o}"], bold(o)) for o in owners])
    group += body
    return table


def follow(identity, threads):
    """A radio button for each thread, and the style that highlights the cells of the chosen one."""
    inputs = "".join(f'<input type="radio" name="{identity}" id="{identity}-{t}" class="t{t}"'
                     f'{" checked" if t == 0 else ""}><label for="{identity}-{t}">{t}</label>' for t in range(threads))
    rules = ", ".join(f"#{identity} input.t{t}:checked ~ table td.t{t}" for t in range(threads))
    return nodes.raw("", f'<span class="follow">Follow thread</span>{inputs}<style>{rules} '
                         "{ background: var(--schedule-mine); font-weight: bold; }</style>", format="html")


def schedules(doctree):
    return [box for box in doctree.findall(nodes.container) if "stages" in box]


def schedule_problem(env, box):
    """Why the schedule cannot be drawn, or None."""
    threads, stages = env.bcw_values.get(box["threads"]), box["stages"]
    if not isinstance(threads, int) or threads < 1:
        return (f"the schedule names {box['threads'] or 'no PARAMETER'} in its option threads, which has no value "
                "that is a positive number")
    if not stages or len(stages) > threads:
        return (f"the schedule has {len(stages)} stages and {threads} threads, so it needs 1 to {threads} stages: "
                "with more, a thread would hold two stages in one cycle")
    for names, reason in box["shared"]:
        if not names or not reason:
            return f"the schedule line of {' '.join(names) or 'no register'} needs names, a colon and a reason"
    return None


def check_schedules(app, env):
    """Warn once for each schedule that does not fit, after bcw.py has found the values, and keep the
    record of each schedule for tools/run_checks.py."""
    env.weave_schedules = []
    for docname in sorted(env.found_docs):
        for box in schedules(env.get_doctree(docname)):
            problem = schedule_problem(env, box)
            if problem:
                logger.warning(problem, location=box)
            path = Path(box.source).relative_to(Path(app.srcdir).parent).as_posix()
            env.weave_schedules.append({"path": path, "line": box.line, "module": box["module"],
                                        "private": box["private"], "stages": box["stages"],
                                        "prefixes": box["prefixes"], "shared": box["shared"]})


def write_schedules(app, exception):
    """build/schedules.json: the record of each schedule, which tools/run_checks.py checks against its module."""
    root = app.config.bcw_tangle_root
    if exception is None and root is not None:
        bcw.write(Path(root) / "build" / "schedules.json",
                  json.dumps(getattr(app.env, "weave_schedules", []), indent=1) + "\n")


def shared_list(module, shared):
    """The registers of the module that no stage holds, each line with its reason."""
    if not shared:
        return []
    items = nodes.bullet_list()
    for names, reason in shared:
        item = nodes.paragraph()
        for number, name in enumerate(names):
            item += [nodes.Text(", " if number else ""), nodes.literal(text=name)]
        item += nodes.Text(f": {reason}")
        items += nodes.list_item("", item)
    return [nodes.paragraph(text=f"The registers of {module or 'the module'} that no stage holds:"), items]


def draw_schedules(env, doctree, builder_format):
    """Put the table of each schedule that fits in its place, and drop each other one."""
    for number, box in enumerate(schedules(doctree), 1):
        if schedule_problem(env, box):
            box.parent.remove(box)
            continue
        threads, stages, identity = env.bcw_values[box["threads"]], box["stages"], f"schedule-{number}"
        box["ids"] = [identity]
        if builder_format == "html":
            box += [follow(identity, threads), schedule_table(identity, stages, threads, box["caption"], lambda o: False)]
        else:
            box += schedule_table(identity, stages, threads, f"{box['caption']} Thread 0 is in bold.", lambda o: o == 0)
        box += shared_list(box["module"], box["shared"])


def link(anchor, docname):
    """A link to the chunk with the anchor, around the anchor as a literal."""
    return bcw.citation_link("", nodes.literal(text=anchor), anchor, docname)


def container(node, chunk, docname):
    """The chunk node as a container of standard nodes, from the Chunk that bcw.py read from it."""
    result = nodes.container(classes=["chunk", chunk.label.lower()], ids=node["ids"])
    if chunk.label in bcw.VALUED:
        result["anchor"], result["value"] = chunk.anchor, chunk.options.get("value")
    head = nodes.paragraph(classes=["chunk-label"])
    head += nodes.strong(text=chunk.label)
    if chunk.anchor:
        head += [nodes.Text(" "), nodes.literal(text=chunk.anchor)]
    if chunk.title:
        head += nodes.Text(" " + chunk.title)
    result += head
    result += node.children
    parents = bcw.parents(chunk)
    if parents:
        serves = nodes.paragraph(classes=["chunk-serves"])
        serves += nodes.Text("Serves: ")
        for number, parent in enumerate(parents):
            if number:
                serves += nodes.Text(", ")
            serves += link(parent, docname)
        result += serves
    return result


def new_id(root, node, prefix):
    """Give node the id prefix-n, with the first n that no node of the chapter at root has."""
    used = {ident for element in root.findall(nodes.Element) for ident in element["ids"]}
    number = 1
    while f"{prefix}-{number}" in used:
        number += 1
    node["ids"].append(f"{prefix}-{number}")


def last_section(root, title, prefix):
    """A new section at the end of the title section of the chapter at root."""
    section = nodes.section()
    new_id(root, section, prefix)
    section += nodes.title(text=title)
    top = next((child for child in root.children if isinstance(child, nodes.section)), root)
    top += section
    return section


def enclosing_section(node):
    while not isinstance(node, nodes.section):
        node = node.parent
    return node


def swap(old, new):
    """Put new in the place of old. replace_self would copy the classes of old to new."""
    old.parent.replace(old, new)


def link_uses(doctree, document):
    """Put a line Uses: after each source block that uses fragments, with a link to each fragment."""
    blocks = {block.line: block for block in document.blocks}
    for block in list(doctree.findall(nodes.literal_block)):
        if block.get("bcw") != "source":
            continue
        names = dict.fromkeys(name for _, name, _ in bcw.fragment_uses(blocks[block.line]))
        if not names:
            continue
        uses = nodes.paragraph(classes=["fragment-uses"])
        uses += nodes.Text("Uses: ")
        for number, name in enumerate(names):
            if number:
                uses += nodes.Text(", ")
            uses += bcw.citation_link("", nodes.literal(text=name), bcw.fragment_id(name), document.docname)
        block.parent.insert(block.parent.index(block) + 1, uses)


def link_checks(doctree, document):
    """Put a line Verifies: after each check, and name the module and the twin of an equiv check."""
    for block in list(doctree.findall(nodes.literal_block)):
        if block.get("bcw") != "check":
            continue
        check = next(check for check in document.blocks if check.line == block.line)
        verifies = nodes.paragraph(classes=["check-verifies"])
        verifies += nodes.Text("Verifies: ")
        for number, anchor in enumerate(bcw.verifies(check)):
            if number:
                verifies += nodes.Text(", ")
            verifies += link(anchor, document.docname)
        block.parent.insert(block.parent.index(block) + 1, verifies)
        if not check.text.strip():
            module = check.options.get("module", "")
            proof = nodes.paragraph(classes=["check-proof"])
            proof += [nodes.emphasis(text=summary(block)), nodes.Text(": the module "), nodes.literal(text=module),
                      nodes.Text(" equals the twin "), nodes.literal(text=check.options.get("twin", module)),
                      nodes.Text(".")]
            swap(block, proof)


def mark_sections(doctree, document, docname):
    """Put an empty line Uses: under the title of each section of level 2 to 4, which show_uses fills.

    The chunks that a section needs can be in chapters that Sphinx has not read yet, so
    the line waits for doctree-resolved. It keeps the key of its section in bcw.py: the
    path of the chapter and the title line.
    """
    for section in list(doctree.findall(nodes.section)):
        depth, parent = 1, section.parent
        while parent is not None:
            depth += isinstance(parent, nodes.section)
            parent = parent.parent
        if 2 <= depth <= 4 and section.line is not None:
            marker = nodes.paragraph(classes=["section-uses"])
            marker["bcw_section"], marker["bcw_doc"] = [document.path, section.line - 1], docname
            section.insert(1, marker)


def show_uses(app, doctree):
    """Fill each line Uses: with a link to each chunk of another section that the section needs, or remove it."""
    imports = bcw.imports(bcw.model(app.env))
    labels = app.env.domains.standard_domain.anonlabels
    for marker in [node for node in doctree.findall(nodes.paragraph) if "section-uses" in node["classes"]]:
        names = [name for name in imports.get(tuple(marker["bcw_section"]), []) if name in labels]
        if not names:
            marker.parent.remove(marker)
            continue
        marker += nodes.Text("Uses: ")
        for number, name in enumerate(names):
            if number:
                marker += nodes.Text(", ")
            docname, labelid = labels[name]
            try:
                marker += make_refnode(app.builder, marker["bcw_doc"], docname, labelid, nodes.literal(text=name))
            except NoUri:
                # The label is in a chapter that the build leaves out, which doc.chapter-path reports.
                marker += nodes.literal(text=name)


def reshape(app, doctree):
    """Make each chunk a container, link the uses of fragments, and move each argument to the Explanation section."""
    docname = app.env.docname
    if docname == app.config.root_doc:
        return
    document = app.env.bcw_documents[docname]
    mark_sections(doctree, document, docname)
    link_uses(doctree, document)
    link_checks(doctree, document)
    chunks = {chunk.line: chunk for chunk in document.chunks}
    moved = []
    for node in list(doctree.findall(bcw.chunk)):
        chunk = chunks[node.line]
        box = container(node, chunk, docname)
        swap(node, box)
        if chunk.label in MOVED:
            moved.append(box)
    if not moved:
        return
    explanation = last_section(doctree, "Explanation", "explanation")
    for box in moved:
        origin = enclosing_section(box.parent)
        item = nodes.container(classes=["explanation"])
        new_id(doctree, item, "why")
        item += nodes.rubric("", "", nodes.reference("", origin[0].astext(), refid=origin["ids"][0]))
        why = nodes.paragraph(classes=["chunk-why"])
        why += [nodes.Text("Why: "), nodes.reference("", "see the explanation", refid=item["ids"][0])]
        swap(box, why)
        item += box
        explanation += item


def summary(block):
    if block["bcw"] == "twin":
        return "Formal twin"
    if block["bcw"] == "check":
        return f"Check ({block['check']})"
    if block["bcw"] == "mutant":
        return f"Mutant of {block['target']}, which {block['options'].get('kills', '')} must catch"
    if bcw.is_fragment_name(block["target"]):
        return f"Fragment: {block['target']}"
    kind = "Verilog" if block["language"] == "verilog" else "Source"
    return f"{kind}: {block['target']}"


def code_blocks(root, kind):
    return [block for block in list(root.findall(nodes.literal_block)) if block.get("bcw") == kind]


def wrap(block, before, after):
    parent = block.parent
    parent.insert(parent.index(block), before)
    parent.insert(parent.index(block) + 1, after)


def weave_html(doctree):
    for block in (code_blocks(doctree, "twin") + code_blocks(doctree, "source") + code_blocks(doctree, "check")
                  + code_blocks(doctree, "mutant")):
        wrap(block, nodes.raw("", f"<details><summary>{html.escape(summary(block))}</summary>", format="html"),
             nodes.raw("", "</details>", format="html"))


def titled(block, setup=""):
    """Make the label of a block the title of its frame, with no space between them, so that it reads
    as the header of the code."""
    box = captioned_literal_block()
    swap(block, box)
    box += [nodes.caption(text=summary(block)), block]
    wrap(box, nodes.raw("", rf"\begingroup{setup}\def\sphinxbelowcaptionspace{{0pt}}", format="latex"),
         nodes.raw("", r"\endgroup", format="latex"))


def weave_latex_chapter(root):
    # LaTeX labels the ids of a target, but not the ids of a container.
    for box in list(root.findall(nodes.container)):
        if box["ids"]:
            box.insert(0, nodes.target(ids=box["ids"]))
            box["ids"] = []
    for block in code_blocks(root, "twin") + code_blocks(root, "check") + code_blocks(root, "mutant"):
        titled(block, r"\fvset{fontsize=\small}")
    sources = code_blocks(root, "source")
    if not sources:
        return
    implementation = last_section(root, "Implementation", "implementation")
    for block in sources:
        item = nodes.container(classes=["implementation"])
        target = nodes.target()
        new_id(root, target, "source")
        item += target
        pointer = nodes.paragraph()
        pointer += [nodes.Text(summary(block).split(":")[0] + ": "),
                    nodes.reference("", block["target"], refid=target["ids"][0])]
        swap(block, pointer)
        item += block
        titled(block)
        implementation += item


def weave_latex(app, doctree, docname):
    files = list(doctree.findall(addnodes.start_of_file))
    if files:
        first = {}
        for caption, docnames in parts(app.env):
            first[docnames[0]] = caption
        for start in files:
            weave_latex_chapter(start)
            if start["docname"] in first:
                caption = first[start["docname"]]
                # An unnumbered part, as in the HTML, which still has a line in the contents.
                start.parent.insert(start.parent.index(start), nodes.raw(
                    "", f"\\part*{{{caption}}}\\addcontentsline{{toc}}{{part}}{{{caption}}}", format="latex"))
    elif docname != app.config.root_doc:
        weave_latex_chapter(doctree)


def show_values(env, doctree):
    """Show the value of each cited PARAMETER or TARGET, and the value on the first line of each."""
    values, unit = env.bcw_values, bcw.model(env).units

    def shown(anchor):
        return " ".join(part for part in [str(values[anchor]), unit.get(anchor)] if part)

    for literal in list(doctree.findall(nodes.literal)):
        if "param" in literal["classes"] and literal.get("anchor") in values:
            swap(literal, nodes.inline(text=shown(literal["anchor"]), classes=["param"]))
    for box in doctree.findall(nodes.container):
        if "value" in box and box.get("anchor") in values:
            anchor = box["anchor"]
            derived = box["value"].strip() != str(values[anchor])
            box[0] += nodes.Text(f" = {box['value'].strip()} = {shown(anchor)}" if derived else f" = {shown(anchor)}")


def weave(app, doctree, docname):
    show_values(app.env, doctree)
    draw_schedules(app.env, doctree, app.builder.format)
    show_uses(app, doctree)
    if app.builder.format == "html":
        weave_html(doctree)
    elif app.builder.format == "latex":
        weave_latex(app, doctree, docname)


# The fonts of texlive-fonts-recommended, in place of Sphinx's default TeX Gyre fonts.
FONTS = r"\usepackage{mathptmx}\usepackage[scaled=.9]{helvet}\usepackage{courier}"


# The folder of weave.css, the stylesheet that sets each chunk apart.
STATIC = Path(__file__).resolve().parent / "static"


HEX = r"#([0-9a-fA-F]{6})"

# A box with a bar on its left side, over a background. It can break across
# pages. The bar of 3pt is the bar of 4px in weave.css.
BOX = (r"\newenvironment{bcwchunk}[2]{\def\FrameCommand{{\color{#1}\vrule width 3pt}"
       r"\fboxsep=6pt\colorbox{#2}}\MakeFramed{\advance\hsize-\width\FrameRestore}}{\endMakeFramed}")


def colours(css):
    """(bar, background) for each label, from the rules .chunk and .chunk.<label> of the stylesheet."""
    css = re.sub(r"(?s)/\*.*?\*/", "", css)
    declared = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        bar = re.search(r"border-left(?:-color)?:[^;]*" + HEX, body)
        background = re.search(r"background:\s*" + HEX, body)
        for selector in selectors.split(","):
            entry = declared.setdefault(selector.strip(), {})
            if bar:
                entry["bar"] = bar.group(1).upper()
            if background:
                entry["background"] = background.group(1).upper()
    base = declared[".chunk"]
    result = {}
    for name in bcw.CHUNK_DIRECTIVES:
        own = declared.get(f".chunk.{name}", {})
        result[name] = (own.get("bar", base["bar"]), own.get("background", base["background"]))
    return result


# The title of a block of code: a bar across the top of its frame, in place of a numbered caption.
# The frame of Sphinx reaches past the text by its border and padding, so the bar does too.
TITLE = (r"\makeatletter\renewcommand*\sphinxSetupCaptionForVerbatim[1]{\needspace{\sphinxliteralblockneedspace}"
         r"\def\sphinxVerbatimTitle{\spx@verb@boxes@fcolorbox@setup\fboxsep=3pt\noindent"
         r"\hskip-\dimexpr\spx@boxes@border@left+\spx@boxes@padding@left\relax\rlap{\colorbox{bcwtitle}"
         r"{\makebox[\dimexpr\linewidth+\spx@boxes@border@left+\spx@boxes@padding@left+\spx@boxes@padding@right"
         r"+\spx@boxes@border@right-2\fboxsep][l]{\small\strut\sphinxLiteralBlockLabel #1}}}}}\makeatother")


def chunk_boxes():
    """The LaTeX that gives the chunks of each label their box, and each block of code its title.
    Sphinx applies the environment sphinxclass<name> to a container with the class <name>."""
    css = (STATIC / "weave.css").read_text()
    title = re.search(r"details > summary\s*\{[^}]*background:\s*" + HEX, css).group(1).upper()
    lines = [BOX, rf"\definecolor{{bcwtitle}}{{HTML}}{{{title}}}", TITLE]
    for label, (bar, background) in colours(css).items():
        lines += [rf"\definecolor{{bcwbar{label}}}{{HTML}}{{{bar}}}",
                  rf"\definecolor{{bcwback{label}}}{{HTML}}{{{background}}}",
                  rf"\newenvironment{{sphinxclass{label}}}{{\begin{{bcwchunk}}{{bcwbar{label}}}{{bcwback{label}}}}}"
                  rf"{{\end{{bcwchunk}}}}"]
    return "\n".join(lines) + "\n"


def configure(app, config):
    # No fncychap: LaTeX then heads each chapter with its number in numerals, as the HTML does.
    # Sphinx names the contents after the caption of the first toctree, which is
    # the first part. The name is set back here, after Sphinx sets it.
    preamble = chunk_boxes() + config.latex_elements.get("preamble", "")
    config.latex_elements = {"fontpkg": FONTS, "fncychap": "",
                             "tableofcontents": r"\renewcommand{\contentsname}{Contents}\sphinxtableofcontents",
                             **config.latex_elements, "preamble": preamble}
    config.html_static_path = [*config.html_static_path, str(STATIC)]


def setup(app):
    app.setup_extension("bcw")
    app.connect("config-inited", configure)
    app.add_css_file("weave.css")
    app.add_directive("chapters", ChaptersDirective)
    app.add_directive("code-index", CodeIndexDirective)
    app.add_directive("schedule", ScheduleDirective)
    app.connect("env-before-read-docs", read_index_last)
    # After Sphinx's own numbering, which runs at the default priority of 500.
    app.connect("env-get-updated", number_through, priority=600)
    app.connect("doctree-read", reshape, priority=450)
    app.connect("doctree-resolved", weave)
    # After bcw.py finds the values, at the default priority of 500.
    app.connect("env-check-consistency", check_schedules, priority=600)
    app.connect("build-finished", write_schedules)
    return {"parallel_read_safe": False, "env_version": 1}
