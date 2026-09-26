"""The weave: the reader edition of the book, as HTML and as LaTeX for the PDF.

make weave runs Sphinx with this extension and tools/bcw.py. The weave reads
and checks nothing itself. It orders and reshapes what bcw.py reads:

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
- The HTML links static/weave.css, which sets each chunk apart. The LaTeX
  gives each chunk a box with the bar colour and background of its label in
  weave.css, so the PDF shows the same colours.
- Each :param: citation shows the value and unit of its PARAMETER or TARGET,
  and each PARAMETER and TARGET shows its value on its first line.
- The directive code-index lists each file and each fragment, with a link to
  the block that defines it and to each block that uses it.
"""

import html
import re
from pathlib import Path

from docutils import nodes
from docutils.statemachine import StringList
from sphinx import addnodes
from sphinx.util.docutils import SphinxDirective

import bcw

CAPTIONS = {"tutorial": "Tutorials", "how-to": "How-to guides", "reference": "Reference",
            "explanation": "Explanation"}
LEFT_OUT = "Unordered"
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


def reshape(app, doctree):
    """Make each chunk a container, link the uses of fragments, and move each argument to the Explanation section."""
    docname = app.env.docname
    if docname == app.config.root_doc:
        return
    document = app.env.bcw_documents[docname]
    link_uses(doctree, document)
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
    for block in code_blocks(doctree, "twin") + code_blocks(doctree, "source"):
        wrap(block, nodes.raw("", f"<details><summary>{html.escape(summary(block))}</summary>", format="html"),
             nodes.raw("", "</details>", format="html"))


def weave_latex_chapter(root):
    # LaTeX labels the ids of a target, but not the ids of a container.
    for box in list(root.findall(nodes.container)):
        if box["ids"]:
            box.insert(0, nodes.target(ids=box["ids"]))
            box["ids"] = []
    for block in code_blocks(root, "twin"):
        label = nodes.paragraph("", "", nodes.emphasis(text=summary(block)))
        block.parent.insert(block.parent.index(block), label)
        wrap(block, nodes.raw("", r"\begingroup\fvset{fontsize=\small}", format="latex"),
             nodes.raw("", r"\endgroup", format="latex"))
    sources = code_blocks(root, "source")
    if not sources:
        return
    implementation = last_section(root, "Implementation", "implementation")
    for block in sources:
        item = nodes.container(classes=["implementation"])
        target = nodes.target()
        new_id(root, target, "source")
        item += [target, nodes.rubric(text=summary(block))]
        pointer = nodes.paragraph()
        pointer += [nodes.Text(summary(block).split(":")[0] + ": "),
                    nodes.reference("", block["target"], refid=target["ids"][0])]
        swap(block, pointer)
        item += block
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


def chunk_boxes():
    """The LaTeX that gives the chunks of each label their box. Sphinx applies the
    environment sphinxclass<name> to a container with the class <name>."""
    lines = [BOX]
    for label, (bar, background) in colours((STATIC / "weave.css").read_text()).items():
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
    app.connect("env-before-read-docs", read_index_last)
    # After Sphinx's own numbering, which runs at the default priority of 500.
    app.connect("env-get-updated", number_through, priority=600)
    app.connect("doctree-read", reshape, priority=450)
    app.connect("doctree-resolved", weave)
    return {"parallel_read_safe": False, "env_version": 1}
