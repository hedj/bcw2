#!/usr/bin/env bash
# run.sh GOLD.json RTL.v WORK: synthesise RTL (top module ring) for the ECP5, place and route it,
# and check each netlist against GOLD, the netlist that the bridge read. Then check that the check
# finds each seeded fault and each wrong cell model. Exits 1 unless every case gives its expected
# result: "proved" (equivalent, no counterexample) or "killed" (a counterexample).
# Run it under ./dev, which gives yosys and nextpnr-ecp5.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
gold=$1 rtl=$2 work=$3
mkdir -p "$work"
yosys -q -p "read_verilog -sv $rtl; synth_ecp5 -top ring -json $work/synth.json" > "$work/synth.log" 2>&1
nextpnr-ecp5 --25k --package CABGA256 --json "$work/synth.json" --placer static --seed 1 \
    --write "$work/routed.json" --log "$work/pnr.log" > /dev/null 2>&1
python3 "$here/mutate.py" synth-lut "$work/synth.json" "$work/synth_lut.json"
python3 "$here/mutate.py" routed-carry "$work/routed.json" "$work/routed_carry.json"
python3 "$here/mutate.py" routed-swap "$work/routed.json" "$work/routed_swap.json"
sed '/^\/\/ yosys.s TRELLIS_COMB/,$d' "$here/routed_cells.v" > "$work/yosys_comb.v"
failures=0
check() {   # name expected netlist models extra
    local result out
    out=$(MODELS=$4 EXTRA=$5 bash "$here/check.sh" "$gold" "$work/$3.json" "$work/$1")
    case $out in
        *"proof: equivalent"*"no counterexample"*) result=proved ;;
        *"counterexample, first"*) result="killed (cycle ${out##*cycle })" ;;
        *) result="neither: $out" ;;
    esac
    [ "${result%% *}" = "$2" ] || failures=$((failures + 1))
    printf '%-14s expected %-7s got %s\n' "$1" "$2" "$result"
}
routed=$here/routed_cells.v high="setundef -undriven -one;"
check synth        proved synth        ""           ""
check synth_lut    killed synth_lut    ""           ""
check routed       proved routed       "$routed"    "$high"
check routed_carry killed routed_carry "$routed"    "$high"
check routed_swap  killed routed_swap  "$routed"    "$high"
check yosys_comb   killed routed       "$work/yosys_comb.v" "$high"
check tie_low      killed routed       "$routed"    "setundef -undriven -zero;"
[ $failures = 0 ]
