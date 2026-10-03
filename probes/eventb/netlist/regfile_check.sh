#!/usr/bin/env bash
# regfile_check.sh GOLD.json GATE.json core_regfile OUT: check the core's register file, whose two
# memories synthesis maps to DP16KD block RAMs with a delayed write and forwarding logic. The third
# argument is fixed; it keeps the arguments of module_check.sh. Both memories become flip-flops
# (memory_map; the RAM through the trusted model dp16kd.v), every flip-flop becomes ports
# (state_ports.py), and regfile_relation.py writes a one-step check of the relation between the two
# states. ABC (iprove) proves its output "bad" constant 0. Prints "core_regfile: proved", "killed"
# (ABC finds an assignment) or "open: why".
set -u
here=$(cd "$(dirname "$0")" && pwd)
gold=$1 gate=$2 out=$4 m=core_regfile
yosys -q -p "read_json $gold; hierarchy -top $m; memory_map; opt_clean; write_json $out.gold_mm.json" > "$out.log" 2>&1 &&
yosys -q -p "read_json $gate; delete =A:blackbox; read_verilog -DNO_INCLUDES +/ecp5/cells_sim.v; read_verilog -overwrite $here/dp16kd.v;
  hierarchy -top $m; proc; flatten -wb; proc; opt_clean; memory -nomap; opt -full; dffunmap; opt_clean; memory_map; opt_clean;
  write_json $out.gate_mm.json" >> "$out.log" 2>&1 || { echo "$m: open: yosys failed ($out.log)"; exit 0; }
python3 "$here/state_ports.py" "$out.gold_mm.json" $m "$out.gold_ev.json" gold_ev > "$out.gold_ports.json" 2>> "$out.log" &&
python3 "$here/state_ports.py" "$out.gate_mm.json" $m "$out.gate_ev.json" gate_ev > "$out.gate_ports.json" 2>> "$out.log" &&
python3 "$here/regfile_relation.py" "$out.gold_ports.json" "$out.gate_ports.json" "$out.check.v" 2>> "$out.log" ||
  { echo "$m: open: $(tail -1 "$out.log")"; exit 0; }
yosys -q -p "read_json $out.gold_ev.json; read_json $out.gate_ev.json; read_verilog $out.check.v; hierarchy -top rf_check;
  flatten; opt -fast; techmap; opt -fast; aigmap; opt_clean; write_aiger -zinit $out.aig" >> "$out.log" 2>&1 ||
  { echo "$m: open: yosys failed ($out.log)"; exit 0; }
yosys-abc -c "read_aiger $out.aig; strash; iprove" > "$out.abc" 2>&1
case $(grep -oE '(UN)?SATISFIABLE|UNDECIDED' "$out.abc" | tail -1) in
  UNSATISFIABLE) echo "$m: proved" ;;
  SATISFIABLE) echo "$m: killed" ;;
  *) echo "$m: open: ABC did not decide ($out.abc)" ;;
esac
