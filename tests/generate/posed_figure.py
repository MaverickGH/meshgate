"""build(mg) for the pose check: a plain figure modelled with its arms hanging, rigged, with a clip. With --pose a / t
the rig raises the arms into an A-pose / T-pose, and that is the file's rest pose: the model gets wider."""


def build(mg):
    skin = mg.color("skin", "#9a8a78")
    P = [(0, 0, 0.9), (0, 0, 1.2), (0, 0, 1.4), (0, 0, 1.5), (0.1, 0, 0.88), (0.11, 0, 0.5), (0.11, 0, 0.1),
         (-0.1, 0, 0.88), (-0.11, 0, 0.5), (-0.11, 0, 0.1), (0.2, 0, 1.38), (0.24, 0, 1.12), (0.26, 0, 0.88),
         (-0.2, 0, 1.38), (-0.24, 0, 1.12), (-0.26, 0, 0.88)]
    E = [(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 6), (0, 7), (7, 8), (8, 9),
         (2, 10), (10, 11), (11, 12), (2, 13), (13, 14), (14, 15)]
    body = mg.skin(P, [0.13, 0.14, 0.13, 0.05, 0.07, 0.055, 0.045, 0.07, 0.055, 0.045, 0.05, 0.04, 0.035, 0.05, 0.04, 0.035],
                   skin, edges=E)
    head = mg.part("sphere", skin, loc=(0, 0, 1.63), scale=(0.22, 0.24, 0.26))
    fig = mg.join("posed_figure", [body, head])
    mg.rig(fig, {"hips": (0, 0, 0.9), "spine": (0, 0, 1.15), "chest": (0, 0, 1.35), "neck": (0, 0, 1.48),
                 "head": (0, 0, 1.52), "head_top": (0, 0, 1.76), "shoulder_l": (0.2, 0, 1.38), "elbow_l": (0.24, 0, 1.12),
                 "hand_l": (0.26, 0, 0.88), "hip_l": (0.1, 0, 0.88), "knee_l": (0.11, 0, 0.5), "ankle_l": (0.11, 0, 0.1),
                 "toe_l": (0.11, -0.12, 0.03)})
    mg.clip("shamble", "zombie_walk")
