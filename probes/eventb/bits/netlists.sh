#!/usr/bin/env bash
# The bit-blasted netlists of the probe: yosys techmap maps each word-level cell to single-bit gates.
# The default map gives the adder a Brent-Kung carry tree; ripple.v gives it a ripple chain.
#
# Usage, from the root of the repository: probes/eventb/bits/netlists.sh RTL OUT
#   RTL  the tangled RTL of the book (build/rtl)
#   OUT  the directory for the netlists
set -eu
here=$(cd "$(dirname "$0")" && pwd); alu=$here/../alu
rtl=$1; out=$2
mkdir -p "$out"
net() {   # net NAME CORE_ALU F_T MAPS
    ./dev sh -c "yosys -q -p 'read_verilog -sv $2 $alu/alu_$3.v; prep -top alu_$3 -flatten; opt -full; techmap $4; opt -full; opt_clean; write_json $out/$1.json'"
}
net ctl_xor_4_0 "$alu/ctl_xor/core_alu.v" 4_0 ""
net ctl_xor_4_1 "$alu/ctl_xor/core_alu.v" 4_1 ""
net book_0_0 "$rtl/core/core_alu.v" 0_0 ""
net ripple_0_0 "$rtl/core/core_alu.v" 0_0 "-map $here/ripple.v -map +/techmap.v"
