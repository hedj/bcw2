# Handoff: Event-B and Rodin as the formal system of bcw2

For a Claude who plans or starts the move of bcw2's formal machinery to Event-B. Everything here
was measured in one session (1–2 Oct 2026), in a cloud container with 4 cores. It is a probe, not
a design: nothing here is part of the book, and `make check` does not run it. Where something was
not tested, the note says so.

## Verdict

Event-B in Rodin can replace the ad-hoc formal system of bcw2 (twins, `equiv`, `prove`) and
enforce a top-down exposition, with open solvers only and no weaker proofs. A vertical slice
proved, with no proof written by hand, from a top machine (threads, a fixed rotation, isolation)
down to sequential RTL: 144 of 144 obligations in 17 s. A mutant check killed each of three
seeded faults with a concrete counterexample, and kept a correct variant. Verilog generated from
the slice's lowest machine proves the same obligations through the same bridge, and synthesises to
the same netlist as the hand-written ring.

Not probed: non-interference, the multiplier, a whole chapter's audit time and live set.

## Decisions the author made

| Decision | Detail |
|---|---|
| Event-B enforces the top-down exposition | To build refinement into bcw2's own tools would reinvent the B-method |
| Open solvers only | The ClearSy provers (ML, PP) were tried and removed: proprietary |
| No weaker proofs | A check replaces a proof only if the check is exhaustive |
| A mutant is killed only by a counterexample | An obligation that stays open, or a timeout, is not a kill |
| No direct z3 calls | Solvers run only inside Rodin; ProB gives counterexamples |
| Proof budget | Timeout 6 s per attempt; quick Z3 0.7 s; SLOWER means over 1 s and over 1.5 times the baseline |

## Toolchain

| Part | Version and source | Notes |
|---|---|---|
| Rodin | 3.10.0, `rodin-3.10.0.202607010932-881664d81-linux.gtk.x86_64.tar.gz` from SourceForge (`Core_Rodin_Platform/3.10`), sha256 `5323ef00173320a27c410ee6db200fa337e7249ecad4df5655f0100e6f75ff46` | Headless with `-application bcw.rodin.build` |
| JDK | Nix `jdk21_headless` from the repository's nixpkgs (openjdk-headless 21.0.12.1) | `--add-modules=ALL-SYSTEM` |
| SMT Solvers plug-in | 1.5.0, `https://rodin-b-sharp.sourceforge.net/updates/Plugin_SMT_Solvers/1.5.0`, installed by p2 director: `-installIU org.eventb.smt.feature.group,org.eventb.smt.cvc4.feature.group,org.eventb.smt.z3.feature.group` | Bundles CVC3, CVC4 and Z3 4.5, which the default solvers do not use |
| Z3 | 4.16.0 from the repository's nixpkgs (`nixpkgs#z3`; `./dev` has the same version) | `bcw.z3new`, or `z3` on PATH; replaces the plug-in's Z3 4.5.0 |
| cvc5 | 1.4.0 from the repository's nixpkgs (`nixpkgs#cvc5`; not in `./dev`) | `bcw.cvc5`, or `cvc5` on PATH; replaces CVC3 and CVC4 |
| ProB | 1.16.2-nightly source, `https://www3.hhu.de/stups/downloads/prob/source/ProB_src.tgz`, sha256 `7b1277140ca528b6ff55207a00f34e30607bb71b307ba08d4c14c7d2f8b99463`; EPL 1.0 | Parser: `./gradlew updateParser` (Maven `de.hhu.stups:cliparser:2.16.1`) |
| SWI-Prolog | 10.0.2 from the repository's nixpkgs | `PROLOG_SYSTEM=swi ./probcli_src.sh` |

The Theory plug-in (4.0.4) was installed for a probe but nothing here needs it. The ProB tarball is
a moving nightly with no revision stamp: pin a fixed copy by its hash.

## The build application (`rodin-app/`)

`Build.java` (360 lines) is an Eclipse application in an OSGi bundle in Rodin's `dropins/`. Build
it with `javac --release 17` against every jar in Rodin's `plugins/`, then `jar cfm` with
`META-INF/MANIFEST.MF` and `plugin.xml`. Check `javac`'s own exit status: a pipe through `grep`
once skipped the `jar` step and ran an old bundle.

For each project on the command line it imports, builds and proves every obligation:

1. Rodin's default auto-tactic. Rodin turns on its auto-prover only from the GUI, so the
   application applies tactics through `IProofAttempt`.
2. The first solver (Z3 4.16) alone on the selected hypotheses for 0.7 s (`bcw.first`). It closes
   most goals.
3. A contest of two searches at once, each on its own copy of the goal. The first proof is
   grafted onto the goal by `ProofBuilder.reuse`, and the other search stops:
   * the sets: all four solvers at once on the goal alone, then on the selected hypotheses,
     then on all of them, 6 s each (`bcw.timeout`);
   * the split, for a variable that a hypothesis bounds to at most 8 values (`bcw.split`): a
     variable of the goal if one has such a bound, else a variable that shares a hypothesis with
     the goal (see Primed names). Rodin's case rule (`Tactics.doCase`) for each value, Rodin's tactics on each
     case, the first solver for 0.7 s on the selected hypotheses and then on all, and then the sets.
