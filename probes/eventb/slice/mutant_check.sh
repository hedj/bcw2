#!/usr/bin/env bash
# The slice and its mutant check, from the RTL to the verdicts.
#
# For the ring, for each variant and for the ring that eventb2v.py writes from M1: yosys writes the
# netlist, gen.py writes the machines M0, M1 and M2, and Rodin (with the bcw.rodin bundle) proves
# them. ProB then looks for a counterexample to each obligation left open. A variant is killed only
# if ProB finds one.
#
# Environment (no defaults; each must name an existing directory or file):
#   RODIN  the Rodin 3.10 directory, with the SMT Solvers plug-in and dropins/bcw.rodin_1.0.0.jar
#   JDK    a Java 21 home for Rodin
#   PROB   the ProB source directory, with lib/probcliparser.jar built
#   SWI    a SWI-Prolog 10 installation (its bin/ holds swipl)
#   RTL    the tangled RTL of the book (build/rtl of a worktree after make)
#   WORK   an empty directory for the models, the netlists and the reports
#   Z3     a Z3 4.16 binary, and CVC5 a cvc5 1.4 binary, as in the pinned nixpkgs: the default solvers
# Run it from the root of the repository, so that ./dev gives yosys.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
for v in RODIN JDK PROB SWI RTL WORK Z3 CVC5; do [ -e "${!v}" ] || { echo "$v: no such path: ${!v}" >&2; exit 2; }; done
variants="ring wrap6 wrongrec reset control"
for m in $variants; do
    src=$here/ring.v; rot=$RTL/core/core_rotate.v
    [ $m != ring ] && src=$here/mutants/ring_$m.v
    [ $m = wrap6 ] && rot=$here/mutants/core_rotate_wrap6.v
    ./dev sh -c "yosys -q -p 'read_verilog -sv $RTL/bcw_params.sv $rot $src; prep -top ring -flatten; opt -full; dffunmap; opt_clean; write_json $WORK/ring_$m.json'"
    python3 "$here/gen.py" "$WORK/models" "$WORK/ring_$m.json" "Slice_$m"
done
# The variant gen is the ring that eventb2v.py writes from M1; like ring, it must prove.
mkdir -p "$WORK/gen"
python3 "$here/../gen/eventb2v.py" "$WORK/models/Slice_ring/M1.bum" ring > "$WORK/gen/ring.v"
./dev verilator --lint-only -Wall "$WORK/gen/ring.v"
./dev sh -c "yosys -q -p 'read_verilog -sv $WORK/gen/ring.v; prep -top ring -flatten; opt -full; dffunmap; opt_clean; write_json $WORK/ring_gen.json'"
python3 "$here/gen.py" "$WORK/models" "$WORK/ring_gen.json" Slice_gen
variants="$variants gen"
# The netlists that synthesis and place and route make of gen must equal the one the bridge read.
./dev sh -c "bash $here/../netlist/run.sh $WORK/ring_gen.json $WORK/gen/ring.v $WORK/netlist"
start=$SECONDS
"$JDK/bin/java" -Xmx4g -Dbcw.z3new="$Z3" -Dbcw.cvc5="$CVC5" -Dbcw.report="$WORK/rodin.csv" -Dstdout.encoding=UTF-8 --add-modules=ALL-SYSTEM \
    -jar "$RODIN"/plugins/org.eclipse.equinox.launcher_*.jar -clean -nosplash -data "$WORK/workspace" \
    -application bcw.rodin.build $(for m in $variants; do echo "$WORK/models/Slice_$m"; done) > "$WORK/rodin.raw" 2>&1 || true
echo "rodin: $((SECONDS - start)) s"
cd "$PROB" && export PATH=$SWI/bin:$JDK/bin:$PATH PROLOG_SYSTEM=swi LANG=C.UTF-8 LC_ALL=C.UTF-8
: > "$WORK/prob.csv"
grep ',open,' "$WORK/rodin.csv" | cut -d, -f1 | while read -r po; do
    project=${po%%/*}; rest=${po#*/}; machine=${rest%%/*}; name=${rest#*/}
    f=$WORK/$(echo "$po" | tr "/'" "__").txt
    python3 "$here/../prob/po_extract.py" "$WORK/models/$project/$machine.bpo" "$name" > "$f" 2>/dev/null
    begin=$SECONDS; code=0; timeout 120 ./probcli_src.sh -p TIME_OUT 100000 -eval_file "$f" > "$f.out" 2>&1 || code=$?
    verdict=$(grep -oE 'Evaluation results: \[[A-Z ]+' "$f.out" | tail -1 | sed 's/.*\[//')
    [ $code = 124 ] && verdict="NO ANSWER (timeout)"
    echo "$po,${verdict:-none},$((SECONDS - begin))" >> "$WORK/prob.csv"
done
echo "prob: done"
