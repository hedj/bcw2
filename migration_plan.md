# The BCW-2 Soubou's new repository: workflow and migration plan

This document is self-contained. It states the workflow the new repository
adopts, the decisions behind it, the evidence for its less obvious choices,
and the phases that set it up. Apart from the frozen BCW-1 repository, which
the machine is imported from, it needs no other document.

Three rules run through every phase:

- **Every phase ends in something that runs in continuous integration.**
- **No change of meaning is made before the design gate exists** (section 6.4).
- **The new repository's conventions are its own.** Its documentation
  requirements are those of section 3.8. Nothing here applies the BCW-1
  repository's other conventions to it: not its `CLAUDE.md`, and not the BCW-1
  checks that enforce them. What carries over from BCW-1 is the machine: its
  specification, its RTL, and the tests that verify it.

This document is a plan, not a rule set. The decisions of section 2.2 stay
open until the author records them in that table. Once the new conventions
document exists (section 6.5), it holds the rules, and this plan becomes a
record.

**How references are written here.** A specification section is named by its
document's mnemonic and its section number. For example, CAPH 2.9 is section
2.9 of `docs/05_REGIONS_HANDLES.md`. The paths are the frozen repository's,
which the import keeps.

| Mnemonic | File | Mnemonic | File |
|---|---|---|---|
| CONV | `docs/00_DOCUMENTATION_CONVENTIONS.md` | SURF | `docs/07_SURFACE_ENGINE.md` |
| RATH | `docs/01_ARCHITECTURE_RATIONALE.md` | GRPH | `docs/08_GRAPHICS_DISPLAY.md` |
| SYST | `docs/02_SYSTEM_OVERVIEW.md` | AUDP | `docs/09_AUDIO_PERIPHERALS.md` |
| CORE | `docs/03_CORE_PIPELINE.md` | ETHR | `docs/10_ETHERNET.md` |
| MEMC | `docs/04_MEMORY_ACCELERATOR.md` | CRYP | `docs/11_CRYPTO_ENGINE.md` |
| CAPH | `docs/05_REGIONS_HANDLES.md` | STOR | `docs/12_STORAGE.md` |
| SIPC | `docs/06_SYSTEM_SERVICES_IPC.md` | HIDV | `docs/13_HID.md` |
| VERI | `docs/14_VERIFICATION_LIFECYCLE.md` | SPER | `docs/15_SYSTEM_PERIPHERALS.md` |

Other paths used:

- the build plan: `impl/build-plan.md`;
- the open-numbers record: `exp/open-numbers.md`;
- the decisions record: `exp/decisions.md`;
- the census record: `exp/census.md`;
- the predecessor record: `exp/predecessors.md`.

Numbers such as #296 are BCW-1 review-queue numbers.

**Severity**, for defects: 1 would build a different machine, 2 misleads a
reader, and 3 is cosmetic.

## 1. Where things stand

As of 24 September 2026, the frozen repository is `hedj/bcw` (private). Its
default branch, `claude/plan-review-mab78k`, is at commit `60df9a1`.

