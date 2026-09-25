# Documentation conventions

## 1. Overview

These conventions govern every chapter in `book/`. Each rule in them names the goal that it
supports.

The book holds reference text and explanation. The rules are the reference text, and the rest
of the book explains them. How-to guides go in `tools/README.md`, and the book has no
tutorials yet.

Each GOAL and each rule carries an anchor, such as `core.rotation`, on the attribute line at
the end of its paragraph. The attribute line also names the parents of the chunk.
`book/retired-anchors.txt` lists the anchors that no chunk can use again. `make check` also
prints the number of rules with more than two parents, because a long list of parents says
little.

Section 2 states the goals. The later sections define the terms and state the rules.

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

**REQUIREMENT.** Each chunk shall hold `shall` exactly once if it is a REQUIREMENT, and not at
all otherwise.
{rule=doc.one-shall parent=doc.one-reading,doc.rules-apart}

**REQUIREMENT.** Where a chunk is a rule or a GOAL, the chunk shall carry a unique anchor
that is not retired.
{rule=doc.anchors parent=doc.traceable}

**REQUIREMENT.** Each twin shall follow a rule directly and carry the stamp of that rule.
{rule=doc.stamps parent=doc.read-is-checked}

**RATIONALE.** Judgement decides whether a rule is right. A script decides whether the text
obeys it.

## 4. Trace

**REQUIREMENT.** Where a rule is a REQUIREMENT, the rule shall appear in an `implements=` list
or `implements:` comment, or carry `impl=none`.
{rule=doc.implemented parent=doc.traceable}

**DEFINITION.** A **reference** is an entry in a `parent=` or `implements=` list, an
`implements:` comment in `tools/`, or a citation.
{rule=doc.reference parent=doc.traceable}

**DEFINITION.** A **citation** is a code span of lower-case words joined by dots, whose first
word is also the first word of an anchor.
{rule=doc.citation parent=doc.traceable}

**REQUIREMENT.** Each reference shall name an anchor in the book.
{rule=doc.references parent=doc.traceable}

**REQUIREMENT.** Where a chunk carries an anchor and is not a GOAL, the chunk shall reach a
GOAL through its parents.
{rule=doc.reaches-goal parent=doc.traceable}

**REQUIREMENT.** Where a chunk is a DEFINITION, the chunk shall name at most one parent.
{rule=doc.definition-parent parent=doc.traceable}

**RATIONALE.** A Verilog block names the requirements that it implements in its
`implements=` list. A check in `tools/` names its rule in an `# implements:` comment, so each
documentation rule traces down to its script.

## 5. Sentences and layout

**DEFINITION.** A **REQUIREMENT sentence** is a sentence of a REQUIREMENT that holds `shall`.
{rule=doc.requirement-sentence parent=doc.one-reading}

**DEFINITION.** A **defined term** is the first bold text of a DEFINITION. In a REQUIREMENT
sentence, it can follow The, A, An, Each, Every or No.
{rule=doc.defined-term parent=doc.one-reading}

**REQUIREMENT.** Each REQUIREMENT sentence shall have the form
`[Where F,] [While S,] [When T, | If C, then] X shall R.`, where X names a defined term.
{rule=doc.ears parent=doc.one-reading,doc.traceable}

**REQUIREMENT.** Each rule shall have no finding of level `advisory-free` from
`tools/ste_lint.py`.
{rule=doc.linter parent=doc.one-reading,doc.one-engineer}

**REQUIREMENT.** No rule shall hold a word from the `never=` list of a DEFINITION.
{rule=doc.vocabulary parent=doc.one-reading}

**RATIONALE.** EARS gives each REQUIREMENT a fixed form, and a defined actor names who acts.
The linter keeps each rule short and plain. A `never=` list keeps one word for each meaning.

## 6. Layout

**REQUIREMENT.** Each chunk shall stand after the second `##` heading of its chapter.
{rule=doc.overview-first parent=doc.rules-apart,doc.one-engineer}

**DEFINITION.** A **section** is the text after a heading of level 2, 3 or 4, up to the next
heading of those levels.
{rule=doc.section parent=doc.one-engineer}

**REQUIREMENT.** Where a section holds a rule, the section shall hold at most one RATIONALE or
DISCUSSION, of 40 words or fewer.
{rule=doc.argument-budget parent=doc.one-engineer,doc.rules-apart}

**DEFINITION.** A **code block** is a fenced or indented block of code in a chapter.
{rule=doc.code-block parent=doc.rules-apart}

**REQUIREMENT.** Each code block shall carry `file=`, the class `.formal` or the class
`.check`.
{rule=doc.code-kinds parent=doc.rules-apart}

**RATIONALE.** A reader meets the purpose of a chapter before its rules, as Diátaxis keeps
explanation apart from reference. The budget keeps argument short. A code block is part of the
machine or a check of it.
