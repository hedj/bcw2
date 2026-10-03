"""evert_regs.py GOLD.json IN.json MODULE OUT.json: replace each flip-flop bit of MODULE in IN by an
input port "q:<reg>[i]" (its state) and an output port "d:<reg>[i]" (its next state). <reg> is a
net of GOLD's MODULE made only of register bits; each bit takes the least such name that holds it.
The same rule on gold and gate gives ports that a miter pairs by name; a flip-flop bit with no such
name, or two bits with one name, is an error. Clocks are dropped: one step of the miter is one cycle."""
import json
import sys

gold_path, in_path, module, out_path = sys.argv[1:]
FF = {"$dff"}
OTHER_FF = {"$adff", "$sdff", "$dffe", "$sdffe", "$sdffce", "$adffe", "$aldff", "$aldffe", "$dffsr", "$dffsre", "$dlatch", "$adlatch"}


def register_names(m):
    q = {b for c in m["cells"].values() if c["type"] in FF for b in c["connections"]["Q"]}
    return {n for n, w in m["netnames"].items() if not w["hide_name"] and w["bits"] and set(w["bits"]) <= q}


gold = json.load(open(gold_path))["modules"][module]
allowed = register_names(gold)
design = json.load(open(in_path))
m = design["modules"][module]
others = sorted({c["type"] for c in m["cells"].values() if c["type"] in OTHER_FF or c["type"].startswith(("$_DFF", "$_SDFF", "$_ALDFF", "$_DLATCH"))})
if others:
    raise SystemExit(f"{module}: flip-flops of kinds this script does not turn into ports: {others}")
label = {}   # bit -> canonical name
for name in sorted(allowed, reverse=True):          # the least name is written last and wins
    if name in m["netnames"]:
        for i, b in enumerate(m["netnames"][name]["bits"]):
            if isinstance(b, int):
                label[b] = f"{name}[{i}]"
ports, used, problems = {}, {}, []
for cname, c in list(m["cells"].items()):
    if c["type"] not in FF:
        continue
    for qb, db in zip(c["connections"]["Q"], c["connections"]["D"]):
        name = label.get(qb)
        if name is None:
            problems.append(f"no register name for bit {qb} of {cname}")
            continue
        if name in used:
            problems.append(f"{name} names two flip-flop bits ({used[name]}, {cname})")
            continue
        used[name] = cname
        ports[f"q:{name}"] = {"direction": "input", "bits": [qb]}
        ports[f"d:{name}"] = {"direction": "output", "bits": [db]}
    del m["cells"][cname]
if problems:
    raise SystemExit(f"{len(problems)} problems, e.g. " + "; ".join(problems[:5]))
m["ports"].update(ports)
json.dump(design, open(out_path, "w"))
print(f"{module}: {len(used)} register bits everted")
