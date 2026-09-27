"""The complexity measures of the code and the documents of the system.

The code of the system is each Python file under tools/, without tools/tests/. radon
counts its measures:

- lines: the lines of code of each file, without blank lines, comments and
  docstrings, summed;
- mccabe: the McCabe complexity (the number of independent paths) of each function,
  method and nested function, summed;
- halstead_volume and halstead_effort: the Halstead volume and effort of each file,
  summed. radon counts only the operators of arithmetic, comparisons and logic,
  so a call or an assignment adds nothing to them, but it adds to lines.

The documents of the system are the chapters (book/**/*.rst), readme.build and each
Markdown file at the root. The measures count only their prose, without code blocks
and inline code:

- words: the words that tools/ste_lint.py counts;
- reading_grade: the Flesch-Kincaid grade that textstat gives. The total grade is the
  grade of the prose of all the documents together, not the mean of their grades;
- ste_violations and ste_advisory: the hard and the advisory findings of
  tools/ste_lint.py;
- audit_days: the audit time of design.audit-time, the days that one engineer takes to
  check the chapters: their words and their lines of code (of code directives and
  literal blocks), AUDIT_RATE of them an hour for AUDIT_HOURS hours a day.

documents holds the measures of each document, by path: its words, its lines of code,
its reading grade and its STE findings.

The design of the system is the graph in build/design.json, which make check writes.
An edge a -> b says that a reader needs b to understand a. The measures count the
cognitive burden of the design:

- interactivity_mean and interactivity_max: the number of distinct elements that an
  element needs;
- overload and overloaded: the elements that need more than WORKING_MEMORY elements;
- propagation_cost: the mean share of the elements that depend on an element, directly
  or through others, which a reader re-reads to change it safely;
- live_peak and live_mean: the largest and the mean live set of the elements, which
  tools/bcw.py gives each node (doc.live-set): what a reader holds at an element, with
  each section of the book as a black box;
- forward_references: the needs of an element that the reading order puts later;
- vocabulary and vocabulary_total: the defined terms that each chapter uses;
- unimplemented and unverified: the REQUIREMENTs that nothing implements or verifies.

design is None when build/design.json does not exist.

With --compare BEFORE.json, the tool prints a table in place of the JSON: each
scalar measure before (from the file) and now, its change, and "worse" where it
rose. A higher value is worse for each of these measures. The pre-push hook uses it.

Run it from the root of the repository: ./dev python3 tools/metrics.py
"""

import argparse
import json
import re
from pathlib import Path

import ste_lint
import textstat
from radon.complexity import cc_visit
from radon.metrics import h_visit
from radon.raw import analyze
from radon.visitors import Function

DOCUMENTS = ["book/**/*.rst", "readme.build", "*.md"]
FENCED = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
# The rST directives whose content is code, not prose.
CODE_DIRECTIVES = {"source", "twin", "check", "mutant", "code-block", "code", "literalinclude", "math", "raw"}
DIRECTIVE = re.compile(r"\.\.\s+([\w-]+)::")
FIELD = re.compile(r":[\w-]+:(\s|$)")
UNDERLINE = re.compile(r"([=\-~^\"'`#*+.:_])\1{2,}")
LITERAL = re.compile(r"``[^`\n]*``")
ROLE = re.compile(r":[\w-]+:`([^`\n]*)`")
# The number of chunks that an adult holds in working memory (Cowan, 2001).
WORKING_MEMORY = 4
# The words or lines of code that an auditor checks in an hour, and the hours of audit in a day:
# the rates of design.audit-time in book/design/design.rst.
AUDIT_RATE = 300
AUDIT_HOURS = 4


def mccabe(blocks):
    """The McCabe complexity of each function in blocks and of each function nested in it, summed.

    radon lists each method as a function too, so a class adds nothing of its own.
    """
    return sum(block.complexity + mccabe(block.closures) for block in blocks if isinstance(block, Function))


def rst_parts(text):
    """The prose of an rST text and its number of lines of code.

    The prose is without code directives, literal blocks, directive lines, fields (such as
    directive options), comments, heading underlines and inline literals, and with the text of
    each role. A line of code is a line of a code directive or a literal block that is not blank
    and not an option.
    """
    kept, code = [], 0
    skip, in_code = None, False  # while skip is set, leave out the blank lines and the lines indented more
    for line in text.splitlines():
        indent, stripped = len(line) - len(line.lstrip()), line.strip()
        if skip is not None:
            if not stripped or indent > skip:
                code += in_code and bool(stripped) and not FIELD.match(stripped)
                continue
            skip = None
        directive = DIRECTIVE.match(stripped)
        if directive:
            if directive.group(1) in CODE_DIRECTIVES:
                skip, in_code = indent, True
        elif stripped.startswith(".."):
            skip, in_code = indent, False
        elif UNDERLINE.fullmatch(stripped) or FIELD.match(stripped):
            continue
        elif stripped.endswith("::"):
            kept.append(line[:-1])
            skip, in_code = indent, True
        else:
            kept.append(line)
    return ROLE.sub(r"\1", LITERAL.sub("", "\n".join(kept))), code


