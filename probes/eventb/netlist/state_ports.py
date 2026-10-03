"""state_ports.py IN.json MODULE OUT.json NAME: MODULE of IN, renamed NAME, with every $dff replaced by
ports: "q:<net>" (the state, an input) and "d:<net>" (the next state, an output), one pair for each
named net made only of flip-flop outputs, else one pair for each remaining bit ("q:bit<id>").
Writes OUT, and prints a JSON map from each flip-flop output bit, named "<port>/<index>", to the
input port bit that feeds its D directly, if any (so that a caller can find delayed inputs)."""
import json
import sys

src, module, dst, name = sys.argv[1:]
design = json.load(open(src))
m = design["modules"][module]
dffs = [c for c in m["cells"].values() if c["type"] == "$dff"]
if any(c["type"].startswith("$") and "ff" in c["type"] and c["type"] != "$dff" for c in m["cells"].values()):
    raise SystemExit("flip-flops of another kind")
clocks = {tuple(c["connections"]["CLK"]) for c in dffs}
if len(clocks) > 1:
    raise SystemExit(f"{len(clocks)} clocks: one step of the check would not be one cycle")
d_of = {}
for c in dffs:
    for q, d in zip(c["connections"]["Q"], c["connections"]["D"]):
        d_of[q] = d
port_in = {b: f"{n}[{i}]" for n, p in m["ports"].items() if p["direction"] == "input" for i, b in enumerate(p["bits"])}
taken, ports, fed = set(), {}, {}
for net in sorted(m["netnames"]):
    w = m["netnames"][net]
    bits = w["bits"]
    if w["hide_name"] or not bits or not all(isinstance(b, int) and b in d_of and b not in taken for b in bits):
        continue
    taken |= set(bits)
    ports[net] = bits
for b in sorted(set(d_of) - taken):
    ports[f"bit{b}"] = [b]
for net, bits in ports.items():
    m["ports"][f"q:{net}"] = {"direction": "input", "bits": bits}
    m["ports"][f"d:{net}"] = {"direction": "output", "bits": [d_of[b] for b in bits]}
    for i, b in enumerate(bits):
        if d_of[b] in port_in:
            fed[f"{net}/{i}"] = port_in[d_of[b]]
for n in [n for n, c in m["cells"].items() if c["type"] == "$dff"]:
    del m["cells"][n]
design["modules"] = {name: m}
json.dump(design, open(dst, "w"))
print(json.dumps({"widths": {n: len(b) for n, b in ports.items()}, "fed": fed}))
