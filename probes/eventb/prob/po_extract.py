"""Write a Rodin proof obligation as one closed B predicate: ∃ ids · (hypotheses ∧ ¬ goal)."""
import sys, xml.etree.ElementTree as ET
bpo, name = sys.argv[1], sys.argv[2]
root = ET.parse(bpo).getroot()
sets = {s.get("name"): s for s in root if s.tag.endswith("poPredicateSet")}
po = next(s for s in root if s.tag.endswith("poSequent") and s.get("name") == name)
idents, hyps, goal = {}, [], None
def collect(predset):
    parent = predset.get("org.eventb.core.parentSet")
    if parent:
        collect(sets[parent.split("#")[-1].replace("\\", "")])
    for e in predset:
        if e.tag.endswith("poIdentifier"):
            idents[e.get("name")] = e.get("org.eventb.core.type")
        elif e.tag.endswith("poPredicate"):
            hyps.append(e.get("org.eventb.core.predicate"))
for e in po:
    if e.tag.endswith("poPredicateSet"):
        collect(e)
    elif e.tag.endswith("poIdentifier"):
        idents[e.get("name")] = e.get("org.eventb.core.type")
    elif e.tag.endswith("poPredicate"):
        goal = e.get("org.eventb.core.predicate")
hyps = [h for h in hyps if h != "⊤"]
print(f"identifiers {len(idents)}, hypotheses {len(hyps)}, goal {len(goal)} chars", file=sys.stderr)
print(f"types: {sorted(set(idents.values()))}", file=sys.stderr)
import re
text = " ∧ ".join(f"({h})" for h in hyps) + f" ∧ ¬({goal})"
# ProB's parser rejects the prime of an after-value: rot' becomes rot_prime.
print(re.sub(r"(\w)'", r"\1_prime", text))
