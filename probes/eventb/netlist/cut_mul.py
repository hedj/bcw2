"""cut_mul.py IN.json MODULE OUT.json: replace each $mul cell of MODULE whose product drives an output
port P by ports: "a:P" and "b:P" (its operands, outputs to check) and "y:P" (its product, an input
shared with the other side). Prints each cut's parameters, which must match across gold and gate:
then equal operands into equal multipliers give equal products, and the miter checks only operands."""
import json
import sys

src, module, dst = sys.argv[1:]
design = json.load(open(src))
m = design["modules"][module]
port_of = {}
for name, p in m["ports"].items():
    if p["direction"] == "output":
        for b in p["bits"]:
            port_of[b] = name
cuts = {}
for cname, c in list(m["cells"].items()):
    if c["type"] != "$mul":
        continue
    owners = {port_of.get(b) for b in c["connections"]["Y"] if isinstance(b, int)}
    if len(owners) != 1 or None in owners:
        raise SystemExit(f"{cname}: its product does not drive exactly one output port ({owners})")
    port = owners.pop()
    if port in cuts:
        raise SystemExit(f"two multipliers drive {port}")
    params = {k: int(v, 2) for k, v in c["parameters"].items()}
    cuts[port] = params
    m["ports"][f"a:{port}"] = {"direction": "output", "bits": c["connections"]["A"]}
    m["ports"][f"b:{port}"] = {"direction": "output", "bits": c["connections"]["B"]}
    m["ports"][f"y:{port}"] = {"direction": "input", "bits": c["connections"]["Y"]}
    del m["cells"][cname]
json.dump(design, open(dst, "w"))
print(json.dumps(cuts, sort_keys=True))
