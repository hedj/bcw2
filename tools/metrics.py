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
  tools/ste_lint.py.

documents holds the four document measures of each document, by path.

Run it from the root of the repository: ./dev python3 tools/metrics.py
"""

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
CODE_DIRECTIVES = {"source", "twin", "check", "code-block", "code", "literalinclude", "math", "raw"}
DIRECTIVE = re.compile(r"\.\.\s+([\w-]+)::")
FIELD = re.compile(r":[\w-]+:(\s|$)")
UNDERLINE = re.compile(r"([=\-~^\"'`#*+.:_])\1{2,}")
LITERAL = re.compile(r"``[^`\n]*``")
ROLE = re.compile(r":[\w-]+:`([^`\n]*)`")


def mccabe(blocks):
    """The McCabe complexity of each function in blocks and of each function nested in it, summed.

    radon lists each method as a function too, so a class adds nothing of its own.
    """
    return sum(block.complexity + mccabe(block.closures) for block in blocks if isinstance(block, Function))


def rst_prose(text):
    """The prose of an rST text: without code directives, literal blocks, directive lines, fields
    (such as directive options), comments, heading underlines and inline literals, and with the
    text of each role."""
    kept = []
    skip = None  # while set, leave out the blank lines and the lines indented more than this
    for line in text.splitlines():
        indent, stripped = len(line) - len(line.lstrip()), line.strip()
        if skip is not None:
            if not stripped or indent > skip:
                continue
            skip = None
        directive = DIRECTIVE.match(stripped)
        if directive:
            if directive.group(1) in CODE_DIRECTIVES:
                skip = indent
        elif stripped.startswith(".."):
            skip = indent
        elif UNDERLINE.fullmatch(stripped) or FIELD.match(stripped):
            continue
        elif stripped.endswith("::"):
            kept.append(line[:-1])
            skip = indent
        else:
            kept.append(line)
    return ROLE.sub(r"\1", LITERAL.sub("", "\n".join(kept)))


def prose(path, text):
    """The prose of one document."""
    if path.endswith(".md"):
        return INLINE_CODE.sub("", FENCED.sub("", text))
    return rst_prose(text)


def grade(text):
    return textstat.flesch_kincaid_grade(text) if text.split() else 0


def document_measures(path, text):
    findings, words = ste_lint.lint(text, path)
    return {"words": words, "reading_grade": grade(text),
            "ste_violations": sum(f["level"] == "advisory-free" for f in findings),
            "ste_advisory": sum(f["level"] == "advisory" for f in findings)}


def main():
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
    texts = {path: prose(path, Path(path).read_text()) for path in paths}
    documents = {path: document_measures(path, text) for path, text in texts.items()}
    metrics["words"] = sum(d["words"] for d in documents.values())
    metrics["reading_grade"] = grade("\n\n".join(texts.values()))
    metrics["ste_violations"] = sum(d["ste_violations"] for d in documents.values())
    metrics["ste_advisory"] = sum(d["ste_advisory"] for d in documents.values())
    metrics["documents"] = documents
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
