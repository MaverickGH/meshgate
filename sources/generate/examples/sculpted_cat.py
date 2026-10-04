"""A sitting zombie cat sculpted, not stacked: one blob body with carved eye sockets, a skin tail, brush detail."""

def build(mg):
    fur = mg.color("zombie_fur", "#7d8a6a", rough=0.8, material="fabric")
    dark = mg.color("dark_fur", "#4a5440", rough=0.85, material="fabric")
    eye = mg.color("eye_glow", "#c8ff5a", glow=2.0)
    nose = mg.color("nose", "#8a4a55", rough=0.5)
    body = mg.blob([
        {"ellipsoid": (0, 0.02, 0.22), "size": (0.13, 0.2, 0.14)},        # torso
        {"ball": (0, -0.14, 0.34), "r": 0.1},                            # chest
        {"ellipsoid": (0, -0.2, 0.47), "size": (0.12, 0.1, 0.1)},        # head
        {"ball": (-0.045, -0.29, 0.44), "r": 0.035},                     # cheeks / muzzle
        {"ball": (0.045, -0.29, 0.44), "r": 0.035},
        {"capsule": ((-0.07, -0.13, 0.25), (-0.07, -0.16, 0.03)), "r": 0.035},   # front legs
        {"capsule": ((0.07, -0.13, 0.25), (0.07, -0.16, 0.03)), "r": 0.035},
        {"ellipsoid": (-0.08, 0.12, 0.13), "size": (0.06, 0.1, 0.1)},    # haunches
        {"ellipsoid": (0.08, 0.12, 0.13), "size": (0.06, 0.1, 0.1)},
        {"ellipsoid": (-0.08, 0.02, 0.03), "size": (0.045, 0.07, 0.03)},  # hind paws
        {"ellipsoid": (0.08, 0.02, 0.03), "size": (0.045, 0.07, 0.03)},
        {"ball": (-0.07, -0.17, 0.03), "r": 0.04},                        # front paws
        {"ball": (0.07, -0.17, 0.03), "r": 0.04},
        {"ball": (-0.045, -0.27, 0.5), "r": 0.03, "cut": True},           # eye sockets
        {"ball": (0.045, -0.27, 0.5), "r": 0.03, "cut": True},
    ], fur, blend=0.8)
    mg.sculpt(body, "noise", amount=0.004, scale=40)
    mg.sculpt(body, "crease", path=[(0, -0.3, 0.43), (0, -0.305, 0.40)], radius=0.012, amount=0.006)
    ears = []
    for sx in (-1, 1):
        ear = mg.part("cone", dark, loc=(sx * 0.07, -0.19, 0.58), scale=(0.07, 0.04, 0.09), rot=(0.2, sx * -0.3, 0))
        ears.append(ear)
        e = mg.part("sphere", eye, loc=(sx * 0.045, -0.265, 0.5), scale=(0.045, 0.045, 0.045))
        ears.append(e)
    tail = mg.skin([(0, 0.2, 0.2), (0, 0.3, 0.25), (0.03, 0.36, 0.38), (0.08, 0.34, 0.5)], [0.03, 0.028, 0.024, 0.018], dark)
    n = mg.part("sphere", nose, loc=(0, -0.315, 0.455), scale=(0.025, 0.018, 0.016))
    mg.join("organic_cat", [body, tail, n, *ears])
