# Documentation conventions

## 1. Overview

These conventions govern every chapter in `book/`. Each rule in them names the goal that it
supports.

The book holds reference text and explanation. The rules are the reference text, and the rest
of the book explains them. How-to guides go in `tools/README.md`, and the book has no
tutorials yet.

Each GOAL and each rule carries an anchor, such as `core.rotation`, on the attribute line at
the end of its paragraph. The attribute line also names the parents of the chunk.
`book/retired-anchors.txt` lists the anchors that no chunk can use again.

Section 2 states the goals. Section 3 defines the terms and states the rules for marking text.

## 2. Goals

**GOAL.** Every rule has one meaning, so that two readers of the rule build the same
machine.
{rule=doc.one-reading}

**GOAL.** Each rule is stated once. Its formal twin, its Verilog, its checks and every view
of it are tied to that statement or generated from it.
{rule=doc.one-source}

**GOAL.** The English of a rule and its formal twin cannot drift apart without a check
failing.
{rule=doc.read-is-checked}

**GOAL.** Every rule traces up to the goal or security property that it serves, and down to
its checks and its implementation. A reference stays valid when the chapters change.
{rule=doc.traceable}

**GOAL.** The chapters stay small and plain enough for one engineer to read completely, and
their reading burden is measured.
{rule=doc.one-engineer}

**GOAL.** A reader can tell at once which text is a rule, which is explanation, and which is
an open question or a record.
{rule=doc.rules-apart}

**GOAL.** A script finds each change that alters what the machine does, and sends it to the
author for approval.
{rule=doc.changes-reach-author}

## 3. Terms and marking

**DEFINITION.** A **chunk** is a paragraph that starts with a bold label, with the fenced
blocks that follow it directly.
{rule=doc.chunk parent=doc.rules-apart}

**DEFINITION.** A **rule** is a chunk labelled REQUIREMENT, PARAMETER or DEFINITION. The
English of a rule is its text without the label and the attribute line.
{rule=doc.rule parent=doc.rules-apart}

**DEFINITION.** The **normative text** of the book is the English of its rules. Unlabelled
text states no rule.
{rule=doc.normative parent=doc.rules-apart}

**DEFINITION.** A **documentation rule** is a rule in this chapter that a script checks when
`make check` runs. The author drops a rule that no script can check, or reduces it to a part
that a script can check.
{rule=doc.scripted parent=doc.one-reading}

**DEFINITION.** A **twin** is a fenced block with the class `.formal`.
{rule=doc.twin parent=doc.read-is-checked}

**DEFINITION.** The **stamp** of a rule is the first eight hexadecimal digits of the SHA-256
hash of its label, a space and its English.
{rule=doc.stamp parent=doc.read-is-checked}

**REQUIREMENT.** Each chunk shall carry one of these labels: GOAL, REQUIREMENT, PARAMETER,
DEFINITION, RATIONALE, DISCUSSION, TARGET or OPEN.
{rule=doc.labels parent=doc.rules-apart}

**REQUIREMENT.** Where a chunk is a rule or a GOAL, the chunk shall carry a unique anchor
that is not retired.
{rule=doc.anchors parent=doc.traceable}

**REQUIREMENT.** Each twin shall follow a rule directly and carry the stamp of that rule.
{rule=doc.stamps parent=doc.read-is-checked}

**RATIONALE.** Judgement decides whether a rule is right. A script decides whether the text
obeys it.
