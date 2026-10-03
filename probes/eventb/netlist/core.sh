#!/usr/bin/env bash
# core.sh RTL WORK: check the ECP5 netlist of the core, module by module, against the netlist that
# prep makes. RTL is the tangled RTL of the book (build/rtl); top module core_top. Both netlists
# keep the hierarchy (synth_ecp5 -noflatten). Each module is checked by module_check.sh, the
# multiplier with its products cut, and the register file by regfile_check.sh; then four seeded
# faults must each give a counterexample. Exits 1
# unless every case gives its expected result. Run it under ./dev (yosys).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rtl=$1 work=$2
mkdir -p "$work"
src="$(find "$rtl" -name '*.sv' | sort | tr '\n' ' ') $(find "$rtl" -name '*.v' | sort | tr '\n' ' ')"
yosys -q -p "read_verilog -sv $src; prep -top core_top; opt -full; dffunmap; opt_clean; write_json $work/gold.json" > "$work/gold.log" 2>&1
yosys -q -p "read_verilog -sv $src; synth_ecp5 -noflatten -top core_top -json $work/gate.json" > "$work/gate.log" 2>&1
python3 "$here/mutate.py" lut4 "$work/gate.json" "$work/gate_lut.json" core
python3 "$here/mutate.py" dsp-swap "$work/gate.json" "$work/gate_dsp.json" core_mul_part
python3 "$here/mutate.py" ram-swap "$work/gate.json" "$work/gate_ram.json" core_regfile
python3 "$here/mutate.py" lut4 "$work/gate.json" "$work/gate_rflut.json" core_regfile
modules=$(python3 -c "import json, sys; print(' '.join(sorted(json.load(open(sys.argv[1]))['modules'])))" "$work/gold.json")
start=$SECONDS
{
    for m in $modules; do echo "$m $work/gate.json $m proved"; done
    echo "core $work/gate_lut.json core_lut killed"
    echo "core_mul_part $work/gate_dsp.json core_mul_part_dsp killed"
    echo "core_regfile $work/gate_ram.json core_regfile_ram killed"
    echo "core_regfile $work/gate_rflut.json core_regfile_lut killed"
} | xargs -P "${JOBS:-3}" -L 1 sh -c '
    m=$0 gate=$1 name=$2 want=$3
    cut=0; [ "$m" = core_mul_part ] && cut=1
    check=module_check.sh; [ "$m" = core_regfile ] && check=regfile_check.sh
    got=$(CUT_MUL=$cut bash "'"$here"'/$check" "'"$work"'/gold.json" "$gate" "$m" "'"$work"'/$name")
    printf "%-20s expected %-7s got %s\n" "$name" "$want" "${got#*: }"' | sort > "$work/results.txt"
cat "$work/results.txt"
echo "$(wc -l < "$work/results.txt") cases in $((SECONDS - start)) s"
! awk '{ split($0, f, "got "); if (index(f[2], $3) != 1) bad = 1 } END { exit !bad }' "$work/results.txt"
