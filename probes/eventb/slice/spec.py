"""The hand-written machines of the slice: what a reader audits."""

NEXT = "({{TRUE ↦ 0, FALSE ↦ {0} + 1}})(bool({0} = 7))"            # the thread after the thread {0}
ADD = "({{TRUE ↦ {0} + {1}, FALSE ↦ {0} + {1} − 256}})(bool({0} + {1} < 256))"   # an 8-bit add

# M0: eight threads take turns in a fixed order. A step changes the state of the thread of the turn
# and of no other thread. The machine powers up in any state; reset gives the start state, in which
# thread 0 runs (1) and the others are stopped (0).
M0 = dict(
    variables=["turn", "val"],
    invariants=[("turn_type", "turn ∈ 0 ‥ 7", False), ("val_type", "val ∈ 0 ‥ 7 → 0 ‥ 255", False)],
    events=[
        ("INITIALISATION", [], [], [("init_turn", "turn :∈ 0 ‥ 7"), ("init_val", "val :∈ 0 ‥ 7 → 0 ‥ 255")], None),
        ("reset", [], [], [("reset_turn", "turn ≔ 0"), ("reset_val", "val ≔ {0 ↦ 1} ∪ ((1 ‥ 7) × {0})")], None),
        ("step", ["t", "in"], [("next", f"t = {NEXT.format('turn')}"), ("thread", "t ∈ 0 ‥ 7", True),
                               ("in_type", "in ∈ 0 ‥ 255")],
         [("own", f"val(t) ≔ {ADD.format('val(t)', 'in')}"), ("turn", "turn ≔ t")], None),
    ])

# M1: the pipeline is a ring of 8 stages, F to W, each holding one thread's record. Stage k holds the
# record of the thread of the turn k cycles ago. Each cycle every record moves one stage, and W's
# record comes back to F with its step done.
STAGES = ["f_rec", "x_rec", "d_rec", "r_rec", "e_rec", "m1_rec", "m2_rec", "w_rec"]
def where(rot, prime=""):
    """The records of the threads at turn rot: thread rot − k is in stage k."""
    return "{" + ", ".join(f"{(rot - k) % 8} ↦ {s}{prime}" for k, s in enumerate(STAGES)) + "}"
M1 = dict(
    variables=["rot"] + STAGES,
    invariants=[("rot_type", "rot ∈ 0 ‥ 7", False)] + [(f"{s}_type", f"{s} ∈ 0 ‥ 255", False) for s in STAGES]
               + [("turn_rot", "turn = rot", False)]
               + [(f"where_{r}", f"rot = {r} ⇒ val = {where(r)}", False) for r in range(8)],
    events=[
        ("INITIALISATION", [], [], [("init_rot", "rot :∈ 0 ‥ 7")] + [(f"init_{s}", f"{s} :∈ 0 ‥ 255") for s in STAGES],
         None, [("turn'", "turn' = rot'"),
                ("val'", " ∧ ".join(f"(rot' = {r} ⇒ val' = {where(r, chr(39))})" for r in range(8)))]),
        ("reset", [], [], [("reset_rot", "rot ≔ 0")]
         + [(f"reset_{s}", f"{s} ≔ {1 if s == 'f_rec' else 0}") for s in STAGES], "reset"),
        ("clock", ["in"], [("in_type", "in ∈ 0 ‥ 255")],
         [("rot", f"rot ≔ {NEXT.format('rot')}"), ("f_rec", f"f_rec ≔ {ADD.format('w_rec', 'in')}")]
         + [(s, f"{s} ≔ {p}") for p, s in zip(STAGES, STAGES[1:])], "step", [("t", f"t = {NEXT.format('rot')}")]),
    ])