4. The obligations of a file are proved 4 at once (`bcw.jobs`). Attempts are created, committed
   and disposed one at a time.

Other properties: `bcw.report` (CSV: obligation, result, ms, closers), `bcw.baseline` (an earlier
report; prints LOST and SLOWER), `bcw.measure` (each solver in turn on each goal, timed), and
`bcw.solvers` (default `z3new,z3a2,cvc5`; see A newer Z3 and Primed names). `bcw.z3new` and `bcw.cvc5` name
the binaries, else the `z3` and `cvc5` on PATH are used; the run prints which. A solver of the
order that is not available stops the run with exit status 2. The exit status is 1 if an
obligation stays open.

Each solver call writes its own temporary file and reads its own process's output, so parallel
calls cannot read each other's answers.

### How proof state passes from one step to the next

Rodin passes state only through the proof tree. Its own tactics leave their work as new subgoals;
an external prover either closes the goal it gets or leaves it as it was.

| Kind of step | Effect on the proof tree | Passed on to later steps |
|---|---|---|
| Rewriters and splitters (Rodin's default auto-tactic) | Replace a goal by simpler subgoals | The open subgoals |
| Hypothesis selection (for example lasso), recorded as a rule | Changes the selected hypotheses of a subgoal | The new selection |
| Case split (`Tactics.doCase`) | One subgoal for each case, with the case as a hypothesis | Each case as a new goal |
| External prover (SMT; ML, PP and ProB where installed) | On success, one rule that closes the goal and records the hypotheses it used; on failure, nothing | Only the closure: no lemmas, partial models or search state |

Rodin's combinators (`BasicTactics`) follow this: `composeOnAllPending`, `loopOnAllPending` and
`onAllPending` apply the next tactic to the goals that are still open, and `composeUntilSuccess`
tries alternatives on one goal. In `Build.java` each solver also runs on its own copy of the goal,
as a fresh process with its own benchmark file.

So the order of the solvers changes only the time a race takes: a solver tried later gains nothing
from a failed attempt before it. What helps a solver is a step that transforms the goal before it.
Rodin's default tactic is one; the split is another, and it made the `where_r` invariants, which no
solver proved alone, easy. For a goal that is too hard, add a rewrite, a split or a hypothesis
selection before the solvers, rather than change their order.

## The bridge from Verilog to the lowest machine (`gen/`)

yosys `prep -flatten; opt -full` (and `dffunmap; opt_clean` for registers), then `write_json`.
`bridge2.py` and `bridge_seq.py` translate the netlist; a generator writes the lowest machine,
which refines a hand-written machine, and Rodin proves the refinement.

| Rule | Translation |
|---|---|
| Choice, `$mux`, compare | `({TRUE ↦ x, FALSE ↦ y})(bool(c))` |
| `$add`, `$sub` of width w | The choice that adds or subtracts `2^w` on overflow |
| `$and`, `$or`, `$xor` | Gate parameters in 0 ‥ 1 with linear constraints (the `GATES` table); xor is four inequalities, with no helper term |
| `$pmux` | A one-hot side condition |
| `$shl`, `$shr`, `$sshr` | A case table over the shift amount |
| `$scopeinfo` | Skipped |
| `$dff` | Each named wire that registers drive is a state variable; its D input is its next value. One event for each value of the reset input; at power-up each register takes any value of its width |
| A parameter of the specification | Must be a bit that the netlist names, so it needs no witness: the bits of a gate on the output port are `r0` … `r31`. Else the generator stops and names the parameter; there is no witness table, and no default witness `⊤` |

`core_alu` is proved per (f3, alt): a wrapper `alu/alu_F_T.v` fixes the controls and yosys
propagates them, so each netlist holds one operation. `alu/netlists.sh` rebuilds the 16 netlists.

## Modelling rules learnt

| Proves automatically | Does not |
|---|---|
| Integer registers with per-event bit splits as event parameters | Bit functions glued to integers by sums (205 s, 5 open) |
| Logic as linear 0/1 constraints | Products `aᵢ ∗ bᵢ` (nonlinear) |
| An explicit carry, `a + b = c ∗ 2ⁿ + r` | `mod`, `÷`, `^`: the SMT translation leaves them uninterpreted |
| A cyclic successor as a set of pairs, or a choice | Quantified axioms: no solver instantiates them |
| Field splits as event parameters | Field splits as witnesses: a witness may name only its own parameter |
| Scalar stage records glued to a function by a case table on the turn, with the split | The same gluing without the split: true (ProB), but the solvers time out |
| The lowest machine named as the RTL names its registers | — |

The lowest machine mirrors the structure of the RTL. A correct XOR built as `(a | b) − (a & b)`
(`alu/ctl_xor`) is not proved by the word-level bridge (it is at bit level: see Bit-level
normalisation): the bridge is sound but not complete. Its output comes from `$sub`,
so the netlist names no bit `r0` … `r31` of the specification, and the generator stops with that
message. Before, a table of the specification's values gave the witnesses, and the refinement goal
stayed open with no counterexample from ProB. With linear forms for `$sub` and for those
witnesses, it still stayed open at 6 s: it needs case reasoning on each of the 32 bits.

## Measurements

| Run | Result |
|---|---|
| 311 goals, each solver timed (`reports/measure.csv`) | Z3 proves 308 with all hypotheses, 299 with the selected ones (largest success 5,645 ms against 242 ms); no goal falls only to the selected hypotheses |
| Seven probe models, 74 obligations, by strategy | Sequential ladder 49 s; race only 55 s; quick Z3 then race 27 s; contest 27 s (`reports/contest2_7.csv`, no LOST, no SLOWER against `reports/baseline.csv`) |
| Bridge, combinational | `core_rotate` 50 ms; `core_region` 32 ms; `core_alu` 32 of 32 in 41 s with gates (the first, monolithic form was too slow) |
| Slice: M0 (threads, rotation, isolation), M1 (ring of 8 stage records), M2 (generated from `slice/ring.v`) | 11 + 70 + 63 = 144 of 144 in 30 s wall one obligation at a time (`reports/contest2slice.csv`), 17 s four at a time (`reports/speed/F.csv`); M2 alone 0.8 s |
| Slice, written by hand against the RTL | `slice/spec.py`, 38 lines, for 15 lines of RTL |
| Speed-ups, one run each (`reports/speed/`) | Slice wall: 30.5 s before (A); 16.9 s with 4 obligations at once (F, kept). Seven models: 27 s before; 23.6 s (F7). No obligation lost |

Two more speed-ups were measured and then removed, as about 40 lines of code for a gain that one
run each cannot separate from noise: the cases of a split at once (slice 30.5 → 27.6 s, B) and a
1 s wait for the sets when a split applies (→ 25.9 s, C). The trade-off: with both and 4
obligations at once the slice took 13.5 s (E), against 16.9 s without them (F). The 8 `where_r`
invariants average about 2.3 s each in every configuration, and where that time goes is not
measured.

Obligations run at once compete for the 4 cores, so one obligation can take longer while the whole
run takes less. A baseline from a sequential run then reports SLOWER (here 1.2 s → 2.0–2.3 s for
three obligations with 62 goals each); take the baseline with the same `bcw.jobs`.

`core_region`'s rule holds only for `size ∈ 1 ‥ 7`. Size 0 is reachable (`3'd1 << f3[1:0]` with
`f3[1:0] = 3`), but only for an illegal access.

## Mutant check

A kill needs ProB to find a solution of hypotheses ∧ ¬goal for an open obligation's root sequent.
`prob/po_extract.py` writes that predicate from Rodin's `.bpo` file (primes become `_prime`).

| Model | Seeded fault | Result |
|---|---|---|
| ALU subtract | `b - a` | Killed: `a = 1, b = 0` |
| ALU xor | `a \| b` | Killed: `a = 1, b = 1` |
| ALU control | `(a \| b) - (a & b)` (correct) | Neither proved nor killed (no counterexample in 300 s) |
| Slice `wrap6` | `core_rotate` wraps at 6 | Killed: `rot = 6` |
| Slice `wrongrec` | W steps the M2 record | Killed: `rot = 0, m2_rec = 1, w_rec = 0, in = 0` |
| Slice `reset` | Reset leaves thread 0 stopped | Killed: any state |
| Slice `control` | `rot + 3'd1`, a 3-bit wrap (correct) | Proved, 144 of 144 |

The SMT plug-in also reports `sat`, `unsat` or `unknown` with the Eclipse debug options in
`prob/smt-debug.options` (`reports/verdict.raw`). A `sat` is weaker evidence: the plug-in promises
only that `unsat` is sound.

## cvc5 in place of CVC3 and CVC4

CVC3 is unmaintained and CVC4 is superseded; both ship as binaries inside the SMT plug-in. cvc5 1.4.0
is in the pinned nixpkgs. The plug-in has no kind for cvc5, so `bcw.cvc5` registers the binary as a
CVC4, with `--finite-model-find` (cvc5 rejects the CVC4 configuration's `--fmf-inst-engine`), or
the options of `bcw.cvc5args`. cvc5 checks its answer against the benchmark's
`(set-info :status unsat)` and reports an error, not `sat`; the plug-in counts both as a failure.

Of the 311 measured goals, 3 need CVC3 or CVC4. With Z3, cvc5 and veriT (`reports/cvc5/`):

| Goal | Before | With cvc5 |
|---|---|---|
| `DecodeInt/M1/decode/grd1/GRD` | CVC3 only | Proved: cvc5 with all hypotheses |
| `RotLaps/M1/wrap/glue/INV` | CVC3 or CVC4 | Proved: cvc5 on the goal alone |
| `Shift/M1/sll/act1/SIM` | CVC3 only | Open, with or without `--finite-model-find`, at 6 s and at 20 s |

The open goal's benchmark (`reports/cvc5/sll_sim.smt2`, as the plug-in writes it) is quantifier-free
linear integer arithmetic (`QF_AUFLIA`): division with remainder by 2³³, `a ∗ 2ᵏ = hi ∗ 2³³ + r`,
in a 32-way case table on `k`, against five barrel stages. Run directly:

| Solver and options | Result |
|---|---|
| CVC3 2.4.1, no options (as the plug-in runs it) | `unsat` in 2.4 s |
| cvc5 1.4.0, no options, 120 s | no answer |
| cvc5 with each of `--finite-model-find`, `--dio-decomps`, `--dio-turns=100`, `--cut-all-bounded`, `--arith-eq-solver`, `--arith-rewrite-equalities`, `--miplib-trick`, `--arith-static-learning`, `--no-arith-brab`, `--decision=justification`, `--simplification=none`, `--ite-simp`, `--learned-rewrite`, `--pb-rewrites`, `--restrict-pivots`, `--unate-lemmas=none`, and four pairs of them, 20 s | no answer |
| cvc5, four of those, 120 s; and `--no-dio-solver`, 120 s | no answer |
| cvc5 with each of the 183 switches in its own `--help` (output and unrelated theories left out), 5 s (`reports/cvc5/sweep-5s.tsv`) | no answer; `--preprocess-only` stops before solving |
| With `0 ≤ a ≤ 2³³ − 1` added (an invariant that the selected hypotheses leave out): CVC3 / cvc5 with five option sets, 60 s | `unsat` in 2.1 s / no answer |

The two solvers decide integer arithmetic differently. CVC3 eliminates integer variables exactly
(Fourier–Motzkin with dark and gray shadows; its `-grayshadow-threshold` option). cvc5 uses simplex
with branch and bound, cuts and a Diophantine equation solver, and documents no option for exact
elimination. So cvc5 does not prove everything that CVC3 proves.

The goal comes from the `Shift` probe model, which predates two later rules: it uses 33-bit words,
and it writes a shift as division with remainder. The bridge writes shifts as case tables of bit
sums, and `BridgeAluGates` proves its shifts without CVC3. A `Shift` model in the bridge's form might
let cvc5 replace both CVC3 and CVC4; that is not tested.

So cvc5 can replace CVC4 but not CVC3.

CVC4 itself proves nothing that the others do not. In `reports/measure.csv`, CVC4 proves 134 goals
that CVC3 does not, and Z3 proves all 134. CVC3 proves 7 goals that CVC4 does not; two of them
(Shift `sll` SIM and one goal of `DecodeInt` decode GRD) nothing else proves. The one goal that
only CVC3 and CVC4 prove (`RotLaps/M1/wrap/glue/INV`) CVC3 proves alone. But `measure.csv`
predates the slice, and the slice needs CVC4 or cvc5 (`reports/cvc5/`, one run each):

| Solvers | Seven models (74) | Slice (144) |
|---|---|---|
| Z3, CVC3, CVC4, veriT (default) | 74, 23.6 s | 144, 16.9 s |
| Z3, CVC3, veriT | 74, 19.6 s | 139: 5 `where_r` open, 47.0 s |
| Z3, CVC4, veriT | not run (Shift `sll` needs CVC3) | 144, 13.6 s |
| Z3, CVC3, cvc5, veriT | 74, 20.3 s | 144, 14.8 s |

So cvc5 replaces CVC4 on every measured obligation, and CVC3 stays for Shift `sll`.

As a trial, `gen/shift.py` was rewritten with 32-bit words and shifts as offsets in indexed bit sums
(M0: a table over k, each case the bits of a moved k places; M1: a five-stage barrel that moves each
bit 2^j places when bit j of k is 1). The new SIMs need no CVC3: CVC4 proves them, and so does cvc5
(`unsat` in 3.8 s on its own), though under Rodin only with less contention or more time. Their
benchmarks have 31 quantifiers, from the translation of the `ite` functions. With the bit-sum
`Shift` (one run each; the bit-sum form is in commit `d4ad774`, reverted since, so `gen/shift.py`
and `models/Shift` hold the original model):

| Solvers | Timeout | Seven models (76) | Slice (144) |
|---|---|---|---|
| Z3, CVC3, CVC4, veriT | 6 s | 76, 33.3 s | 144, 16.9 s |
| Z3, cvc5, veriT | 6 s | 75: `Shift/M1/sll/act1/SIM` open, 43.1 s | 144, 13.5 s |
| Z3, cvc5, veriT | 10 s | 76, 48.8 s | 144, 14.6 s |

So with the bit-sum `Shift`, Z3, cvc5 and veriT prove every measured obligation with a 10 s timeout,
and need neither CVC3 nor CVC4. With the original `Shift`, its `sll` SIM still needs CVC3. The
trade-off: the seven models take 48.8 s, against 33.3 s with the four solvers. The bit-sum `Shift`
is itself slower than the original (seven models 33.3 s, against 23.6 s). The default
then stayed Z3, CVC3, CVC4, veriT and 6 s; A newer Z3 below replaced it.

## A newer Z3

The plug-in bundles Z3 4.5.0 (2016); the pinned nixpkgs has Z3 4.16.0. `bcw.z3new` registers the
newer binary as the solver `z3new`, and also as `z3a2`, the same binary with
`smt.arith.solver=2`, its older arithmetic solver; `bcw.z3newargs` gives `z3new` other options.
The quick attempt and the split's short attempts use the first solver of `bcw.solvers`. With the
original models (`reports/z3new/`, one run each):

| Solvers | Seven models (74) | Slice (144) |
|---|---|---|
| Z3 4.5 alone | 71, 39.6 s: open `RotLaps` glue, `DecodeInt` decode GRD, Shift `sll` SIM | 135, 37.9 s: 8 `where_r` and `init_val` SIM open |
| Z3 4.16 alone | 72, 30.1 s: open `RotLaps` glue, `FieldInt` extract GRD | 136, 39.1 s: 7 `where_r` and `init_val` SIM open |
| Z3 4.16 with `smt.arith.solver=2` alone | 71, 34.2 s: as Z3 4.5 | not run |
| Z3 4.16, CVC3, CVC4, veriT | 74, 21.0 s | 144, 15.4 s |
| Z3 4.16, cvc5, veriT | 73, 30.0 s: `FieldInt` extract GRD open | 144, 14.6 s |
| Z3 4.5, Z3 4.16, cvc5, veriT | 74, 24.9 s | 144, 14.8 s |
| **Z3 4.16, `z3a2`, cvc5, veriT** | **74, 25.4 s** | **144, 15.3 s** |
| Z3 4.16, `z3a2`, cvc5 | 74, 24.6 s | 143: `init_val` SIM open (veriT proves it) |
| Z3 4.5, CVC3, CVC4, veriT (default) | 74, 23.6 s | 144, 16.9 s |

The two arithmetic solvers of Z3 4.16 prove different goals: the default proves Shift `sll` SIM,
which before only CVC3 proved, and one goal of `DecodeInt` decode GRD; the older one (as in Z3
4.5) proves `FieldInt` extract GRD. So Z3 4.16 in both modes, cvc5 and veriT prove every measured
obligation, without CVC3, CVC4 or the bundled Z3, in about the time of the default set. veriT,
still bundled, is the one solver that this set does not pin. Since commit `641496a` this set is the
default. With it, the seven models prove 74 of 74 in 25.0 s with the binaries found on PATH, and
`slice/mutant_check.sh` proves the slice and the control 144 of 144 and kills the three mutants, in
95 s in all (Rodin 74 s, against 148 s with the old default).

## Primed names, and the default without veriT

The SMT plug-in writes an after-value such as `val'` as a bare SMT-LIB name: `(declare-fun val'
(Int Int) Bool)`. That is not SMT-LIB, since `'` may not be part of a plain name. veriT and Z3 4.5
accept it; Z3 4.16 and cvc5 reject the whole input with a parse error, in a few milliseconds. In
the slice, 83 of 392 solver calls failed so (`-debug` trace of the plug-in). Rodin closed most of
those goals by itself; two were left to the solvers, both from the witness of `val'` at
INITIALISATION: `init_val` SIM and `val'` WFIS. Only veriT proved `init_val` SIM.

So after Rodin's default tactic, `unprime` in `Build.java` renames each primed name by Rodin's own
rule (`Tactics.abstrExprThenEq` with the input `val_prime = val'`: a fresh name and its equation,
used to rewrite every occurrence), and hides the equations, which still hold the primed names. The
proofs show `val_prime`, the name that `prob/po_extract.py` gives ProB; without a chosen name, Rodin
picks `ae`, `ae0`, and so on. Each step is a rule of
Rodin's prover, recorded in the proof tree; hiding a hypothesis only weakens what the solvers see.
Each renaming also leaves the goal ⊤, which Rodin's default tactic closes; the renaming skips those
goals, else the goals double with each name (1,024 goals and 55 s for `init_val` SIM).

Results (`reports/unprime/`, against `reports/opt1b/`):

| Solvers | Seven models (74) | Slice (144) |
|---|---|---|
| Z3 4.16, `z3a2`, cvc5 | 74, wall 22.6 s | 144, 16.5 s; `init_val` SIM by `z3new` in 0.25 s |
| Z3 4.16, `z3a2`, cvc5, veriT | 74, 24.8 s | 144, 16.5 s |
| Before the renaming, with veriT | 74, 22.1 s | 144, 16.6 s; `init_val` SIM by veriT in 1.9 s |

No obligation is lost. The one SLOWER line, Shift `sll` SIM with veriT (2.5 → 4.8 s), took 2.2 s
in the run without veriT, so it is noise. `slice/mutant_check.sh` with `z3new,z3a2,cvc5`: ring
and control 144 of 144, the three mutants killed by ProB, 80 s in all (Rodin 58 s). So the
default is `z3new,z3a2,cvc5`, and veriT is no longer needed.

Before the cause was found, two other changes were tried:

* The split takes a variable that shares a hypothesis with the goal when no goal variable has a
  small range, so it split `init_val` SIM on `rot'`. That did not prove it (the cases had primed
  names too), but it makes Shift `sll` SIM faster: 5.7 s → about 2.3 s, split on `k0`. It stays.
* The witness of `val'` stated as a function and its values, in four forms: each left 2 to 11
  obligations open (WFIS, WWD), and pointwise invariants made the slice 4 times slower. Dropped.

## Bit-level normalisation (`bits/`)

A netlist bit-blasted to single-bit gates proves where word-level cells do not. `bits/netlists.sh`
runs yosys `techmap` after `prep; opt -full`, and `bits/gen_bits.py` writes each gate as a 0/1
parameter with linear constraints (NOT inline as `1 − x`), with the output bits named `r0` … `r31`,
so that the specification's parameters need no witness. Three choices decide the proof time:

1. One guard per gate, in the order of the cones of `r0`, `r1`, …, with a theorem guard after each
   cone. A theorem's obligation has only the guards before it, so each proof is local, and the
   refinement goal follows from the theorems. The theorems name only bits of the netlist: for xor,
   `r(i)` is `a(i)` xor `b(i)`; for add, `A(i) + B(i) − R(i) = 2^(i+1) ∗ c(i+1)`, with `A(i)` the
   low `i + 1` bits of `a` and `c(i+1)` the carry gate into the next bit.
2. A ripple carry: yosys maps an adder to a Brent–Kung tree, in which each carry depends on all
   lower bits. `bits/ripple.v` (15 lines, tried before yosys's map because its name sorts first)
   maps `$lcu` to `CO[i] = G[i] | P[i] & CO[i−1]`, so each carry depends on the one below.
3. The quick attempt at 1 s (`bcw.first`).

Results, default solvers, 6 s timeout (`reports/bits/`):

| Netlist | Lowest machine | Proved | Wall, proof |
|---|---|---|---|
| Control xor, `(a \| b) − (a & b)`, 318 gates | One guard | 6 of 6 | 340 s, 657 s |
| Control xor | Cones and theorems | 70 of 70 | 96 s, 182 s |
| Adder, Brent–Kung, 220 gates | One guard (also at 60 s) | 3 of 4: SIM open | — |
| Adder, Brent–Kung | Cones and theorems, quick at 1 s | 36 of 36 | 37 s, 87 s |
| Adder, ripple, 154 gates | Cones and theorems | 36 of 36, each theorem by the quick attempt | 20 s, 31 s |
| Adder, ripple | Cones and theorems with the carry | 36 of 36 | 19 s, 25 s |

The control xor, which no word-level encoding proved, proves; so does the adder against `a + b`
modulo 2³². The proof is of the RTL's cells as `techmap` expands them, not of the circuit that the
FPGA tools build; `ripple.v` joins yosys's `techmap.v` as a trusted definition. The generated
machine is not for reading; the rules are: the gate constraints, the ripple map, the cone order and
one theorem form for each kind of operation. Not yet tried: sub, the compares, the shifts, the
multiplier, the divider, registers at bit level, mutants at bit level.

## Verilog generated from the lowest machine (`gen/eventb2v.py`)

The author prefers Verilog generated from a proved machine to hand-written RTL. `gen/eventb2v.py`
(280 lines) writes a synchronous module from a machine in a small subset. The generator need not
be trusted: the bridge reads its netlist back into M2, and Rodin proves that M2 refines the
machine (translation validation). `slice/mutant_check.sh` runs this for the slice as the variant
`gen`, which must prove: with it, the whole check proves `ring`, `control` and `gen` 144 of 144
and kills the three mutants, in 81 s (Rodin 63 s).

The subset, with any other form stopping the generator with a message that names it:

* Each variable has an invariant `x ∈ 0 ‥ n` and becomes a register of the bits of `n`, which
  powers up in any value (`INITIALISATION` gives `x :∈ 0 ‥ n`).
* The event `reset` has no parameters or guards and fires while `rst_n` is 0. One other event, the
  step, fires while `rst_n` is 1. Each of its parameters has one guard `p ∈ 0 ‥ n` and becomes an
  input port.
* Each event assigns every variable, `x ≔ e`, with `e` built from literals, variables, parameters,
  `+`, `−`, `∗` by a literal, and the choice `({TRUE ↦ e1, FALSE ↦ e2})(bool(c))`; `c` is built
  from the comparisons, `∧`, `∨` and `¬`.

Two choices make the netlist one that the bridge reads:

1. Each subexpression is a wire of its own width, so that no cell reads a slice of an internal
   signal, which the bridge does not translate.
2. A value is computed modulo 2^w at its register's width. This is exact, because the invariants
   prove that the integer lies in the register's range. The operands of a comparison are computed
   unsigned, at the width of their interval, so that the comparison sees the integers; an operand
   that may be negative is outside the subset.

The slice, from M1 (one run of both projects, 31 s):

| Measure | `ring.v`, by hand | Generated from M1 |
|---|---|---|
| Source | 15 lines and `core_rotate` (4) | 62 lines, generated |
| M2 from the netlist | — | Byte-identical to that of `ring.v` |
| Obligations | 144 of 144 | 144 of 144 |
| ECP5 cells (`synth_ecp5`) | 67 TRELLIS_FF, 6 LUT4, 4 CCU2C | The same |
| Fmax, 3 seeds, static placer | 295, 298, 308 MHz | 298, 298, 304 MHz |

Two faults of the kind a generator makes, seeded in the generated ring, each left one obligation
open, and ProB found a counterexample to each:

| Fault | Open obligation | Counterexample |
|---|---|---|
| The choice of `rot`'s next value swapped (`t1 ? t2 : 3'd0`) | `clock/rot/SIM` | `rot = 0` |
| `f_rec` reset to 0, not 1 | `reset/reset_f_rec/SIM` | Any state |

They are of the same kind as the mutants `wrap6` and `reset`, so they are not kept as files.

Not yet in the subset, and needed for a core: products of two variables, bit operations (and, or,
shifts, slices), memories, and several step events selected by guards. Each needs the bridge to
read its cells back, which the bit-level probe (`bits/`) does for xor and add. The generated
module has an output `x_q` for each register, since a machine does not say which variables are
outputs; `ring.v` has only `turn` and `w`.

## Below the bridge's netlist (`netlist/`)

The bridge reads the netlist after `prep; opt -full`. The FPGA gets the one after `synth_ecp5` and
nextpnr. `netlist/check.sh` checks a netlist of either kind against the bridge's netlist (GOLD)
with yosys alone, in two ways:

1. **Proof:** `equiv_make`, `equiv_simple` and `equiv_induct` prove, by induction, that the
   signals with the same name stay equal. GOLD may power up in any state, so this proves that every
   run of the gate netlist is a run of GOLD.
2. **Counterexample search:** `sat` searches 20 cycles of a miter. GOLD starts in the gate's
   power-up state, which `powerup.py` copies onto it. As in the mutant check, only a
   counterexample counts as a kill.

The cells become logic through yosys's models (`cells_sim.v`). The routed netlist needs three more
facts, which `routed_cells.v` and the option `EXTRA` state. They are trusted, like `ripple.v`:

* nextpnr's flip-flop takes its data from `M` when `SD` is 0, and from `DI` when `SD` is 1. In the
  slice's routed netlist, every flip-flop with `SD = 0` has `DI` unconnected.
* `TRELLIS_IO` with its tristate control unconnected, and `DCCA`, the clock buffer, as a wire.
* An unconnected cell input is 1. nextpnr folds constant inputs into each LUT's `INITVAL` and
  leaves the pin unconnected; read with 0, the adder cells compute `A`, not `A xor B`.

The check found a defect in yosys 0.69's model of `TRELLIS_COMB`: in mode CCU2 it declares
`wire FCO = …` inside a generate block. That is a new local wire, so the port `FCO` is undriven and
every carry is lost. `routed_cells.v` replaces the model with one that assigns the port. A
simulator that follows Verilog's scope rules would also lose the carry with yosys's model (not
tested).

`netlist/run.sh` synthesises the generated ring, places and routes it, and runs seven cases in
7 s. `slice/mutant_check.sh` runs it on `gen`. Each case gives its expected result:

| Case | Expected | Result |
|---|---|---|
| `synth_ecp5` netlist | Proved | Proved: 170 of 170 signals, 1.6 s |
| One LUT bit inverted after synthesis (reset never asserted) | Killed | Counterexample, cycle 2 |
| Routed netlist (nextpnr `--write`) | Proved | Proved: 146 of 146 signals, 1.6 s |
| Carry-generate bit of an adder cell inverted after routing | Killed | Counterexample, cycle 14 |
| Inputs of two flip-flops exchanged after routing | Killed | Counterexample, cycle 16 |
| Routed, with yosys's `TRELLIS_COMB` model | Killed | Counterexample, cycle 2 |
| Routed, with unconnected inputs read as 0 | Killed | Counterexample, cycle 17 |

The gap that remains is the last one: the routed netlist states which nets connect which pins, and
the bitstream sets the switches (PIPs) that make those connections. No tool here reads a bitstream
back into a netlist; Project Trellis's database could. The proof also assumes the cell models,
nextpnr's own netlist writer, and yosys's equivalence passes.

### The core

`netlist/core.sh` checks the core of the book (`build/rtl`, top `core_top`) the same way, module by
module, against the netlist that `prep; opt -full` makes. Both netlists keep the hierarchy
(`synth_ecp5 -noflatten`). `module_check.sh` makes each module's check combinational:

1. Each instance of another module becomes ports on both sides (`expose -evert`): its inputs are
   checked, and its outputs are shared.
2. Each flip-flop bit becomes a pair of ports (`evert_regs.py`): the state as an input, the next
   state as an output. Both sides name the ports after the gold netlist's register nets, so the
   ports pair by name, and `miter` refuses to run if any register is unpaired.
3. A one-step miter must give equal outputs and equal next state. From equal power-up states, this
   gives equal runs by induction.

yosys's own `equiv_induct` left 671 signals of the module `core` unproven, even against a netlist
with no optimisation, so the probe does not use it. All 3,403 register bits of `core` pair by name;
synthesis neither merges nor duplicates any.

SAT does not prove a multiplier: 15 minutes for part of one module. `cut_mul.py` cuts each `$mul`
into ports instead: its operands are checked, its product is shared, and both sides' multipliers
must have identical parameters after `opt -full; wreduce`. `mult18x18d.v` models the DSP block in
its combinational configuration only. yosys has no model of it; this one is trusted, like the
others.

| Case | Expected | Result |
|---|---|---|
| 21 modules (`core`, 3,403 flip-flops and 2,801 LUTs, the longest at 21 s) | Proved | Proved |
| `core_regfile` (two `DP16KD` block RAMs) | Open | Open: a memory needs its own argument |
| `core` with one LUT bit inverted | Killed | Counterexample |
| `core_mul_part` with two DSP operand bits exchanged | Killed | Counterexample |

The 24 cases take 27 s. They check `-noflatten` synthesis, which `make timing` does not use. With
3 seeds, out of context, at `core.clock` (85 MHz):

| Synthesis | Fmax (MHz) | Logic cells | Flip-flops |
|---|---|---|---|
| Flat (`make timing`) | 90.7, 91.4, 92.7 | 4,867 | 3,387 |
| `-noflatten` (checked) | 86.1, 88.9, 89.4 | 6,593 (+35%) | 3,481 |

Not yet tried for the core: the routed netlist, which needs models of nextpnr's packed RAM and DSP
cells, and the flat netlist.

## The earlier handoff

[`HANDOFF-2026-10-01.md`](HANDOFF-2026-10-01.md) records an earlier session's measurements of
Event-B's reading structure. Its rule `doc.dependencies-first` (commit `47670bc`) is not on this
branch, so its figures for the book describe another branch. Against its open questions:

| Question | Status |
|---|---|
| A bridge from the Verilog to the model ("the main risk") | Answered: the generated lowest machine (`gen/`, `slice/`), sound but not complete; at bit level (`bits/`) the control xor and the adder prove. The multiplier is not proved. The other candidate, Verilog generated from the model, works for the slice (`gen/eventb2v.py`), with the bridge as the check. |
| An analogue of mutants and of `doc.proof-meaning` | Answered for the slice: `slice/mutant_check.sh` kills a mutant only by a ProB counterexample, and a correct control is not killed |
| Headless Rodin in the toolchain | Answered: `rodin-app/`, with Z3 and cvc5 from the pinned nixpkgs. Rodin, the SMT plug-in and ProB are not yet pinned |
| `core.rotation` end to end | Answered by the slice: M0, M1, and M2 from `ring.v` |
| Live set with each event a section | Open: not measured on these models |
| Belief edges from proofs | Open: not measured; the all-hypotheses attempt of the build application overstates them |
| A stamp that ties the English to the formulas | Open |
| Whether proofs and generated machines count toward audit time | Open |

## Open questions

1. Non-interference: a property of two runs, so it needs a self-composed machine.
2. The multiplier. The plug-in declares a linear logic (`AUFLIA`), in which Z3 and cvc5 reject any
   product of two variables without trying it. cvc5 now runs with `--force-logic=ALL` by default
   and tries them; Z3 has no such option, so cvc5 is the one solver for products. With it, cvc5
   proves small nonlinear steps, such as `Σ_j (b(j) ∗ a) ∗ 2^j = a ∗ b` at 32 bits in under 1 s,
   but not `a ∗ b` against hundreds of gate bits in one goal: a multiplier needs refinement steps.
3. A whole chapter: audit time (the hand-written machines count, the generated ones are tool
   output), the live set with event-level sections, and the belief edges from `prHyps`. A solver
   records every hypothesis it was given, so a proof with all hypotheses inflates that measure.
4. Pinning: Rodin, the SMT plug-in and ProB are downloads, not Nix packages yet.
5. Bitvectors: Event-B has no bitvector type, and the SMT plug-in sends only integer logic
   (`AUFLIA`, `QF_AUFLIA`), so Z3 and cvc5 never use their bitvector solvers. Bits are integers,
   and the bit-level goals (Shift `sll`, `FieldInt` extract, `DecodeInt` decode) are the slowest.
   Watch them as the models grow towards a chapter.

## Pitfalls met

* An `isIdle` wait for Eclipse's jobs never ends; Eclipse always has background jobs.
* A null progress monitor fails in the tactics; pass `NullProgressMonitor`.
* An abstract parameter that a refinement drops gets the witness `⊤` unless the generator gives one.
* An `INITIALISATION` cannot read variables: write power-up as `:∈`, with witnesses from the gluing.
* A range bound such as `4294967295` overflows `int`; compare bounds as `BigInteger`.
* ProB on SWI-Prolog does not honour its own `TIME_OUT`; wrap it in `timeout`.

## Files

| Path | Holds |
|---|---|
| `rodin-app/` | The build application |
| `gen/` | The XML writer, the bridge, the generators of the probe models, and `eventb2v.py`, which writes Verilog from a machine; `replay.py` replays measured attempts under other orders |
| `models/` | The sources (`.bum`, `.buc`) of six of the seven probe models; `BridgeAluGates` regenerates with `alu/netlists.sh` and `gen/bridge_alu_split.py` |
| `alu/` | The 16 wrappers, the ALU variants of the mutant check, and `netlists.sh` |
| `slice/` | `ring.v`, `spec.py` (M0, M1), `gen.py` (M2), the mutants, and `mutant_check.sh`, which runs the whole slice and the mutant check |
| `prob/` | `po_extract.py` and the SMT debug options |
| `netlist/` | The check below the bridge: `check.sh`, `powerup.py`, `routed_cells.v` (the trusted models of the routed cells), `mutate.py` and `run.sh`; for the core, `core.sh`, `module_check.sh`, `evert_regs.py`, `cut_mul.py` and `mult18x18d.v` |
| `bits/` | The bit-level probe: `netlists.sh` (yosys `techmap`), `ripple.v` (the ripple carry map) and `gen_bits.py` (the lowest machines) |
| `reports/` | The CSV reports and verdicts quoted above |
| `HANDOFF-2026-10-01.md` | The earlier handoff on Event-B's reading structure, as received |
