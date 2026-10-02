"""Writes small Rodin projects from Python descriptions, for the probes only."""
from pathlib import Path
from xml.sax.saxutils import quoteattr

OV = ""  # Rodin's overriding symbol


def project(root, name):
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    for f in d.iterdir():
        if f.is_file():
            f.unlink()
    (d / ".project").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<projectDescription><name>{name}</name><comment></comment>'
        "<projects></projects><buildSpec><buildCommand><name>org.rodinp.core.rodinbuilder</name>"
        "<arguments></arguments></buildCommand></buildSpec><natures><nature>org.rodinp.core.rodinnature</nature>"
        "</natures></projectDescription>\n")
    return d


def a(**kw):
    return " ".join(f"org.eventb.core.{k}={quoteattr(v)}" for k, v in kw.items())


def machine(d, name, variables, invariants, events, refines=None, sees=None):
    """invariants: [(label, predicate, theorem)]; events: [(label, params, guards, actions, refines)]."""
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           '<org.eventb.core.machineFile org.eventb.core.configuration="org.eventb.core.fwd" version="5">']
    if refines:
        out.append(f'<org.eventb.core.refinesMachine name="r1" {a(target=refines)}/>')
    if sees:
        out.append(f'<org.eventb.core.seesContext name="s1" {a(target=sees)}/>')
    out += [f'<org.eventb.core.variable name="v{i}" {a(identifier=v)}/>' for i, v in enumerate(variables)]
    for i, (label, pred, thm) in enumerate(invariants):
        extra = ' org.eventb.core.theorem="true"' if thm else ""
        out.append(f'<org.eventb.core.invariant name="i{i}" {a(label=label, predicate=pred)}{extra}/>')
    for i, event in enumerate(events):
        label, params, guards, actions, ref = event[:5]
        witnesses = event[5] if len(event) > 5 else []
        out.append(f'<org.eventb.core.event name="e{i}" org.eventb.core.convergence="0" '
                   f'org.eventb.core.extended="false" {a(label=label)}>')
        if ref:
            out.append(f'<org.eventb.core.refinesEvent name="r1" {a(target=ref)}/>')
        out += [f'<org.eventb.core.parameter name="p{j}" {a(identifier=p)}/>' for j, p in enumerate(params)]
        out += [f'<org.eventb.core.guard name="g{j}" {a(label=g[0], predicate=g[1])}'
                + (' org.eventb.core.theorem="true"' if len(g) > 2 and g[2] else '') + '/>' for j, g in enumerate(guards)]
        out += [f'<org.eventb.core.witness name="w{j}" {a(label=l, predicate=x)}/>' for j, (l, x) in enumerate(witnesses)]
        out += [f'<org.eventb.core.action name="a{j}" {a(label=l, assignment=x)}/>' for j, (l, x) in enumerate(actions)]
        out.append("</org.eventb.core.event>")
    out.append("</org.eventb.core.machineFile>")
    (Path(d) / f"{name}.bum").write_text("\n".join(out) + "\n")


def context(d, name, constants, axioms):
    """axioms: [(label, predicate, theorem)]."""
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           '<org.eventb.core.contextFile org.eventb.core.configuration="org.eventb.core.fwd" version="3">']
    out += [f'<org.eventb.core.constant name="c{i}" {a(identifier=c)}/>' for i, c in enumerate(constants)]
    for i, (label, pred, thm) in enumerate(axioms):
        extra = ' org.eventb.core.theorem="true"' if thm else ""
        out.append(f'<org.eventb.core.axiom name="x{i}" {a(label=label, predicate=pred)}{extra}/>')
    out.append("</org.eventb.core.contextFile>")
    (Path(d) / f"{name}.buc").write_text("\n".join(out) + "\n")
