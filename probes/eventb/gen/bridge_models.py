import sys
from pathlib import Path
import bridge
import rodin_xml as rx
root, netlists, suffix = sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else ""
B = lambda c: f"({{TRUE ↦ 1, FALSE ↦ 0}})(bool({c}))"

MODULES = {
    "core_rotate": dict(
        context=[("rotation", "rotation = (λi·i ∈ 0 ‥ 6 ∣ i + 1) ∪ {7 ↦ 0}", False),
                 ("rotation_type", "rotation ∈ 0 ‥ 7 → 0 ‥ 7", True)],
        constants=["rotation"],
        outputs={"next": "0 ‥ 7"}, assume=["turn ∈ 0 ‥ 7"], spec={"next": "rotation(turn)"}),
    "core_region": dict(
        context=[], constants=[],
        outputs={"out": "0 ‥ 1"},
        assume=["offset ∈ 0 ‥ 4294967295", "size ∈ 1 ‥ 7", "bound ∈ 0 ‥ 131071"],
        spec={"out": B("¬ (offset ‥ offset + size − 1 ⊆ 0 ‥ bound − 1)")}),
}

for top, m in MODULES.items():
    name = top.replace("core_", "Bridge_").title().replace("_", "") + suffix
    d = rx.project(root, name)
    sees = None
    if m["context"]:
        ctx = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
               '<org.eventb.core.contextFile org.eventb.core.configuration="org.eventb.core.fwd" version="3">']
        ctx += [f'<org.eventb.core.constant name="c{i}" {rx.a(identifier=c)}/>' for i, c in enumerate(m["constants"])]
        ctx += [f'<org.eventb.core.axiom name="x{i}" {rx.a(label=l, predicate=p)}' + (' org.eventb.core.theorem="true"' if t else '') + '/>'
                for i, (l, p, t) in enumerate(m["context"])]
        (d / "C0.buc").write_text("\n".join(ctx + ["</org.eventb.core.contextFile>"]) + "\n")
        sees = "C0"
    inputs, rtl = bridge.translate(netlists / f"{top}.json", top)
    outs = list(m["outputs"])
    typing = [("outputs", " ∧ ".join(f"{o} ∈ {r}" for o, r in m["outputs"].items()), False)]
    init = ("INITIALISATION", [], [], [("act1", ", ".join(outs) + " ≔ " + ", ".join("0" for _ in outs))], None)
    assume = [(f"assume{i}", g) for i, g in enumerate(m["assume"])]
    rx.machine(d, "M0", outs, typing,
               [init, ("eval", list(inputs), assume, [(f"act{i}", f"{o} ≔ {m['spec'][o]}") for i, o in enumerate(outs)], None)], sees=sees)
    ports = [("ports", " ∧ ".join(f"{p} ∈ 0 ‥ {2 ** w - 1}" for p, w in inputs.items()))]
    rx.machine(d, "M1", outs, [],
               [init, ("eval", list(inputs), assume + ports, [(f"act{i}", f"{o} ≔ {rtl[o]}") for i, o in enumerate(outs)], "eval")],
               refines="M0", sees=sees)
    print(name, "ok")
