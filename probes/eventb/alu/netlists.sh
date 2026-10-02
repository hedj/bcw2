#!/usr/bin/env bash
# The netlists of core_alu for each (f3, alt): yosys propagates the constants of a wrapper alu_F_T.v,
# so that each netlist holds one operation. The recipe reproduces the netlist that the probe proved.
#
# Usage, from the root of the repository: probes/eventb/alu/netlists.sh RTL CORE_ALU OUT
#   RTL       the tangled RTL of the book (build/rtl)
#   CORE_ALU  core_alu.v to use: RTL/core/core_alu.v, or one of mut_sub, mut_xor, ctl_xor/core_alu.v
#   OUT       the directory for alu_F_T.json
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rtl=$1; alu=$2; out=$3
mkdir -p "$out"
for f in 0 1 2 3 4 5 6 7; do
    for t in 0 1; do
        ./dev sh -c "yosys -q -p 'read_verilog -sv $alu $here/alu_${f}_${t}.v; prep -top alu_${f}_${t} -flatten; opt -full; write_json $out/alu_${f}_${t}.json'"
    done
done
