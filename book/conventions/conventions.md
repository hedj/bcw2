# Documentation conventions

These conventions govern every chapter in `book/`. Each rule in them names the goal that
it supports.

## 1. Goals

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

**DEFINITION.** A documentation rule is a rule in this chapter that a script checks when
`make check` runs. The author drops a rule that no script can check, or reduces it to a part
that a script can check.
{rule=doc.scripted}

**RATIONALE.** Judgment decides whether a rule is right. A script decides whether the text
obeys it.
