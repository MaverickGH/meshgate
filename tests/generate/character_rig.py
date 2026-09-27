"""build(mg) for the character check: a small clay biped with fur cards, a Humanoid skeleton and three clips."""


def build(mg):
    fur = mg.color("test_fur", "#8a7a60", rough=0.8, material="fur")
    belly = mg.color("belly_fur", "#e0d8c4", rough=0.8, material="fur")
    shapes = [{"ellipsoid": (0, 0, 0.45), "size": (0.14, 0.11, 0.2)}, {"ball": (0, -0.01, 0.72), "r": 0.11}]
    for sx in (-1, 1):
        shapes += [{"capsule": ((sx * 0.08, 0, 0.3), (sx * 0.09, 0, 0.06)), "r": 0.05},
                   {"ellipsoid": (sx * 0.09, -0.04, 0.035), "size": (0.05, 0.08, 0.035)},
                   {"capsule": ((sx * 0.13, 0, 0.56), (sx * 0.2, -0.05, 0.36)), "r": 0.035}]
    body = mg.blob(shapes, fur, blend=0.9)
    mg.paint(body, belly, at=(0, -0.1, 0.45), radius=0.14, facing=(0, -1, 0), rough=0.4)
    mg.sculpt(body, "ridge", path=[(-0.05, -0.1, 0.76), (0.05, -0.1, 0.76)], radius=0.01, amount=0.006)
    mg.sculpt(body, "pinch", path=[(-0.05, -0.1, 0.76), (0.05, -0.1, 0.76)], radius=0.01, strength=0.4)
    mg.sculpt(body, "layer", at=(0, -0.11, 0.66), radius=0.03, amount=0.004)
    mg.sculpt(body, "flatten", at=(0, 0.1, 0.45), radius=0.06, strength=0.5)
    eye_c = mg.color("eye_glow", "#9dff3a", glow=2.0)
    eyes = [mg.eye((sx * 0.04, -0.09, 0.75), 0.02, eye_c) for sx in (-1, 1)]
    coat = mg.fur(body, length=0.02, count=2000, droop=0.6, below=0.62)
    char = mg.join("critter", [body, coat, *eyes])
    mg.rig(char, {"hips": (0, 0, 0.3), "chest": (0, 0, 0.55), "neck": (0, 0, 0.62), "head": (0, 0, 0.65),
                  "head_top": (0, 0, 0.84), "shoulder_l": (0.12, 0, 0.56), "elbow_l": (0.16, -0.03, 0.46),
                  "hand_l": (0.2, -0.05, 0.36), "hip_l": (0.08, 0, 0.3), "knee_l": (0.085, 0, 0.18),
                  "ankle_l": (0.09, 0, 0.06), "toe_l": (0.09, -0.08, 0.03)})
    mg.clip("idle", "idle")
    mg.clip("walk", "zombie_walk")
    mg.clip("attack", "attack")
