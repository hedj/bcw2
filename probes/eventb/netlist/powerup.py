"""powerup.py GOLD.json GATE_FLAT.json: a yosys setattr for each register of GOLD (the netlist the
bridge reads, which may power up in any state) that gives it GATE's power-up value, bit by bit.
A register bit that GATE does not have, or has without a power-up value, is an error."""
import json
import sys

gold = json.load(open(sys.argv[1]))["modules"]["ring"]
gate = json.load(open(sys.argv[2]))["modules"]["ring"]["netnames"]
init = {}
for wire in gate.values():
    for bit, value in zip(wire["bits"], reversed(wire["attributes"].get("init", ""))):
        init[bit] = value


def gate_bits(name, width):
    """GATE's bits of the register name: a word, or bits named name[i] as nextpnr writes them."""
    if name in gate:
        return gate[name]["bits"]
    return [gate[f"{name}[{i}]"]["bits"][0] if f"{name}[{i}]" in gate else None for i in range(width)]


q_bits = {b for c in gold["cells"].values() if c["type"] == "$dff" for b in c["connections"]["Q"]}
for name, wire in sorted(gold["netnames"].items()):
    if wire["hide_name"] or not q_bits.intersection(wire["bits"]):
        continue
    bits = gate_bits(name, len(wire["bits"]))
    if any(b not in init for b in bits):
        raise SystemExit(f"{name}: the gate netlist has no power-up value for every bit")
    print(f"setattr -set init {len(bits)}'b{''.join(init[b] for b in reversed(bits))} gold/w:{name};")
