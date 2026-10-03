#!/usr/bin/env bash
# check.sh GOLD.json GATE.json OUT: prove the ECP5 netlist GATE equivalent to the netlist GOLD that
# the bridge reads, by induction over the signals they share; then search 20 cycles for a
# counterexample from GATE's power-up state, which GOLD (any power-up state) may also take. MODELS
# names Verilog models that replace cells of yosys's ECP5 library; EXTRA, yosys commands to run on
# GATE after flattening.
set -eu
gold=$1 gate=$2 out=$3
models=${MODELS:+read_verilog -overwrite $MODELS;}
yosys -q -p "read_json $gate; delete =A:blackbox; read_verilog -DNO_INCLUDES +/ecp5/cells_sim.v; $models
  hierarchy -auto-top; rename -top ring; proc; flatten -wb; proc; ${EXTRA:-} opt_clean; splitnets;
  select -assert-none t:\$paramod* t:CCU2C t:LUT4 t:TRELLIS_FF t:TRELLIS_COMB t:TRELLIS_IO t:DCCA; write_json $out.flat.json" > $out.flat.log 2>&1 \
  || { echo "flatten failed: $out.flat.log"; exit 2; }
powerup=$(python3 "$(dirname "$0")/powerup.py" "$gold" "$out.flat.json")
load="read_json $gold; rename ring gold; $powerup splitnets; design -stash gold_d; read_json $out.flat.json; rename ring gate;
  design -stash gate_d; design -copy-from gold_d -as gold gold; design -copy-from gate_d -as gate gate"
yosys -p "$load; equiv_make gold gate equiv; hierarchy -top equiv; equiv_simple -seq 2; equiv_induct -seq 2; equiv_status -assert" > $out.equiv.log 2>&1 \
  && echo "proof: equivalent" || echo "proof: not proved ($(grep -o '[0-9]* are unproven' $out.equiv.log | tail -1))"
yosys -p "$load; miter -equiv -flatten -make_outputs gold gate miter; hierarchy -top miter;
  sat -verify -seq 20 -prove trigger 0 -show-inputs -show-outputs miter" > $out.sat.log 2>&1 \
  && echo "search: no counterexample in 20 cycles" \
  || echo "search: counterexample, first at cycle $(grep -E '^ +[0-9]+ +.trigger +1' $out.sat.log | head -1 | awk '{print $1}')"