def parts(path, text):
    """The prose of one document and its number of lines of code."""
    if not path.endswith(".md"):
        return rst_parts(text)
    code = sum(1 for block in FENCED.finditer(text) for line in block.group(0).splitlines()[1:-1] if line.strip())
    return INLINE_CODE.sub("", FENCED.sub("", text)), code


def grade(text):
    return textstat.flesch_kincaid_grade(text) if text.split() else 0


def document_measures(path, text, code_lines):
    findings, words = ste_lint.lint(text, path)
    return {"words": words, "code_lines": code_lines, "reading_grade": grade(text),
            "ste_violations": sum(f["level"] == "advisory-free" for f in findings),
            "ste_advisory": sum(f["level"] == "advisory" for f in findings)}


def dependants_of(anchor, dependants):
    """The elements that depend on anchor, directly or through others."""
    found, stack = set(), [anchor]
    while stack:
        for other in dependants[stack.pop()] - found:
            found.add(other)
            stack.append(other)
    return found


def design_measures(graph):
    position = {node["anchor"]: node["position"] for node in graph["nodes"]}
    chapter = {node["anchor"]: node["chapter"] for node in graph["nodes"]}
    needs = {anchor: set() for anchor in position}
    dependants = {anchor: set() for anchor in position}
    terms = {}
    for source, target, kind in graph["edges"]:
        needs[source].add(target)
        dependants[target].add(source)
        if kind == "term":
            terms.setdefault(chapter[source], set()).add(target)
    count = len(position)
    interactivity = [len(targets) for targets in needs.values()]
    live = [node["live"] for node in graph["nodes"]]
    return {"elements": count,
            "interactivity_mean": sum(interactivity) / count if count else 0,
            "interactivity_max": max(interactivity, default=0),
            "overload": sum(size > WORKING_MEMORY for size in interactivity),
            "overloaded": sorted(anchor for anchor, targets in needs.items() if len(targets) > WORKING_MEMORY),
            "propagation_cost": sum(len(dependants_of(anchor, dependants)) for anchor in position) / count ** 2
            if count else 0,
            "live_peak": max(live, default=0),
            "live_mean": sum(live) / count if count else 0,
            "forward_references": sum(position[target] > position[source]
                                      for source, targets in needs.items() for target in targets),
            "vocabulary": {name: len(used) for name, used in sorted(terms.items())},
            "vocabulary_total": len(set().union(*terms.values())),
            "unimplemented": len(graph["unimplemented"]),
            "unverified": len(graph["unverified"])}


ROWS = ["lines", "mccabe", "halstead_volume", "halstead_effort", "words", "reading_grade", "ste_violations",
        "ste_advisory", "audit_days"]
DESIGN_ROWS = ["interactivity_mean", "interactivity_max", "overload", "propagation_cost", "live_peak", "live_mean",
               "forward_references", "vocabulary_total", "unimplemented", "unverified"]


def scalars(metrics):
    """Each scalar measure of the output of this tool, or None where it is missing."""
    design = metrics.get("design") or {}
    return {**{name: metrics.get(name) for name in ROWS}, **{name: design.get(name) for name in DESIGN_ROWS}}


def shown(value, sign=""):
    if value is None:
        return "none"
    return f"{value:{sign}.2f}" if isinstance(value, float) else f"{value:{sign}d}"


def comparison(before, after):
    """The table of each scalar measure before and after, with its change, and "worse" where it rose."""
    old, new = scalars(before), scalars(after)
    lines = [f"{'measure':20} {'before':>12} {'after':>12} {'change':>12}"]
    for name in old:
        row = f"{name:20} {shown(old[name]):>12} {shown(new[name]):>12}"
        if old[name] is not None and new[name] is not None:
            change = new[name] - old[name]
            row += f" {shown(change, '+'):>12}" + ("  worse" if round(change, 6) > 0 else "")
        lines.append(row)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Print the complexity measures of the code and the documents.")
    parser.add_argument("--compare", metavar="BEFORE.json", help="print a table of the change from this output")
    arguments = parser.parse_args()
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
    paths = sorted({path.as_posix() for pattern in DOCUMENTS for path in Path(".").glob(pattern)})
    split = {path: parts(path, Path(path).read_text()) for path in paths}
    texts = {path: text for path, (text, _) in split.items()}
    documents = {path: document_measures(path, text, code) for path, (text, code) in split.items()}
    metrics["words"] = sum(d["words"] for d in documents.values())
    metrics["reading_grade"] = grade("\n\n".join(texts.values()))
    metrics["ste_violations"] = sum(d["ste_violations"] for d in documents.values())
    metrics["ste_advisory"] = sum(d["ste_advisory"] for d in documents.values())
    book = [d["words"] + d["code_lines"] for path, d in documents.items() if path.startswith("book/")]
    metrics["audit_days"] = sum(book) / (AUDIT_RATE * AUDIT_HOURS)
    metrics["documents"] = documents
    graph = Path("build/design.json")
    metrics["design"] = design_measures(json.loads(graph.read_text())) if graph.exists() else None
    if arguments.compare:
        print(comparison(json.loads(Path(arguments.compare).read_text()), metrics))
    else:
        print(json.dumps(metrics))


if __name__ == "__main__":
    main()
