#!/usr/bin/env bash
# module_check.sh GOLD.json GATE.json MODULE OUT: check one module of a hierarchical ECP5 netlist
# (GATE, from synth_ecp5 -noflatten) against the same module of GOLD (prep, not flattened).
# On both sides each instance of another module of the design becomes ports (its inputs to check,
# its outputs shared), and each flip-flop bit becomes a pair of ports (evert_regs.py), so that one
# step of a miter is one cycle: equal state and inputs must give equal next state and outputs. With
# CUT_MUL=1, each multiplier becomes ports as well (cut_mul.py), and the two sides' multipliers must
# have the same parameters. Prints "MODULE: proved", "killed" (a counterexample) or "open: why".
set -u
here=$(cd "$(dirname "$0")" && pwd)
gold=$1 gate=$2 m=$3 out=$4
others=$(python3 -c "import json, sys; print(' '.join(n for n in json.load(open(sys.argv[1]))['modules'] if n != sys.argv[2]))" "$gold" "$m")
cut=""; [ "${CUT_MUL:-0}" = 1 ] && cut="opt -full; wreduce; opt -full;"
instances=$(for o in $others; do printf 't:%s ' "$o"; done)
yosys -q -p "read_json $gold; blackbox $others; hierarchy -top $m; $cut expose -evert $instances; opt_clean; write_json $out.gold.json" > "$out.log" 2>&1 &&
yosys -q -p "read_json $gate; delete =A:blackbox; blackbox $others; read_verilog -DNO_INCLUDES +/ecp5/cells_sim.v;
  read_verilog -overwrite $here/mult18x18d.v; hierarchy -top $m; proc; flatten -wb; proc; $cut
  expose -evert $instances; opt_clean; write_json $out.gate.json" >> "$out.log" 2>&1 ||
  { echo "$m: open: yosys failed ($out.log)"; exit 0; }
for side in gold gate; do
  python3 "$here/evert_regs.py" "$gold" "$out.$side.json" "$m" "$out.$side.json" >> "$out.log" 2>&1 ||
    { echo "$m: open: $(tail -1 "$out.log")"; exit 0; }
  if [ -n "$cut" ]; then
    python3 "$here/cut_mul.py" "$out.$side.json" "$m" "$out.$side.json" > "$out.$side.cuts" 2>> "$out.log" ||
      { echo "$m: open: $(tail -1 "$out.log")"; exit 0; }
  fi
done
[ -z "$cut" ] || cmp -s "$out.gold.cuts" "$out.gate.cuts" || { echo "$m: open: the multipliers differ"; exit 0; }
yosys -p "read_json $out.gold.json; rename $m gold; design -stash g; read_json $out.gate.json; rename $m gate; design -stash t;
  design -copy-from g -as gold gold; design -copy-from t -as gate gate;
  miter -equiv -flatten -make_outputs gold gate miter; hierarchy -top miter;
  sat -verify -prove trigger 0 -timeout ${LIMIT:-600} miter" >> "$out.log" 2>&1
case $(grep -o 'SAT proof finished - [a-z ]*' "$out.log" | tail -1) in
  *"no model found"*) echo "$m: proved" ;;
  *"model found"*) echo "$m: killed" ;;
  *) echo "$m: open: $(grep -m1 -E 'ERROR|timeout' "$out.log")" ;;
esac
