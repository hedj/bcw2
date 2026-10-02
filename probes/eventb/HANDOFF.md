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
seeded faults with a concrete counterexample, and kept a correct variant.

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
| SMT Solvers plug-in | 1.5.0, `https://rodin-b-sharp.sourceforge.net/updates/Plugin_SMT_Solvers/1.5.0`, installed by p2 director: `-installIU org.eventb.smt.feature.group,org.eventb.smt.verit.feature.group,org.eventb.smt.cvc4.feature.group,org.eventb.smt.z3.feature.group` | Bundles veriT, CVC3, CVC4 and Z3 4.5 |
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
2. Z3 alone on the selected hypotheses for 0.7 s (`bcw.first`). It closes most goals.
3. A contest of two searches at once, each on its own copy of the goal. The first proof is
   grafted onto the goal by `ProofBuilder.reuse`, and the other search stops:
   * the sets: all four solvers at once on the goal alone, then on the selected hypotheses,
     then on all of them, 6 s each (`bcw.timeout`);
   * the split, for a variable in the goal that a hypothesis bounds to at most 8 values
     (`bcw.split`): Rodin's case rule (`Tactics.doCase`) for each value, Rodin's tactics on each
     case, Z3 for 0.7 s on the selected hypotheses and then on all, and then the sets.
4. The obligations of a file are proved 4 at once (`bcw.jobs`). Attempts are created, committed
   and disposed one at a time.

Other properties: `bcw.report` (CSV: obligation, result, ms, closers), `bcw.baseline` (an earlier
report; prints LOST and SLOWER), `bcw.measure` (each solver in turn on each goal, timed), and
`bcw.solvers` (default `Z3,CVC3,CVC4,veriT`). The exit status is 1 if an obligation stays open.

Each solver call writes its own temporary file and reads its own process's output, so parallel
calls cannot read each other's answers.

## The bridge from Verilog to the lowest machine (`gen/`)

yosys `prep -flatten; opt -full` (and `dffunmap; opt_clean` for registers), then `write_json`.
`bridge2.py` and `bridge_seq.py` translate the netlist; a generator writes the lowest machine,
which refines a hand-written machine, and Rodin proves the refinement.

| Rule | Translation |
|---|---|
| Choice, `$mux`, compare | `({TRUE ↦ x, FALSE ↦ y})(bool(c))` |
| `$add`, `$sub` of width w | The choice that adds or subtracts `2^w` on overflow |
| `$and`, `$or`, `$xor` | Gate parameters in 0 ‥ 1 with linear constraints (the `GATES` table); xor has an AND term `t` |
| `$pmux` | A one-hot side condition |
| `$shl`, `$shr`, `$sshr` | A case table over the shift amount |
| `$scopeinfo` | Skipped |
| `$dff` | Each named wire that registers drive is a state variable; its D input is its next value. One event for each value of the reset input; at power-up each register takes any value of its width |
| A gate the netlist lacks | The witness is the value that the specification gives it; without one, Rodin's default witness `⊤` makes the obligation false for any netlist |

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
was neither proved nor killed: the bridge is sound but not complete.

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
only CVC3 and CVC4 prove (`RotLaps/M1/wrap/glue/INV`) CVC3 proves alone. So on the measured goals,
Z3, CVC3 and veriT prove all that the four solvers prove.

## Open questions

1. Non-interference: a property of two runs, so it needs a self-composed machine.
2. The multiplier: products are nonlinear for the open solvers.
3. A whole chapter: audit time (the hand-written machines count, the generated ones are tool
   output), the live set with event-level sections, and the belief edges from `prHyps`. A solver
   records every hypothesis it was given, so a proof with all hypotheses inflates that measure.
4. Pinning: Rodin, the SMT plug-in and ProB are downloads, not Nix packages yet.

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
| `gen/` | The XML writer, the bridge, and the generators of the probe models; `replay.py` replays measured attempts under other orders |
| `models/` | The sources (`.bum`, `.buc`) of six of the seven probe models; `BridgeAluGates` regenerates with `alu/netlists.sh` and `gen/bridge_alu_split.py` |
| `alu/` | The 16 wrappers, the ALU variants of the mutant check, and `netlists.sh` |
| `slice/` | `ring.v`, `spec.py` (M0, M1), `gen.py` (M2), the mutants, and `mutant_check.sh`, which runs the whole slice and the mutant check |
| `prob/` | `po_extract.py` and the SMT debug options |
| `reports/` | The CSV reports and verdicts quoted above |
