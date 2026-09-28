"""build(mg) for the rigged-blocks check: a figure of separate soft blocks — arms sunk into the body's sides, legs into
its bottom, the head on top — rigged. Every block follows its own bone, so no face of the body may be removed as
"hidden": when an arm swings away the body under it must still be there."""


def build(mg):
    c = mg.color("vinyl", "#7a9a6a")
    parts = [mg.part("cube", c, loc=(0, 0, 0.9), scale=(0.36, 0.24, 0.5), bevel=0.06, subdiv=1, smooth=True),       # body
             mg.part("cube", c, loc=(0, 0, 1.31), scale=(0.4, 0.32, 0.36), bevel=0.1, subdiv=1, smooth=True)]       # head
    for sx in (-1, 1):
        parts += [mg.part("cube", c, loc=(sx * 0.22, 0, 0.92), scale=(0.1, 0.1, 0.42), bevel=0.03, subdiv=1, smooth=True),   # arm
                  mg.part("cube", c, loc=(sx * 0.09, 0, 0.36), scale=(0.14, 0.15, 0.62), bevel=0.04, subdiv=1, smooth=True)]  # leg
    fig = mg.join("rigged_blocks", parts)
    mg.rig(fig, {"hips": (0, 0, 0.68), "spine": (0, 0, 0.9), "chest": (0, 0, 1.1), "neck": (0, 0, 1.17),
                 "head": (0, 0, 1.2), "head_top": (0, 0, 1.54), "shoulder_l": (0.22, 0, 1.1), "elbow_l": (0.22, 0, 0.92),
                 "hand_l": (0.22, 0, 0.73), "hip_l": (0.09, 0, 0.66), "knee_l": (0.09, 0, 0.38), "ankle_l": (0.09, 0, 0.08),
                 "toe_l": (0.09, -0.1, 0.03)})
    mg.clip("shamble", "zombie_walk")