| What | State |
|---|---|
| Specification | 16 documents, `docs/00_*.md` to `docs/15_*.md`. 497 labelled statements, 244 of them REQUIREMENTs. 367 occurrences of "shall". |
| Built | The core (build-plan phase 1). The core on the board with the serial console (phase 1b). Display timing, line buffers and ramp (phase 2). |
| Next | Build-plan phase 3, the hardware trusted base (the build plan's section 1). |
| Checks | `make check` runs 32 checks in about 20 s. 28 of them verify the machine. The other 4 enforce BCW-1 conventions: `check-ste`, `check-xref`, `check-argument` and `check-lint`. `make gate` runs the 32, plus `check-serial-shipping`, `check-compliance` and `check-core-gate`, plus the bitstream, in about 9 min. `make formal` runs the toolchain smoke test and has no proofs yet. `make timing` and `make timing-sweep` also exist. |
| Specification model | `docs/formal/check.py` (330 lines) and `docs/formal/lifecycle.py` (390 lines): a model of the request lifecycle in Python over the z3 solver. 35 rules formalised, 25 sentences unmodelled, 12 scenarios, traces of 8 steps over 3 threads. Four findings: #296, #310, #311 and #312. |
| Review queue | `.claude/review-ledger.md`: 315 items and 27 settled decisions. 4 fixed, 63 dropped, 1 half-settled (#32), 247 open. Of the 248 not closed: 17 at severity 1, 102 at severity 2 (with #32), 129 at severity 3 (4 of them design-tagged). |
| Continuous integration | None. |

## 2. Decisions

### 2.1 Decided by the author

| Decision | Where it acts |
|---|---|
| **A new repository with a clean start**, and a literate structure: the BCW-1 documentation structure is replaced. The BCW-1 repository is frozen. | Everywhere |
| **The name.** The migrated design is the BCW-2 Soubou. Soubou (僧房) is its name, and BCW-2 its designation. BCW-1 is the frozen predecessor, which already called itself "the BCW-1 Soubou" (SYST 1), so the designation is what tells the two apart. Document identifiers keep the designation: `DOC-BCW2-<number>-<mnemonic>`. The name is OPEN in SYST 3, and closing it is a change of meaning, made first in pass 2. | Sections 6.2, 6.5 |
| **Scope.** The timing invariant holds between processes with no external time reference. External time references are the operating system's concern. | Section 4.1 |
| **Quotas.** Allocation from shared pools is by static quota, granted at creation. | Section 4.4 |
| **No signals.** Events arrive only as channel messages, taken by a blocking receive. | Section 4.4 |
| **Cognitive burden** replaces conceptual economy as the second design goal, starting with three measures, set per document. | Section 3.13 |
| **The RTL stays in Verilog,** literate by reference. | Section 3.2 |
| **One defect list,** a file in `exp/`. | Section 3.16 |
| **A conservative design gate:** a change to an untwinned rule or to a parameter is a design change. Choice A2 of section 5 extends this, subject to D2. | Section 3.15 |
| **The documentation requirements are those of section 3.8.** No other BCW-1 convention is applied. | Section 3.8 |

### 2.2 Needed before starting

| # | Decision | Recommended | Blocks |
|---|---|---|---|
| D1 | The new repository's name, and whether it is public | Public, or private with GitHub Pro. On GitHub Free, only public repositories get protected branches and rulesets. | W0 |
| D2 | Confirm the choices of section 5, A1 to A11. Each names the alternative it replaces. | Yes, all eleven | W2, W3 |
| D3 | The place-and-route build that recorded Fmax figures use | `yowasp-nextpnr-ecp5==0.11.1.0.post826`, pinned by pip and reproducible in CI. The native 0.11 build differs by 2.7 MHz on identical RTL. Re-measure the recorded figures with the pinned build before comparing new ones with them. `make timing` then uses only the pinned build. | W0 |
| D4 | Proof scope and engines | Prove beyond the four formal checks: self-composition for Leg 1, and later Leg 2 (section 3.12). This replaces VERI 1.2's "and not elsewhere", and its statement that proof establishes functional correctness and not timing. Yices is the primary engine and z3 the cross-check. Leave github.com off the network allow-list unless ABC is wanted. | P2, and the new `CLAUDE.md` |
| D5 | How the review queue migrates | Migrate the 119 items at severity 1 and 2 and the four design-tagged items at severity 3, 123 in all. Close the other 125 severity-3 items with a note in the migration ledger. The model's baseline keeps #311 and #312 visible. The queue's 27 settled decisions are constraints the new specification honours. | W3 |
| D6 | Standing permission for the LLM to open pull requests in the new repository | Yes. Every change is a pull request. | W0 |
| D7 | Whether the new repository adopts BCW-1's zero-warning lint rule for the RTL | Adopt it. The imported RTL already passes it. | P1 |

### 2.3 For the author during pass 2

These are proposed changes of meaning. Each goes through the design gate as
its own change (section 7):

- **The target rule.** CAPH 2.12 binds accelerators only, and the supervisor
  is target 0, not an accelerator. The rule is generalised from "an
  accelerator" to "a target", covering state, ordering, rejection and returned
  values. A target rejects only for properties of the request itself, and
  waits otherwise.
- **Revocation after stop.** A supervisor rule: an entry that an in-flight
  request holds is revoked only after the supervisor has stopped the request
  (cause 7). The re-executed request then fails at its first unit, before any
  progress it could measure.
- **Labelled security properties.** The security properties of RATH 4.1,
  RATH 4.2 and RATH 4.3 get labels and anchors. The timing invariant is stated
  as a rule.

## 3. The workflow

### 3.1 Goal and principles

The design's goals are optimised in order (RATH 1):

1. auditability;
2. cognitive burden, which replaces conceptual economy;
3. ultra-low interface latency;
4. throughput.

Auditability means every security property traces to a structural fact about
the hardware. It also means the hardware and operating system are small
enough for one engineer to read completely.

The workflow's goal follows from the first two:

> One literate source, from which the machine-checked artefacts and the
> human-readable documents are both generated, so that what a reader reads is
> exactly what the machine checks, and so that the burden of reading it is
> measured and kept down.

Principles:

- **The human validates; the machine verifies.** The human does not check
  proofs. The human checks that the rules and theorems say the right thing.
- **One source, many projections.** Every artefact is generated from one
  literate source, or checked against it (Knuth's literate programming,
  generalised from two outputs to many).
- **What you read is what is checked.** The reader's documents and the checked
  artefacts come from one parse of one source.
- **Every documentation rule is a script.** A rule about how the specification
  is written must be checkable by a program within the fast tier's budget.
  Otherwise it is dropped, or reduced to a part that is. Judgment is reserved
  for deciding whether a rule is right.
- **No new places to look.** Generated views appear inside existing documents,
  next to the rules they explain.
- **Integrate what belongs together.** A rule, its formal statement and its
  checks sit side by side (the split-attention effect of cognitive load
  theory).
- **Jargon stays where it is needed.** Terms from formal methods appear in the
  formal twins, not in the English rules.
- **Tool metadata stays out of the reader's way.** Anchors, stamps, attributes
  and check bindings exist for tools and the author. The reader edition hides
  them.
- **Ratchet, don't stall.** A new check starts from the violations that
  already exist and may only reduce them.
- **The human decides what the machine should be.** Any change that alters
  what the machine does goes to the author. The process detects such changes
  mechanically, rather than trusting an author, human or LLM, to notice.
- **The machine is never checked less than in BCW-1.**
- **Measures cost more than they look.** A new measure or check enters on
  probation, with a stated purpose and a review point, and leaves if it has
  found nothing real.
- **The tools are in the chain of trust.** They must be small, specified and
  checked.

### 3.2 Trees

| Tree | Holds | Form | Produces |
|---|---|---|---|
| `docs/` | The rules | Literate Markdown | System model, module models, RTL property jobs, parameters, verification manifest |
| `rtl/`, `tb/` | RTL and testbenches | Verilog, literate by reference | Themselves |
| `impl/` | How the built thing works | Literate Markdown, weaving in code from `rtl/` and, if chosen, the supervisor | Woven documents |
| `exp/` | What was tried and what it measured, the defect list, the migration ledger, and the process-health log | Plain Markdown | Nothing |

Generated output goes to `build/` and is never edited by hand.

**Literate by reference.** The RTL stays in Verilog. Timing closure, linting,
pin constraints and netlist names all work on the Verilog as written, and a
tangle step would put every one of those tools behind it.

- Each module, or block within a module, carries a comment citing the anchors
  of the rules it implements.
- The weaver pulls the cited blocks into the `impl/` documents, next to the
  prose that explains them.
- The implementation check reads the citations directly from the Verilog.

What is lost is Knuth's ideal of code in expository order. The supervisor
faces the same choice, and it is decided when the supervisor is first written.

### 3.3 Rule chunks

The source is Markdown, readable in a pull request without building.

- **A rule chunk** is one labelled rule, its anchor line, and the fenced blocks
  that belong to it. A chunk holds one rule: at most one "shall".
- **The seven labels** are REQUIREMENT, RATIONALE, PARAMETER, DEFINITION,
  TARGET, DISCUSSION and OPEN.
  - REQUIREMENT, PARAMETER and DEFINITION are **rules**.
  - RATIONALE and DISCUSSION are **argument**.
  - Unlabelled text is not normative.

A sketch. It is illustrative, and the syntax is settled when the tool is
built:

````markdown
**REQUIREMENT.** An access of *n* bytes at offset *o* shall address
base + *o* only if *o* + *n* is at most the bound.
{rule=caph.base-bound parent=prop.confinement}

```formal stamp=9c41e0
def base_bound(base, bound, o, n):   # bit-vectors of 24, 25, 32 and 3 bits
    ok = ULE(ZeroExt(2, o) + ZeroExt(31, n), ZeroExt(9, bound))
    return ok, base + Extract(23, 0, o)
```

```check kind=equiv module=bb_check mutant=mutants/bb-off-by-one.patch
map base->i_base bound->i_bound o->i_off n->i_len ok->o_ok addr->o_addr
```
````

The blocks:

- **`formal`** is the rule's **twin**: its formal statement, as a Python
  expression over z3, in the form `docs/formal/lifecycle.py` already uses. No
  new syntax is designed. A twin belongs to the system model, or is a module
  model (section 3.12).
- **`check`** is something that verifies a rule. It is written in the document
  of the subsystem that performs it. `verifies=` names the anchor of the rule
  it verifies, which may be in another document. `mutant=` names the patch
  that should make it fail (section 3.10). Its `kind` is one of these:

  | Kind | Meaning |
  |---|---|
  | `equiv` | An RTL module proved equivalent to its module model |
  | `rtl` | A property proved over the RTL with SymbiYosys |
  | `netlist` | A structural check that a path does not exist |
  | `static` | Arithmetic over parameters. It becomes a build-time assertion in the fast tier where its inputs are all parameters. |
  | `test` | A directed or simulation test |
  | `measure` | A measurement against a stated bound, such as the supervisor's 300 µs limit (SIPC 2.2) or the crypto engine's zero timing variance (CRYP 2.2) |
  | `audit` | An inspection of supervisor code against its catalogue row or rule |

- **`param`** is a parameter definition (section 3.4).
- Implementation code appears only in `impl/`, where it is written literately
  at all.

**Attributes.**

- Authored on every rule:
  - `parent`, naming the rule it supports. DEFINITIONs carry one too
    (section 3.13).
  - `impl=none`, on the few REQUIREMENTs in technical documents that no
    implementation implements. It is a deliberate claim.
- Authored on check blocks: `kind=`, `verifies=`, `module=`, `mutant=` and the
  port map.
- Everything else is derived:
  - a rule is **open** when an OPEN chunk names it as parent;
  - its leg, verification status, implementing code and history come from the
    parent chain, the check bindings, the citations in `rtl/` and `impl/`, and
    git.

**Anchors** are stable, unique and never reused, and a retired registry lists
removed ones. The reader edition hides them. They still appear in RTL
comments, commit trailers and the defect list, so their form must be readable.

A **review stamp** is a hash, recorded with a twin, of the English it was last
validated against. Changing it is part of a change the author approves
(section 3.15).

### 3.4 Parameters

- Every PARAMETER is defined once and tangled into each consumer:
  - a SystemVerilog package that the Verilog in `rtl/` includes;
  - constants for the formal models;
  - constants for the supervisor;
  - values substituted into the woven documents.
- Every `static` check whose inputs are all parameters becomes a build-time
  assertion in the fast tier. The first is the hazard inequality of CORE 2.3,
  *T* > *n* − *k*. The specification already has the pattern: the serial
  rate assertion fails synthesis rather than warns (SPER 3.2).
- The parameter source accepts TARGET values as inputs, such as the system
  clock (CORE 2.2). It marks every value derived from one, such as the serial
  divisor, so a changed target shows which parameters and assertions it
  touches.

### 3.5 Tangle, weave and history

**Tangling** produces, from `docs/`:

- the system model;
- the module models;
- the equivalence queries and SymbiYosys jobs;
- the parameter files;
- a verification manifest.

**Weaving** produces:

- **the reader edition:** the documents in their order, with twins collapsed
  beneath their rules, tool metadata hidden, and generated views in place;
- **section-5 tables,** generated from the checks written in each document,
  whichever document's rule they verify;
- **the `impl/` documents,** with the cited Verilog blocks in place.

The reader edition of a tagged release is archived with it. An audit edition,
with everything expanded, is deferred until a subsystem needs it.

**History comes from git.** Hand-kept changelogs and document versions exist
only to carry the reason for a change, and the commit already carries it.

- Every commit carries a *why* in a trailer. A commit hook checks it locally;
  the setup script sets `core.hooksPath` so that the hook runs in a fresh
  container. Continuous integration checks it again.
- A document's history is the commits that touch its chunks, with their *why*
  trailers.
- A commit that changes a review stamp names the rule's anchor in a trailer. A
  commit that raises a burden ceiling names the measure.
- Version numbers are kept only at tagged releases.

### 3.6 The tool

A small purpose-built tool. It is in the chain of trust, and the fast checks
need a parser that understands rule chunks.

- **One parser,** on a standard CommonMark library, producing one document tree
  that tangle and weave both work from.
- **An incremental dependency graph.** Every input is hashed and every check
  result cached, and continuous integration shares the cache. A check re-runs
  only when one of its inputs changes.
- **Failure messages** that name the rule, the location and the fix.
- **A check whose tool is missing fails.** It never skips.
- **A solver's timeout or "unknown" answer is a failure.**
- **Tangled files are read-only outputs.** There is no bidirectional
  synchronisation.
- **A watch mode,** built after W3, re-runs the touched fast checks when a
  source file is saved.

### 3.7 Tiers, and the definition of done

- **The fast tier** (`make check-fast`):
  - It holds the checks of section 3.8.
  - Its budget is 30 s for a full run over the whole repository, enforced
    locally. CI fails it only past 60 s, because a shared runner's timing
    varies.
  - Because the tool is incremental, a typical run re-checks only what
    changed.
- **The touched slow checks** (`make check-touched`) are the slow checks bound
  to the chunks and files a change touches, each with a timeout. An LLM runs
  them while editing RTL. No check is ever performed by reading.
- **The slow tier** (`make check`) holds everything (section 3.11).
- **Continuous integration** runs:
  - on every pull request: the fast tier, the touched slow checks through the
    shared cache, and the diffs of section 3.15;
  - nightly on the default branch: everything, uncached, including the
    mutation job;
  - at a phase gate: `make gate` and `make timing-sweep`.
- **Outside the tiers** are the scheduled supervisor audit and the sampled
  reading review (section 3.16). Neither blocks a merge.

**Definition of done** for a change, by a human or an LLM:

- the fast tier is green;
- the touched slow checks are green;
- the commit carries its *why*;
- the design gate has passed (section 3.15).

Continuous integration then runs, and the default branch accepts only merges
that pass.

### 3.8 The documentation requirements

These are the fast checks. Each is a script, and each is a ratchet
(section 3.10).

A **technical document** is one of documents 03 to 13, and 15.

A **rule sentence** is a sentence of a REQUIREMENT, PARAMETER or DEFINITION.

| Check | What the script does |
|---|---|
| Structure | Technical documents carry five section headings, in order: 1 Information and Purpose; 2 Normative Requirements and Rationale; 3 Structural and Interface Reference; 4 Operational and Execution Sequences; 5 Verification and Traceability |
| Labels | Every bold label is one of the seven; every REQUIREMENT contains "shall" |
| One rule per chunk | At most one "shall" per chunk |
| Argument budget | A rule-cluster (a subsection holding at least one rule, or carrying argument of its own) carries at most one RATIONALE or DISCUSSION block, of at most 40 words |
| Language | The linter's hard rules on rule sentences (section 3.9) |
| Vocabulary | In rule sentences only: no term from the "Never" column of the vocabulary table (section 3.9), except in a listed allowed phrase |
| Cross-references | Every citation resolves. No phrase that names no destination ("see above", "as mentioned", "the section below", "elsewhere in this document"). No `§` after an external standard's name. Citations of standards carry a year. |
| Restatement | No two rules are exact duplicates after normalisation. The redundancy query over twins is a touched slow check, not a fast check (sections 3.11 and 5.8). |
| Anchors | Every rule has an anchor. Anchors are unique and absent from the retired registry. |
| Trace upward | Every `parent` resolves. Chains are acyclic and end at a goal. Every security property and the scope rule are labelled statements with anchors. |
| Trace downward | Every REQUIREMENT has a check, or an OPEN chunk names it as parent. Applies to a document from the build phase that builds it. |
| Implementation | Every REQUIREMENT in a technical document is cited from `rtl/` or `impl/`, unless marked `impl=none`. Every citation resolves. Applies to a document from the build phase that builds it. |
| Twins | Every rule whose parent chain reaches a security property has a twin. No twin lacks a rule. |
| Formal checks | Every check VERI 1.2 requires to be proved has a module model and an `equiv` check |
| Supervisor rules | Every REQUIREMENT whose actor is the supervisor or the boot ROM has an `audit` check |
| Check placement | Every `verifies=` resolves |
| Review stamps | Each twin's stamp equals the hash of its rule's current English |
| Mutations | Every check bound to a rule in the argument map has a mutant patch stored beside it, and the patch applies |
| Parameter assertions | Every `static` check over parameters holds |
| Specification model | The system model finds no contradiction, unimplied claim or dead rule, within its bound |
| Reader edition | The reader edition holds only the block kinds on its allow-list (section 3.14) |
| Burden measures | Every measure of section 3.13 is within its document's ceiling |
| Exits | Every standing-exit count is within its ceiling (section 3.10) |
| Defects | Every open entry in the defect list cites an existing anchor |
| Probation | Every check or measure on probation whose review phase gate has passed has a recorded outcome |
| Machine-check fixture | Every machine check carried from BCW-1 is still defined, and the fixture holds its recorded output (section 6.2). The run that compares each check's output with the fixture is a slow check (section 3.11). |

The build plan's section 1 names which documents each phase builds. That
phase's start sets the baselines of Trace downward and Implementation for
those documents.

When the English of a rule changes, the tool's re-stamp command shows the old
sentence, the new sentence and the twin together. Re-reading the twin is the
easy path.

A lemma-graph check, and the proof manager it serves, are deferred until the
first sufficiency proof the system model cannot express.

### 3.9 Language, vocabulary, and rules reduced or removed

**Language.** The linter comes from the frozen repository,
`.claude/skills/asd-ste100/scripts/ste-lint.py`, and moves into the tool tree.

- Its hard rules block a change: semicolons, phrasal verbs, nominalisations,
  marketing adjectives, synonym rotation, and a cap of 25 words per sentence.
- Passive voice and the present perfect are advisory.
- The approved-word dictionary is dropped. It was never checked.

**Vocabulary.** In rule sentences, these words have one meaning each, and the
"Never" column is forbidden:

| Word | Means | Never |
|---|---|---|
| thread | One of the eight threads of the barrel core | a *context*; a software thread within a process |
| worker | Any thread other than thread 0 | a process, which is what a worker runs |
| accelerator | As CAPH 1.1 defines it; the supervisor is target 0, not an accelerator | a *controller*, except a media access controller or a host controller |
| handle | As CAPH 1.1 defines it | a *capability*, except when naming the capability-system tradition |
| process | A program image the supervisor loads onto a thread | a thread |
| turn | A thread's cycle in the rotation: thread *n* takes its turn on every cycle *C* with *C* mod 8 = *n*, whether or not it has work | a *slot* |
| region | As CAPH 1.1 defines it | a surface's extent |
| stage | One of the ten positions an instruction occupies as it moves down the pipeline | a slot or a turn |
| bank | As CORE 2.9 defines it | a thread; a memory bank |
| core | The one barrel datapath the eight threads share | an execution context, which is a thread |

**Rules reduced or removed.** The imported conventions document (CONV) holds
BCW-1's rules. Each is reduced to what a script checks, or removed:

| BCW-1 rule | Disposition |
|---|---|
| Conform to a tailored IEC/IEEE 82079-1 (CONV 1) | Removed; its conventions stay as far as section 3.8 checks them |
| The tree-placement test (CONV 1.0) | Removed as a rule; the directories remain |
| Every substantive statement starts with a label (CONV 4) | Removed; unlabelled text is already non-normative |
| The form of a performance figure, and where measurements belong (CONV 4) | Removed |
| Front matter and its class field (CONV 6) | Reduced to the identifier; everything else is derived |
| Changelogs, versions, and the *why* (CONV 6) | Replaced by commit trailers and git history (section 3.5) |
| Document before RTL, updated in the same commit (CONV 6) | Replaced by citation resolution, and by the design gate, which catches a change of meaning in either |
| No restatement of another document's rule (CONV 7) | The redundancy query over twins, and exact duplicates elsewhere |
| A repeated table is marked as a copy (CONV 7) | Removed; generated views make copies unnecessary |
| Simplified Technical English (CONV 8) | The linter, less the dictionary |
| A rewrite keeps "shall" and adds no count or actor (CONV 8) | Removed |
| One meaning per word; outside meanings marked (CONV 9) | Reduced to the vocabulary check in rule sentences |
| The mechanism census (CONV 10) | Replaced by the burden measures (section 3.13) |

**A known gap.** A change in implementation that alters behaviour without a
change to its rule is caught only where a check observes it. The semantic
diff's RTL part narrows this (section 3.15). A change that no check observes
still passes unseen.

### 3.10 Ratchets, exits and mutations

**Ratchets.**

- Every fast check starts with a baseline: the number of violations in the
  migrated content, per check and per document, stored as data, one line
  each.
- A count may fall but never rise.
- CI fails unless each committed baseline equals the computed count. The fast
  tier rewrites baselines locally, and CI never writes them.
- New content must be clean. A new chunk with a violation fails, even while old
  chunks carry the baseline.
- The fast tier prints every non-zero baseline, so the debt stays visible.
- Each phase gate names the baselines that must reach zero before the phase
  closes.

**Exits.** An exit is a legitimate way for a rule to pass a check it would
otherwise fail.

- **Standing exits** are counted, each with a ceiling:
  - `impl=none`, which satisfies Implementation;
  - an OPEN chunk naming the rule, which satisfies Trace downward;
  - an allowed phrase, which satisfies Vocabulary.
- **Events** have no ceiling, because their count only rises: a re-stamp, a
  change classed editorial, a raised ceiling. Each goes to the author through
  the design gate.
- **A parent change** that takes a rule out of a security property's chain is
  a design change. A script sees it, because the trusted reading base falls or
  a twin obligation disappears.

**Mutations are patches, not names.**

- Each check bound to a rule in the argument map has a mutant patch that
  should make it fail.
- A pull request runs the mutants of the checks it touches, and a fast check
  fails when a patch no longer applies.
- A nightly job runs every mutant and fails any that survives.
- Checks outside the argument map carry no mutation obligation.

### 3.11 The slow tier

The slow tier holds:

- equivalence of stateful checks;
- RTL properties, including the self-composition proofs;
- `static` checks that need more than parameters;
- netlist checks;
- simulation tests;
- measurements;
- the solver cross-checks;
- the semantic diff;
- nightly, the mutation job.

It also holds two checks that section 3.8 leaves out of the fast tier. These
are the redundancy query over twins (section 5.8), and the comparison of each
machine check's output with the fixture (section 6.2).

### 3.12 Formal layers

**Two formal languages.**

- Python over z3 holds the system model, the module models, and the
  equivalence of combinational checks.
- SymbiYosys holds everything sequential on RTL.
- Neither appears in the reader edition.

**The system model** grows from `docs/formal/lifecycle.py`.

- Its four queries:

  | Query | Role in the workflow |
  |---|---|
  | Contradictions | Joint satisfiability of the twins |
  | Unimplied claims | Sufficiency of the argument: a property that does not follow from its cited rules shows a missing rule or citation |
  | Redundancy | The Restatement check's query over twins, run with the touched slow checks |
  | Dead rules | A rule no scenario exercises, which is a vacuity warning |

- It found #309, the stop that lost the rest of a request, and the
  restatements #311 and #312.
- It grows as every twin of every rule the security argument depends on joins
  it. It is split by concern (the request lifecycle, addresses, and the
  schedule), each part holding the rules it cites.
- Four extensions are each added when the first proof that needs it arrives:
  - named lemmas with explicit citations, passing only the cited facts to the
    solver;
  - a dependency check, so that the argument map is itself verified;
  - standard encodings for induction, two-copy comparison and refinement;
  - vacuity checks on every proof's assumptions.
- General theorems such as Kahn's are cited, not proved. The model proves
  their premises for each specified service.
- **The supervisor is not itself a Kahn process.** It waits until any enabled
  status bit is set (SIPC 2.1), which is a multi-source wait. So that it
  implements each service as an independent blocking process is one `audit`
  leaf per service-catalogue row.

**Module models and equivalence.** VERI 1.2 requires proof for four checks:

- the handle check (CAPH 2.6);
- the base-and-bound check (CAPH 2.8);
- the supervisor-part check and the resume check (CAPH 2.9).

None has a model or RTL yet. Each module model is written from its English
rule, in the rule's chunk as its twin, before any RTL exists. Then the RTL is
written, and then equivalence is proved:

- **A combinational check:** the RTL module is imported once through Yosys's
  `write_smt2` as a function, and equivalence with the model is one z3 query.
- **A check with state,** such as the resume check: a SymbiYosys job with a
  generated harness.

Three points need care:

- the port mapping, kept trivial with widths from the parameter source;
- preconditions, each recorded as an obligation on the module that supplies
  the input;
- wiring, which equivalence does not cover and netlist checks do (for
  example, suppression ahead of any buffer, CAPH 2.8).

The rest of the hardware trusted base (CAPH 1.2) keeps the verification the
specification gives it: the accelerators' per-unit entry copies, coherence at
resume, the rotation counter, and the reset path.

**RTL properties with SymbiYosys.** SymbiYosys runs from the pinned
yowasp-yosys, which bundles it. A smoke test must pass a good property and
fail a broken one before any other result is trusted. Checks of kind `rtl`,
and stateful `equiv` checks, tangle to SymbiYosys jobs with generated
assertion harnesses. There is no bridge from Python to transition systems: it
would re-implement the unrolling, induction and witness traces that
yosys-smtbmc already provides.

**Self-composition for Leg 1** (subject to D4). Two copies of the design are
constrained to agree on everything one thread owns and on its inputs, with an
assertion that the thread's trace is identical in both. The plan:

1. The core alone. Its fetch, data and device ports are outside it, so memory
   is cut to per-thread oracles (an assumption of section 4.5).
2. Bank switching disabled, and the divider stubbed before it is included.
3. The harness of section 5.11, starting both copies from one power-up
   state.
4. Bounded checking to the depth the slow tier affords.
5. Then k-induction, with a relational invariant over the watched thread's
   register bank, its program counter and bank entries, and the pipeline
   registers holding its instructions.
6. Before trusting a pass, plant a leak (give an unused turn to the next thread
   with work) and confirm the check fails.

For Leg 2, a self-composition proof that varies the stop points between the
two copies can be added once the targets exist.

**The golden model** is the frozen repository's phase-0 simulator, checked
against the official RISC-V ISA tests. The RISC-V Sail model is not used,
though it could later serve as an independent cross-check.

**The supervisor.** Each service function is bound to its catalogue row by a
citation. It is audited against every rule whose actor is the supervisor.
Those include the rules section 4.5 depends on:

- quotas;
- revocation after stop;
- rejection only for the request's own properties;
- channel-only event delivery.

Verification tools for memory-safe languages could later prove specific
catalogue properties; that is optional.

**Trust in the solvers.** Run the same SymbiYosys job with two engines, and the
same z3 query on a second solver, and fail if they disagree. Proof
certificates are not required. If one is ever wanted for a combinational
check, bit-blast it to CNF and check a DRAT proof.

**The toolchain** is defined once, in `tools/setup.sh`, and used by both the
LLM's environment and continuous integration. Its pins are in section 6.1.
Tools an environment cannot fetch are vendored.

### 3.13 Cognitive burden

RATH 1.2 is rewritten in pass 2, as drafted here:

> **REQUIREMENT.** The cognitive burden of the design shall be minimised,
> counted across hardware, supervisor and the discipline imposed on user
> software.
>
> **DEFINITION.** The **cognitive burden** is what a reader must hold in mind
> to build, verify or operate the machine. The measures of the conventions
> document count it.

The goal keeps its place, second after auditability. The two reinforce each
other: the trusted reading base below is the size of what one engineer must
read completely, which is auditability's own test.

**Measures.** Each is a count computed by a fast-tier script:

| Measure | What the script counts | Why it is burden |
|---|---|---|
| Mechanisms | DEFINITIONs whose `parent` is the cognitive-burden goal, per document | Each is an idea a reader must learn |
| Trusted reading base | Words in the rule chunks whose parent chain reaches a security property, per document | What one engineer must read completely to trust the security argument |
| Author burden | Fast checks, check kinds and authored attributes, counted from the tool's own anchored rules | What the author and an LLM must hold in mind every day |

- **Ceilings.** Each measure has a ceiling, held as a parameter and set per
  document when that document's rules are written.
  - The fast tier fails if a count exceeds its ceiling.
  - Raising a ceiling needs a commit trailer naming the measure and what the
    increase buys. Decreases need nothing.
- **Covered elsewhere.** Rule length is capped by the linter's 25 words per
  sentence. The workflow's additions to the reader edition are limited by its
  allow-list.
- **Candidate measures,** recorded but not adopted:
  - the number of terms a reader must learn;
  - forward references in SYST 2's reading order.

  Each is added only when a real problem shows it is needed, and then on
  probation.
- **Validation.** The measures are proxies. The comprehension exercise
  (section 3.16) validates them occasionally, and gates nothing.

**The census, carried over.** BCW-1's census rules decide what counts as a
mechanism:

- a device is not one;
- an instance of a mechanism is not a second one;
- a decision about where something runs is not one.

They are applied once, when a DEFINITION is written. Every DEFINITION names a
parent: either the cognitive-burden goal, meaning "this introduces a
mechanism", or another parent, meaning "this names a term, a device or an
instance". The choice shows in the diff under review, and misclassification
is visible there. Removing signals lowers the mechanism count by one. Whether
quotas add one is the author's classification to make.

The specification changes this needs are listed in section 7.

### 3.14 Presentation

Every view is generated and woven into an existing document.

- **The argument map, inside the rationale.** Each security property's subtree
  appears beneath its section of RATH 4, collapsed: property, legs, rules,
  twins, checks, and assumptions as explicit leaves.
  - Checks are named in plain words (proof, structural check, test,
    measurement, inspection).
  - The scope rule of section 4.1 is the first assumption leaf of every timing
    subtree.
- **The schedule table, beside the schedule rule** (RATH 4.4). It is generated
  from the parameters, and is a reservation table for one rotation. It shows
  which thread owns each pipeline stage in each cycle, which thread or
  accelerator owns each pool phase, and the reserved positions on external
  memory. Every cell has one owner, and the pattern does not depend on demand.
- **The service catalogue, in place of the interface table** (CAPH 3.4). One
  row per accelerator operation and per supervisor service, including
  allocation within quota and channel receive. It adds four columns in plain
  words:
  - *waits until done*;
  - *result depends only on*;
  - *result never depends on*;
  - *rejects only when*.

  The last three are generated from the target rule of section 2.3.
- **Worked examples** are deferred until the argument's top is written. They
  are traces of concrete requests, generated by the golden model and the system
  model, and placed in section 4 of each document.
- **What the reader must learn.** A reader of the reader edition meets five
  additions:
  - a twin beneath a rule;
  - the three legs;
  - the argument map;
  - the schedule table;
  - the service catalogue's four columns.

  The reader edition's allow-list enforces this.
- **Declined:**
  - separate requirements specifications in the manner of ISO/IEC/IEEE
    29148:2018;
  - a separate learning path;
  - request sheets;
  - flowchart notations such as DRAKON and statecharts.

**ISO/IEC/IEEE 29148:2018 is used selectively.** Conformance is not required.
The decision is recorded in the decisions record in pass 2.

- **Taken,** because it costs the reader nothing or reduces burden:
  - stable identifiers, never reused;
  - tracing to a need and to verification;
  - the recursive view of requirement levels, which shapes the argument map;
  - consistency of the rule set;
  - avoiding vague wording and unversioned references;
  - the distinction between verification and validation;
  - a baseline per release.
- **Declined,** because it would add burden:
  - separate stakeholder, system and software requirements specifications;
  - displayed requirement attributes;
  - a rationale per requirement;
  - a second taxonomy of verification methods;
  - the discouragement of negative statements, since the design's most
    important rules are absences that netlist checks verify;
  - a conformance claim.

### 3.15 The loop and the design gate

**The loop, for every change:**

1. Edit the source: the rule, its twin and its checks together, and any
   Verilog that implements it.
2. Run `make check-fast`. Also run `make check-touched` if the change touches
   anything a slow check covers.
3. If a review stamp fails, re-read the twin in the re-stamp view.
4. Commit, with a *why* trailer. Each pull request holds one change of meaning.
5. Open a pull request. Continuous integration runs, and posts two diffs: the
   woven reader-edition diff and the semantic diff.
6. If the design gate routes the change to the author, wait for the author's
   approval.
7. Merge when the checks pass. The merge is by rebase or by merge commit,
   never squash, so every commit keeps its *why* trailer. The default branch is
   protected: nobody builds on a red base.

An LLM follows the same loop. It never performs a check by reading, and it
never merges, approves, or adds an approval label.

**What goes to the author.**

- Every change to a rule's English, a twin, a PARAMETER or a check's
  definition. Re-stamping a twin is part of the change the author approves.
- Every change the semantic diff reports.
- Every change to the tool, to `tools/` or to a CI workflow. These decide what
  the gate sees, so a pull request that changes them cannot pass the gate
  without the author.

A change is **editorial** when its normalised text is unchanged, or when both
of the model's semantic-diff queries are unsatisfiable. This is computed,
never marked by hand.

**The semantic diff** has three parts:

- **The model.** Two queries over traces from reset, within the model's
  bound. One asks for a trace that the base rules allow and the head rules
  forbid. The other asks for the reverse. Either answer is a design change,
  shown with its trace.
- **The RTL.** The per-cycle port traces of the regression programs, base
  against head. The core is cycle-exact, so any difference is a change of
  behaviour.
- **The service catalogue.** A text diff of the generated cells.

It does not see behaviour beyond the model's bound, or RTL behaviour that no
regression program exercises.

**Approval.**

- A required status check, `design-gate`, passes a pull request in two cases:
  - nothing in it goes to the author;
  - it carries an approval label that the author's GitHub login added, not
    through an app, after the head commit.
- The check records a hash of what it accepted: the routed changes and the
  semantic diff. A push that changes either cancels the approval.
- The check runs from the default branch's copy of the tool and of its
  workflow, never from the pull request's copy. It reads the pull request's
  changes as data. A workflow triggered by `pull_request` runs the pull
  request's own copy, so the gate cannot use that trigger.

**A known gap.** The semantic diff runs the head's twins, which are Python. A
twin can therefore affect the verdict that makes its own change editorial. The
routing above does not close this gap.

**Where the human judges.**

- the design gate, on every change of meaning;
- the scheduled supervisor audit;
- the sampled reading review;
- the occasional comprehension exercise.

None of these is a documentation check, and only the design gate blocks a
merge.

### 3.16 Defects, reading, and changing the process

**One defect list,** a file in `exp/`. A file, rather than an issue tracker, so
that the fast tier can check it offline and an LLM in any environment can
read and write it.

- Each entry has a stable number, a severity, and the anchors it concerns.
  Migrated entries record their BCW-1 queue number.
- A fast check requires every open entry to cite an existing anchor.
- A subsystem's phase closes only when it has no open severity-1 entry.
- A fault noticed while doing other work joins the list. It is not fixed in
  passing.

**Reading is bounded and sampled.** At the end of each phase, a fixed number of
chunks, chosen at random, is read once, and the findings go to the list. The
review never blocks. Unbounded sweeps found faults far faster than anything
fixed them: of BCW-1's 315 queue items, four were fixed.

**Changing the process.** The process changes through the same loop as the
specification.

- The tool's rules and the conventions change by commit, with a *why*. Each
  such change goes to the author (section 3.15).
- A new check or measure enters **on probation**, as a ratchet, with a stated
  purpose and a named phase gate as its review point. If it has found nothing
  real by then, it is removed. The Probation check fails when that gate passes
  with no recorded outcome.
- **Process health** is recorded in `exp/`:
  - time to a green fast tier;
  - continuous-integration duration;
  - red runs per change;
  - the open-defect trend;
  - the exit counts;
  - model time against rule count.

**Measuring comprehension.** SYST 2 sets the specification's own test: a
reader of the overview and rationale should be able to predict most of what
the numbered documents say. Run it occasionally:

1. Write concrete questions.
2. Answer them from the overview, the rationale and the argument map alone.
3. Check the answers against the specification.

Record the results in `exp/`. This validates the burden measures, and gates
nothing.

### 3.17 Mutations

Each row names a mutation and the check that should kill it. The rows include
mutations of the process itself. They are the tool's own tests and the
argument map's stored mutants.

| Mutation | Should fail |
|---|---|
| Give an unused turn to the next thread with work | Leg 1 proof; rotation test |
| Let pool phase allocation respond to demand | Leg 1 proof; phase-selector netlist check |
| Let the divider serve in any free turn | Leg 1 proof; divide-neighbour test |
| Stall the pipeline on a pool conflict | Leg 1 proof |
| Expose a free-running counter in a worker-readable register | Time-source netlist check |
| Write the program counter past the request on a stop with work remaining (#309) | The system model's stop-and-resume scenarios |
| Let an accelerator return a queue depth or completion count | Target-rule check; catalogue audit |
| Let storage reject a page read while an erase runs | Catalogue audit (*rejects only when*) |
| Let allocation fail because another process holds the resource | Quota rule; catalogue audit |
| Let a channel receive return "empty", or merge sources by arrival | Catalogue audit |
| Deliver an event other than by channel message | Supervisor audit |
| Revoke an entry while a request holds it | Supervisor audit |
| Introduce an off-by-one in the RTL bound comparison | Base-and-bound equivalence |
| Add contradictory assumptions to a proof | Vacuity check |
| Put two rules in one chunk | One rule per chunk |
| Add a mechanism without raising its ceiling | Burden measures |
| Change a rule's English without re-stamping its twin | Review stamps |
| Add a rule naming the supervisor as actor, with no audit | Supervisor rules |
| Delete a check bound to a rule the argument map uses | Trace downward; the map shows an unverified leaf |
| Change a rule's meaning and its twin together | Design gate: the semantic diff is not empty |
| Change an untwinned rule's English | Design gate: the change is routed to the author |
| Change the gate's routing code in the pull request that it judges | Design gate: the change is routed to the author |
| Add the approval label through the LLM's GitHub tools | Design gate: the label came through an app |
| Add a violation to a check with a non-zero baseline | Ratchet |
| Add a standing exit beyond its ceiling | Exits |
| Leave a probationary check past its review phase gate | Probation |
| Drop a machine check carried from BCW-1 | Machine-check fixture |
| Change the Verilog in the citation commit of pass 1 | The comments-only verification of section 6.2 |
| Leave a BCW-1 identifier in a BCW-2 rule, or a BCW-2 identifier that does not resolve | Cross-references |
| Uninstall the language linter | Language: a missing tool fails |

## 4. The security argument the workflow organises

The argument map (section 3.14) is built from this section. Its specification
changes are made in pass 2.

### 4.1 Scope

**Decided by the author:** the timing invariant holds between processes with
no external time reference. External time references are the operating
system's concern, not the hardware's.

An **external time reference** is anything from outside the machine that lets
a process measure real time.

- It may be explicit. A hostile network peer can put timestamps in its
  replies, and value purity (section 4.2) allows this, because the reply
  arrives on an authorised stream.
- It may be implicit: which frames the network dropped (ETHR 2.4, #13), or
  which serial bytes were discarded (SPER 2.7).

With such a reference, a process can time its own suspensions, which other
workers' load can change (RATH 4.4). The example that matters most: the
supervisor routes every keystroke (HIDV 2.1), so a compromised network stack
with a cooperating server could recover keystroke timing.

The rationale states this scope as a labelled rule, so that it heads the
argument map as an assumption rather than being implied. Mitigations are
supervisor policy and belong in the supervisor's rules. Examples are not
granting one process both a network handle and keyboard focus, and pacing a
network-facing process's service. The hardware argument does not depend on
them.

### 4.2 Three legs

Fixed rotation makes a worker's instruction count track elapsed cycles
(RATH 4.5). A running worker therefore has a clock: its own instruction count.

Within the scope of section 4.1, the timing invariant ("no protection domain
can alter the observed latency of an operation in any other protection
domain") rests on three legs. Each is necessary.

1. **Schedule independence.** While a worker runs, its cycle-indexed progress
   is independent of every other thread. Its instruction-count clock measures
   only itself.
2. **Request atomicity.** A request is one instruction in logical time, the
   process's own instruction count. However long it takes, however many units
   it is split into, and however often the supervisor stops and resumes it,
   the process resumes into the state an uninterrupted request would have
   produced.
   - Registers are not stable while a request is in flight: a target writes the
     argument registers as it works (CAPH 2.9).
   - What holds instead is that the stop leaves the program counter on the
     request, and the re-executed request presents the remaining part.
3. **Value purity.** Every value a process receives is a function only of its
   own request history and the value streams its handles authorise it to read.
   It is never a function of real time, load, or other workers' activity.

A fourth property, **state separation**, is the storage-channel counterpart,
and the subject of the confinement argument in CAPH.

### 4.3 How each leg is established

- **Schedule independence** follows from:
  - fixed rotation, with no stalls or replays;
  - the divider serving in the thread's own turns;
  - static phase allocation;
  - a fixed clock.

  Netlist checks and cycle-identical tests verify it (CORE 5, MEMC 5). The
  self-composition proof of section 3.12 is added on the RTL.
- **Request atomicity** is established at two levels.
  - In the specification: the system model's three stop-and-resume scenarios
    confirm that a stop and a resume leave the worker as an uninterrupted
    request would.
  - In the RTL: per-target directed tests (CAPH 5), and later a
    self-composition proof that varies the stop points.
- **Value purity** follows from making every request interface Kahn-pure (Kahn,
  1974). A network of such processes is determinate. A Kahn-pure interface
  has these properties:
  - reads block on a named resource until the data exists;
  - reads return exactly what was requested;
  - there is no emptiness test, multi-source wait or timeout;
  - bounded writes block;
  - merges follow fixed rules, never arrival order.

### 4.4 Risks, and how each is disposed of

**Decided by the author:**

1. **Signals are removed.** A signal suspended a worker and redirected it to a
   handler (SIPC 4.2), at a point set by real time and visible to the process
   in its own state. Delivering it at the next request does not help, because
   which request is next depends on when the signal arrived. Every event now
   arrives as a message on a channel, taken by a blocking receive at a point in
   the process's own code. The consequences are accepted knowingly:
   - There is no cooperative cancellation in the middle of a computation. A
     process that wants to be cancellable works in chunks and receives between
     them. Forced termination is unaffected, because suspend and reset are
     wires, not requests (SIPC 3.1).
   - There is no polling, because checking whether a message is waiting would
     be an emptiness test.
   - There is no merging by arrival order. A process receives on a named
     channel with one source, or from a merge whose order follows a fixed rule.
     Arrival order from sources inside the machine reflects their real-time
     progress, which other processes' load can change. Events from outside the
     machine, such as keystrokes, fall under section 4.1.

   This removes a mechanism, and closes #52 and #54.
2. **Allocation is by static quota.** A request for a region, bank, table
   space, tile, audio stream, channel, storage extent or external-memory extent
   could fail because another process holds the resource. That failure would
   reveal the other process's activity.
   - At creation, each process receives a fixed quota of each allocatable
     resource. A request within the quota succeeds, and one beyond it fails.
     Either outcome depends only on the process's own history.
   - Creation itself can fail when a pool is exhausted. Only the process asking
     for the creation sees that, and the supervisor's creation policy governs
     it.
   - Region growth by reallocate-and-copy (SIPC 2.7) is an allocation within
     the quota like any other.
3. **External time references are out of scope** for the hardware argument
   (section 4.1).

**Proposed, for the author (section 2.3):**

4. **Rejections and results depend only on the request.** This is the target
   rule. Two examples show why it matters:
   - rejection: what another worker's page read receives while the
     supervisor's erase runs is not specified (STOR 2.2);
   - returned values: RATH 4.5 forbids publishing time-varying state into
     memory a worker can read, but not returning it in registers.
5. **Revocation waits for in-flight requests.** A revoked request faults, and
   its argument registers show how far it got, which is fixed by when the
   revocation happened (CAPH 2.5). The supervisor rule of section 2.3 closes
   this.

**Still open in the specification:**

6. **Termination as seen by peers.** A terminated process's channel output ends
   at a point set by when it was reset. Where termination is user-initiated,
   it is an external time reference. Where one process can cause another's
   termination, it is inside the machine and needs a rule.
7. **Channel semantics** (SIPC 2.8) must meet item 1's constraints: blocking
   receive on a named channel, no emptiness test, fixed-rule merge.
8. **Network receive with no frame queued** should block (ETHR 2.3).
9. **Absolute time** remains OPEN (RATH 4.5). Under section 4.1 it is an
   external time reference, so granting it is a matter of supervisor policy.
10. **Fault repair** must depend on the request and policy, not on the
    supervisor's timing (SIPC 4.2).

**Removed from the list:** audio stream time through an underrun (AUDP 2.6).
Nothing reports it to a worker. It is output timing, not a value a process
receives.

**Checked and sound:**

- Fetch that one tile leaves unused passes to later tiles, and strokes dropped
  on overrun never touch worker state (GRPH 2.6). Both affect only the display.
- The audio and display rules that resume a worker once an accelerator has
  finished with an extent or a stream (AUDP 2.2, GRPH 2.5) pace the worker by a
  real clock, but only through suspensions.

### 4.5 Composition and assumptions

Within the scope of section 4.1, the three legs together imply that each
process's observable behaviour, indexed by its own logical time, is determined
by its initial state and the values on its authorised inputs. This implies the
timing invariant and is stronger than it. With state separation, the only
information flows between processes are those the handle tables authorise.

The implication rests on assumptions. Each is a leaf of the argument map, and
each is either made true by a rule or recorded as residual:

| Assumption | Made true by |
|---|---|
| No external time reference reaches the process | The scope rule; supervisor policy beyond it |
| No entry is revoked while a request holds it | The revocation rule (section 2.3), audited |
| No target rejects or returns anything outside the request's own properties | The target rule (section 2.3) |
| Allocation succeeds or fails on quota alone | The quota rule, audited |
| The supervisor implements each service as an independent blocking process | One `audit` leaf per catalogue row |
| Memory serves each thread as a fixed-latency oracle | The pool's phase schedule (MEMC 2.2), assumed until the pool is proved |
| Block RAM and DSP cells behave as their behavioural models | Assumed. Yosys models these primitives as empty stubs, so proofs cover the behavioural register file and multiplier; only the board run covers the mapped cells. |
| Every unit ends within one display frame | The one-frame bound of CAPH 2.5, a real-time bound inside a safety argument, verified by simulation |

The composition still needs a careful formal statement for a changing
authorisation policy: grants, revocation and quotas. That part is uncertain.

Physical side channels are out of scope (RATH 2). The crypto engine's
constant-time rule guards key-dependent timing against outside observers
(CRYP 2.2).

## 5. The less obvious choices, with their evidence

D2 asks the author to confirm these eleven choices. Each names the
alternative it replaces.

The measurements below used Python 3.11, z3-solver 5.1.0.0, yices_solver
2.6.5.post24 (Yices 2.6.5), yowasp-yosys 0.69.0.0.post1233 and the SymbiYosys
it bundles. They ran on Ubuntu 24.04 in a Claude Code cloud container on
24 September 2026. The model was the frozen `docs/formal/lifecycle.py`,
unmodified on disk.

### 5.1 A1: the semantic diff compares meanings

- **Choice:** the semantic diff of section 3.15.
- **Alternative:** compare only the verdicts of checks.

**Evidence.** Only a change that keeps every check green can merge, and such a
change alters no verdict, whatever it does to the meaning.

- The stop rule's formula was changed from cause 7 to cause 5. Every scenario,
  claim and query kept its verdict, so a verdict-only gate would not fire.
- The meaning queries found a trace in each direction, in 0.6 s.
- For a rewrite that kept the meaning (`Implies(a, And(b, c))` split into two
  implications), both queries were unsatisfiable, in 0.5 s.
- The whole model ran in 7.8 s: scenarios 3.3 s, triggers 0.5 s, redundancy
  3.2 s.

### 5.2 A2: what goes to the author

- **Choice:** every change to a rule's English, a twin, a PARAMETER or a
  check's definition goes to the author. Editorial status is computed
  (section 3.15). The mutants of touched checks run in the pull request.
- **Alternative:** only changes to untwinned rules and parameters go to the
  author, unless the author marks them editorial.

**Evidence.**

- A rule whose English changes while its twin does not produces an empty
  semantic diff. Whoever runs the re-stamp command, usually the LLM, then
  refreshes the stamp, and the match between English and twin is never
  validated by the author.
- A weakened check stays green on both sides of a change.

### 5.3 A3: approval that cannot be forged

- **Choice:** the `design-gate` check of section 3.15.
- **Alternative:** any approval label.

**Evidence.**

- GitHub does not let a pull request's author approve it.
- The LLM's GitHub tools can add labels, possibly under the author's account.
  W3 tests whether GitHub records the app on such a label (section 6.4).
- A label that survives later pushes approves changes the author never saw.

### 5.4 A4: the order of setup

- **Choice:** the phases of section 6: the workflow's checks that need no
  parents or RTL (W2), then the loop and the gate (W3), then the argument's top
  (P1), then the request-lifecycle slice (P2).
- **Alternative:** bring the slice to zero before the loop exists.

**Evidence.** That alternative cannot be met:

- The model's four findings (#296, #310, #311, #312) are all in the slice, and
  clearing them changes meaning.
- Trace upward, twins, the trusted reading base and the mechanism count need
  parents, and parents need the goals and properties written later.
- Of the slice's ten sections, only the three in CORE are built
  (section 6.6).

### 5.5 A5: downward checks follow the build plan

- **Choice:** Trace downward and Implementation apply to a document from the
  build phase that builds it (section 3.8).
- **Alternative:** apply them to every document from the start.

**Evidence.** 235 of the 367 "shall"s are in documents 04 to 13. Apart from
phase 2's display pieces and the part of the supervisor port the core already
has, their hardware is not built. A new rule there could pass only through
`impl=none` or an OPEN, and then that exit would say something false.

### 5.6 A6: exits

- **Choice:** ceilings for standing exits only, events to the author, and
  parent changes judged by a script (section 3.10).
- **Alternative:** ceilings for all exits, including "a parent chosen away
  from a security property".

**Evidence.**

- The count of an event only rises, so its ceiling would be raised routinely.
- No script sees the parent that was not chosen.

### 5.7 A7: probation ends at a phase gate

- **Choice:** a probationary check is reviewed at a named phase gate.
- **Alternative:** a calendar date.

**Evidence.** A check that fails when a date passes turns the default branch
red with no commit, and the same commit passes one day and fails the next.

### 5.8 A8: the model within the fast-tier budget

- **Choice:** the model split by concern, redundancy with the touched slow
  checks, and the budget enforced locally, with CI failing only past 60 s.
- **Alternative:** the whole model in the fast tier, with the budget timed in
  CI.

**Evidence.**

- Every query reads every rule, so the cache cannot skip part of the model when
  a twin changes.
- Redundancy grows roughly with the square of the rule count. It took 3.2 s of
  the 7.8 s at 35 rules.

### 5.9 A9: ratchet baselines

- **Choice:** CI requires each committed baseline to equal the computed count.
- **Alternative:** it requires only that the count not exceed the baseline.

**Evidence.** With the alternative, a pull request that lowers a count without
committing the lower baseline leaves room that the next pull request can
spend.

### 5.10 A10: the machine's verification carries over, and BCW-1's convention checks do not

- **Choice:**
  - These run in the new repository from W1 and must pass:
    - the 28 machine checks of `make check`;
    - `make gate`'s three further checks and the bitstream;
    - `make formal`'s smoke test.

    Each is compared by output, not by exit status alone.
  - BCW-1's four convention checks (`check-ste`, `check-xref`,
    `check-argument`, `check-lint`) do not run as they stand.
    - The documentation requirements of section 3.8 replace the first three.
    - D7 decides the fourth.
- **Alternative:** carry all of BCW-1's checks.

**Evidence.** A check can pass while checking nothing. `docs/ste_check.sh`
exits 0, printing "ste-lint.py not installed; skipping", when its linter
under `.claude/skills/` is absent. A copy of `docs/` without `.claude/skills/`
passes the language check while reading nothing.

### 5.11 A11: the Leg 1 proof harness and engine

- **Choice:**
  - Yices is the primary engine, and z3 the cross-check.
  - Both copies start from one power-up state.
  - k-induction is the proof method, with bounded checking only to the depth
    the slow tier affords.
- **Alternative:** z3 as the engine, with bounded checking to three rotations.

**Engine availability without GitHub access:**

- Yices installs from PyPI; `yices_solver` ships `yices-smt2`.
- Bitwuzla and cvc5 are on PyPI as Python bindings only. The Ubuntu 24.04
  archive has a cvc5 1.1.2 command-line tool.
- ABC is not available. YoWASP 0.69 has no standalone ABC, and the archive has
  none.

**The probe.** It ran two copies of `bcw_core`, with thread 1 watched. Each
copy exposed stage 7's valid and load flags, the write-back's enable, address
and data, and the run bits. Stage *k* holds thread `rot - (k - 1)`, so:

| Stage | Signal | Constrained equal when it is thread 1's | Asserted equal |
|---|---|---|---|
| 1 | Fetch address | | yes |
| 2 | Fetched word | yes | |
| 5 | `ECALL` and illegal-instruction outputs | | yes |
| 7 | Data address, byte enables, write data, device write, issue pattern | | yes |
| 8 | Load data | yes | |
| 9 | Device read data | yes | |
| 10 | Register write | | yes |

Thread 1's run bit was asserted equal on every cycle. The supervisor port was
constrained to treat thread 1 identically in both copies.

**Results:**

| Run | Engine | Result | Time |
|---|---|---|---|
| Planted leak: thread 1's fetch address depends on whether thread 2 runs | z3 | caught at step 2 | 2 min 43 s |
| Planted leak | Yices | caught at step 2 | 4 s |
| Clean, each copy with its own power-up state | z3 | steps 0 to 5 in 2 min 19 s, no answer at step 6 after 8 min | |
| Clean, each copy with its own power-up state | Yices | failed at step 8 | 20 s |
| Clean, one power-up state, depth 10 | Yices | pass | 72 s |
| Vacuity cover: thread 1 runs and writes back | Yices | reached at step 11 | 5 s |
| Clean, one power-up state, depth 34 | Yices | steps 0 to 15 pass, step 16 unfinished at the 40 min limit | |

**The failure at step 8** is a gap in the harness, not a leak.

- The write-back stage's valid and write-enable flip-flops, `p10_v` and
  `p10_we` in `rtl/bcw_core.v`, have no initial value.
- During the reset cycle, each copy wrote a different garbage value into
  thread 1's bank. Thread 1's first store read it.
- On the FPGA, flip-flops start at zero after configuration, so the hardware
  does not do this.
- The harness therefore starts both copies from one power-up state, with
  `setundef -undriven -zero -init` after `prep`. This models the FPGA's
  power-up. It also resolves the RTL's undefined values to zero in both copies.
- The synthesised resolution is covered by `check-core-gate`, not by the proof.
- On an ASIC, whether that first write should be suppressed goes into the
  defect list at W3, for build-plan phase 8.

**Depth.** Bounded checking cannot reach three rotations, because the time per
step roughly doubles. Steps 0 to 11 took under 6 min, and step 15 alone took
about 17 min.

## 6. Phases

### 6.1 W0: repository, toolchain, continuous integration

The author:

- Creates the repository (D1).
- Gives the Claude GitHub App access to it:
  <https://github.com/apps/claude/installations/select_target>.
- Tags the frozen repository's final commit `bcw1-final`, and archives
  `hedj/bcw`.
- Gives the new repository its own Claude Code environment, whose setup script
  runs the repository's `tools/setup.sh`.
  - Network access needs PyPI and the Ubuntu archive, and github.com only if D4
    wants ABC.
  - Access levels are described at
    <https://code.claude.com/docs/en/claude-code-on-the-web>.
- Gives that environment read access to `hedj/bcw`. The LLM imports from it
  in W0 and W1.
- Adds a ruleset on the default branch:
  - the CI checks required, and `design-gate` required from W3;
  - branches up to date before merging;
  - rebase and merge-commit merges only.

The LLM:

- Writes `tools/setup.sh`, which pins and installs:
  - from apt: Verilator 5.020, Icarus Verilog 12.0 and clang 18;
  - from pip: `yowasp-yosys==0.69.0.0.post1233`,
    `yowasp-nextpnr-ecp5==0.11.1.0.post826` (per D3, which also provides
    `yowasp-ecppack`), `z3-solver==5.1.0.0` and `yices_solver==2.6.5.post24`.

  It also sets `core.hooksPath` and prints the version banner.
- Imports `formal/` from `bcw1-final`, byte for byte, ahead of the rest of the
  tree. The formal smoke test lives there, and W0 needs it. W1 imports
  everything else.
- Writes a CI workflow that runs `tools/setup.sh` on `ubuntu-24.04`, then the
  banner and the formal smoke test.
- Writes an interim `CLAUDE.md`. It holds only what the migration needs:
  - follow this plan;
  - pull requests only, and the LLM never merges, approves or adds an approval
    label;
  - no change of meaning before W3 is done;
  - a solver's timeout or "unknown" is a failure;
  - the YoWASP tools cannot reach `/tmp`, so scratch files go in an ignored
    directory inside the repository.

  It copies nothing from the BCW-1 repository's `CLAUDE.md`. The `CLAUDE.md`
  of section 6.5 replaces it.
- Commits this plan.

Done when:

- the banner is identical in the Claude Code environment and in CI;
- the smoke test's good task passes and its bad task fails, in CI;
- a pull request that breaks the smoke test is blocked.

### 6.2 W1: pass 1, the mechanical import

Converting a rule and changing its meaning in one step would make the diff a
new file, so no change of meaning would be visible in review. The migration
therefore has two passes. Pass 1 is mechanical, by script. Pass 2 holds every
change of meaning, each through the loop.

1. Import the frozen tree at `bcw1-final`: `docs/` without its changelogs,
   `rtl/`, `tb/`, `impl/`, `exp/`, `mk/`, `phase0/`, `Makefile` and
   `README.md`. W0 already imported `formal/`.
   - `.claude/` stays behind. Its review queue migrates in W3, and its language
     linter moves into the tool tree in W2.
2. The rename script changes `DOC-BCW1-` to `DOC-BCW2-` and the designation
   "BCW-1" to "BCW-2".
   - It works on the imported files only. Files written in the new repository
     are left alone.
   - Text that must refer to the previous design, such as the predecessor
     record, names BCW-1 explicitly.
   - Check: the frozen tree contains no "BCW-2" or "BCW2", so the reverse
     substitution is unambiguous. Applied to the result, it must reproduce the
     frozen bytes.
3. The converter turns every labelled statement into a chunk and assigns
   anchors, using a minimal parser and the reader-edition weave. The migration
   ledger in `exp/` is generated, not written.
   - Check: the woven reader edition equals the renamed frozen documents, byte
     for byte.
   - The documents keep their BCW-1 form at this point, because pass 1 changes
     nothing. Their form changes later, through the loop.
4. The RTL moves byte for byte. The commit that adds anchor citations to the
   Verilog comments is checked to change comments only: strip the comments on
   both sides and compare.
5. A separate commit removes BCW-1's four convention checks from `make check`.
   The imported `mk/checks.mk` lists `check-ste`, `check-xref`,
   `check-argument` and `check-lint` in `CHECKS`. Without `.claude/`,
   `check-ste` prints "skipping" and passes (section 5.10). The commit deletes
   the four names from `CHECKS` and deletes their four targets. The scripts
   under `docs/` stay until pass 2 removes the CONV rules that name them.
   - Check: the commit changes only `mk/checks.mk`, and `make check` runs
     exactly the 28 machine checks of section 5.10.
6. The machine's checks of section 5.10 run on the imported tree. Their output
   is recorded once at `bcw1-final`, on exactly the imported file set, as the
   machine-check fixture.

Done when:

- the machine's checks pass in CI, with output identical to the fixture;
- both identity checks pass.

### 6.3 W2: the tool core and the documentation requirements

- **The tool** of section 3.6, except its watch mode.
- **The model moves.** The 35 formulas of `lifecycle.py` move into their chunks
  as twins, and its quote check becomes the review stamp.
  - Check: both semantic-diff queries, run between the frozen `lifecycle.py`
    and the tangled model, are unsatisfiable. The four findings are unchanged.
- **The fast checks** of section 3.8 that need no parents and no RTL, as
  ratchets:
  - structure, labels, one rule per chunk, argument budget;
  - language, with the linter moved into the tool tree;
  - vocabulary, cross-references, anchors;
  - restatement, the specification model, the reader-edition allow-list;
  - parameter assertions, the first being CORE 2.3's hazard inequality;
  - check placement, defects, and the machine-check fixture.
- **Two slow checks** that the fast checks above leave to the slow tier
  (section 3.11): the redundancy query over twins, and the comparison of the
  machine checks' output with the fixture.
- **The sentence split.** The 94 blocks holding more than one "shall" are split
  in a separate scripted commit.
  - Check: the multiset of sentences is unchanged.
- **The tool's own mutants.** Every process row of section 3.17 that W2's
  checks cover becomes a test.

Done when:

- `make check-fast` runs in under 30 s locally and prints every non-zero
  baseline;
- every one of the tool's mutants fails as intended.

### 6.4 W3: the loop and the design gate

- **The gate:** the routing, semantic diff and `design-gate` check of section
  3.15.
- **What CI posts:** the reader-edition diff and the semantic diff, on every
  pull request.
- **The CI frequencies** of section 3.7.
- **The defect list,** migrated per D5. Severity 1 by phase:
  - phase 3: #2, #3, #4, #296, #298, #300, #301, #314;
  - phase 4: #6 to #12;
  - phase 6: #13, #14.
- **The standing-exit counters** of section 3.10, and the process-health log
  of section 3.16.

Done when four test pull requests behave as specified. None of them merges.

- The stop's cause changed from 7 to 5 in CAPH 2.9 and its twin. It is flagged
  with a trace and blocked until the author's label.
- The same twin rewritten without changing its meaning. It passes with no
  approval.
- A change to the gate's routing code that would pass every change. It is
  routed to the author, and the gate that judges it is the default branch's
  copy.
- The first test pull request, with the approval label added through the LLM's
  GitHub tools. `design-gate` does not pass. If GitHub records no app on that
  label event, the gate cannot tell the LLM's label from the author's. Then W3
  stops, and the author decides how approval is given.

### 6.5 P1: the first changes of meaning, and the new conventions

Each item is its own pull request, through the gate:

1. The name: close the OPEN of SYST 3.
2. The argument's top:
   - RATH 1.2 rewritten for cognitive burden (section 3.13);
   - the scope rule of section 4.1;
   - the security properties of RATH 4.1, RATH 4.2 and RATH 4.3, labelled with
     anchors, and the timing invariant stated as a rule;
   - the threat model, stated once.
3. The new conventions document. It records the documentation requirements
   of sections 3.8 to 3.10 and the decisions of section 2, and settles D7.
4. The new `CLAUDE.md`, written from the conventions document. It is short and
   points at `make check-fast` and the loop. Its formal scope follows D4.

Then switch on, as ratchets:

- trace upward, twins, burden measures, supervisor rules and mutations;
- the RTL lint check, if D7 adopts it.

Done when the argument map renders with its unresolved leaves.

### 6.6 P2: build-plan phase 3, through the workflow

1. **The slice's severity-1 items.** The request-lifecycle slice is the ten
   sections of the table below. Its severity-1 items are #2, #3, #4, #296,
   #298, #300, #301 and #314. Five of them are design questions for the
   author: #2, #4, #298, #300 and #301. Each fix is checked by the model and
   the semantic diff.

   | Section | Built | Severity-1 items | Model findings |
   |---|---|---|---|
   | CORE 2.8 | yes | #298 | |
   | CORE 2.10 | yes | | |
   | CORE 2.11 | yes | | #310, #312 |
   | CAPH 2.4 | phase 3 | | |
   | CAPH 2.5 | phase 3 | #3, #4, #300, #301 | |
   | CAPH 2.9 | phase 3 | #2, #296, #314 | #296, #311 |
   | CAPH 3.3 | phase 3 | | |
   | SIPC 2.1 | phase 3 | | |
   | SIPC 2.5 | phase 3 | | |
   | SURF 4.1 | phase 4 | | |

2. **The slice to zero,** on every check that applies (section 3.8).
3. **Module models, then RTL,** for the four formal checks of section 3.12,
   and then the proofs of equivalence.
4. **Leg 1 by self-composition on the core,** per section 3.12. The planted
   leak becomes its stored mutant.
5. **The rest of phase 3:**
   - the supervisor interface;
   - the status word and the supervisor's wait on it;
   - the bank switch;
   - the boot ROM.

Done when the build plan's phase-3 gate is met:

- a confined program runs and faults correctly;
- CAPH 5 is met in full, including the proofs;
- SIPC 5 is met;
- numbers 5 and 9 of the open-numbers record are answered.

Then one sampled reading of the phase, and no open severity-1 entry for it.

### 6.7 After P2

Build-plan phases 4, 5 and 6 follow in order, each through P2's steps. Phase 4
carries #6 to #12, and phase 6 carries #13 and #14.

## 7. Specification changes queued for pass 2

Each is a change of meaning, through the loop, one per pull request. Items 1
to 4 are P1's. The others follow in the phase whose subsystem they concern,
unless the author orders them otherwise.

1. **The name:** close the OPEN of SYST 3 (section 2.1).
2. **The argument's top** (section 6.5).
3. **Cognitive burden.**
   - RATH 1.2 is rewritten as section 3.13 drafts.
   - The census rules of CONV 10 become guidance for classifying a DEFINITION
     in the new conventions document.
   - The census record becomes a generated report of the measures.
   - Rationale that names conceptual economy is reworded, for example RATH 1.4
     and RATH 3.
4. **The conventions' own word.** CONV 6's identifier scheme uses "slot", which
   the vocabulary table forbids. The scheme is renamed in the new conventions
   document.
5. **A conflict inside the specification.** CORE 2.8 defines a suspended
   thread's registers as stable and readable. CAPH 2.9 has a target write the
   argument registers of a request in flight. The system model reports the
   contradiction once both rules have twins. The resolution follows Leg 2:
   registers are stable except for a target's writes to the argument registers
   of a request in flight.
6. **Signals.**
   - Delete the Signals row of SIPC 4.2.
   - Replace the limitation "No hardware-delivered signals" in SIPC 2.7 with
     "No signals: events arrive as channel messages, taken by a blocking
     receive".
   - Add the channel constraints of section 4.4 item 1 to SIPC 2.8.
7. **Quotas.** Add the quota rule to SIPC, and to the life of a process in
   SIPC 4.2: creation grants the quotas.
8. **The target rule** and **revocation after stop,** if the author adopts them
   (section 2.3).
9. **Baselines to clear.**
   - Six REQUIREMENTs contain no "shall":
     - CONV 1.0 (the tree-placement test) and CONV 9 (the vocabulary rule) go
       with the rules section 3.9 removes or reduces;
     - GRPH 2.2 (the surface definition), GRPH 2.6 (the scanline deadline),
       AUDP 3.1 (the reconstruction filter) and SPER 3.1 (the serial register
       layout) are relabelled or reworded.
   - Eighteen sentences hold two "shall"s, mostly compound instructions such as
     "shall be decoded and shall have no effect". They are split.
   - Four DEFINITION sentences exceed the 25-word cap.
   - The system model's four findings: #296, #310, #311 and #312.
10. **The ISO/IEC/IEEE 29148:2018 decision** of section 3.14, recorded in the
    decisions record.
11. **The open risks** of section 4.4, items 6 to 10, each settled when its
    subsystem's phase comes.

## 8. Glossary

The specification's own terms (thread, worker, process, turn, stage, region,
handle, accelerator, bank, core) keep the meanings of section 3.9.

- **Anchor:** a stable identifier for one rule chunk.
- **Argument:** a RATIONALE or DISCUSSION block.
- **Argument map:** the generated tree of each security property's legs,
  rules, twins, checks and assumptions, woven into the rationale.
- **Audit edition:** the woven documents with everything expanded; deferred.
- **Baseline:** the number of violations of one check in one document; it may
  fall but never rise.
- **BCW-1, BCW-2:** the previous design, in the frozen repository; and the
  design in the new repository, whose name is Soubou.
- **Burden measure:** a count, computed by a fast-tier script, that stands for
  part of the cognitive burden.
- **Check kind:** `equiv`, `rtl`, `netlist`, `static`, `test`, `measure` or
  `audit`.
- **Cognitive burden:** what a reader must hold in mind to build, verify or
  operate the machine.
- **Design gate:** the rule that a change routed to the author merges only with
  the author's approval (section 3.15).
- **Editorial change:** a change whose normalised text is unchanged, or whose
  semantic-diff queries are both unsatisfiable.
- **Exit:** a legitimate way for a rule to pass a check it would otherwise
  fail.
- **External time reference:** anything from outside the machine that lets a
  process measure real time.
- **Fast tier, slow tier:** the checks within the 30-second budget, run on
  every edit; and all checks. **Touched slow checks** are the slow checks bound
  to what a change touches.
- **Kahn-pure:** a request interface offering only blocking reads on named
  resources, exact-length reads, blocking writes and fixed-rule merges.
- **Leg:** one of the three properties of section 4.2 on which the timing
  invariant rests.
- **Literate by reference:** source code kept in its own language and files,
  carrying citations of the rules it implements, from which the weaver pulls
  blocks into the documents.
- **Logical time:** the number of instructions a process has executed.
- **Machine-check fixture:** the recorded output of the machine's checks at
  `bcw1-final`.
- **Module model:** the formal specification of one formal check, written from
  its English rule before its RTL.
- **Pass 1, pass 2:** the mechanical import; and every change of meaning after
  it.
- **Probation:** the period after a check or measure is introduced, ending at a
  named phase gate, by which it must have found something real or be removed.
- **Quota:** a process's fixed allowance of an allocatable resource, granted at
  creation.
- **Ratchet:** a check whose count of violations may fall but never rise.
- **Reader edition:** the woven documents for reading the design.
- **Review stamp:** a hash, recorded with a twin, of the English it was last
  validated against.
- **Rule:** a REQUIREMENT, PARAMETER or DEFINITION.
- **Rule chunk:** one labelled rule, its anchor, and the blocks that belong to
  it.
- **Rule-cluster:** a subsection holding at least one rule, or carrying
  argument of its own.
- **Self-composition:** verifying a property of pairs of executions by running
  two copies of a design side by side.
- **Semantic diff:** the changes in meaning a change causes, found by the model
  queries, the RTL trace comparison and the catalogue diff (section 3.15).
- **Slice:** the request-lifecycle sections of section 6.6.
- **System model:** the specification-level model of the rules, grown from
  `docs/formal/lifecycle.py`.
- **Twin:** the formal statement of a rule, in the same chunk.

Sources: Kahn, "The Semantics of a Simple Language for Parallel Programming"
(1974). Knuth, "Literate Programming" (1984). Barthe, D'Argenio and Rezk,
"Secure Information Flow by Self-Composition" (2004). Clarkson and Schneider,
"Hyperproperties" (2010). Sweller, van Merriënboer and Paas, on cognitive load
theory. ISO/IEC/IEEE 29148:2018.
