"""Zombie cat character standing upright, ~1 m tall: grey-green fur, stitched scar, torn ear, glowing green eyes, arms forward."""
import math


def build(mg):
    fur = mg.color("fur", (0.42, 0.48, 0.40), rough=0.85)
    fur_d = mg.color("fur_d", (0.34, 0.40, 0.33), rough=0.85)
    belly = mg.color("belly", (0.80, 0.84, 0.78), rough=0.8)
    pink = mg.color("pink", (0.86, 0.55, 0.60), rough=0.7)
    inner = mg.color("inner", (0.78, 0.50, 0.55), rough=0.7)
    eye = mg.color("eye", (0.35, 0.95, 0.30), rough=0.3, glow=2.5)
    stitch = mg.color("stitch", (0.05, 0.05, 0.06), rough=0.6)
    whisk = mg.color("whisk", (0.9, 0.9, 0.9), rough=0.6)

    parts = []

    # ---- legs ----
    leg = mg.tube([(0.0, 0.0, 0.0), (0.0, 0.0, 0.30)], 0.075, fur, sides=10)
    foot = mg.part("sphere", belly, loc=(0, -0.03, 0.02), scale=(0.11, 0.16, 0.08))
    legL = mg.copy(leg, loc=(0.11, 0.0, 0.0))
    footL = mg.copy(foot, loc=(0.11, -0.03, 0.02))
    parts += [legL, footL]
    parts.append(mg.mirror_x(legL))
    parts.append(mg.mirror_x(footL))

    # ---- body / torso ----
    parts.append(mg.part("sphere", fur, loc=(0, 0, 0.46), scale=(0.30, 0.24, 0.42)))
    parts.append(mg.part("sphere", belly, loc=(0, -0.12, 0.44), scale=(0.20, 0.14, 0.30)))
    # hips joining legs
    parts.append(mg.part("sphere", fur, loc=(0, 0, 0.30), scale=(0.26, 0.22, 0.20)))

    # ---- arms stretched forward ----
    arm = mg.tube([(0.0, 0.0, 0.0), (0.0, -0.18, -0.02), (0.0, -0.34, -0.05)],
                  0.06, fur, sides=8, radii=[0.075, 0.06, 0.055])
    paw = mg.part("sphere", belly, loc=(0, -0.36, -0.05), scale=(0.08, 0.08, 0.08))
    armL = mg.copy(arm, loc=(0.22, -0.02, 0.58))
    pawL = mg.copy(paw, loc=(0.22, -0.38, 0.53))
    parts += [armL, pawL]
    parts.append(mg.mirror_x(armL))
    parts.append(mg.mirror_x(pawL))

    # ---- head ----
    parts.append(mg.part("sphere", fur, loc=(0, 0, 0.82), scale=(0.34, 0.34, 0.32)))
    # muzzle
    parts.append(mg.part("sphere", belly, loc=(0, -0.18, 0.76), scale=(0.16, 0.12, 0.11)))
    parts.append(mg.part("sphere", pink, loc=(0, -0.26, 0.78), scale=(0.05, 0.05, 0.04)))
    # eyes (glowing green)
    eyeR = mg.part("sphere", eye, loc=(-0.13, -0.24, 0.86), scale=(0.055, 0.05, 0.06))
    parts.append(eyeR)
    parts.append(mg.mirror_x(eyeR))

    # ---- ears: left normal, right torn ----
    earR = mg.part("cone", fur, loc=(0.16, 0.02, 1.06), scale=(0.14, 0.05, 0.20),
                   rot=(0.0, 0.0, 0.0), taper=0.0)
    innerR = mg.part("cone", inner, loc=(0.16, -0.02, 1.05), scale=(0.08, 0.03, 0.14), taper=0.0)
    parts += [earR, innerR]
    # torn ear (left) - shorter, cut
    earL = mg.part("cone", fur, loc=(-0.16, 0.02, 1.02), scale=(0.13, 0.05, 0.15), taper=0.15)
    innerL = mg.part("cone", inner, loc=(-0.16, -0.02, 1.00), scale=(0.07, 0.03, 0.10), taper=0.2)
    parts += [earL, innerL]

    # ---- stitched scar across head ----
    parts.append(mg.part("cube", stitch, loc=(0, -0.05, 0.98), scale=(0.20, 0.02, 0.01)))
    for i in range(5):
        x = -0.08 + i * 0.04
        parts.append(mg.part("cube", stitch, loc=(x, -0.05, 0.98), scale=(0.008, 0.03, 0.05)))

    # ---- whiskers ----
    if mg.at_least("mobile-mid"):
        for dz in (-0.02, 0.0, 0.02):
            w = mg.part("cyl", whisk, loc=(-0.20, -0.22, 0.77 + dz), scale=(0.012, 0.012, 0.20),
                        rot=(0, math.pi / 2, 0.25), vertices=6)
            parts.append(w)
            parts.append(mg.mirror_x(w))

    # ---- tail ----
    parts.append(mg.tube([(0.22, 0.10, 0.55), (0.30, 0.12, 0.70),
                          (0.30, 0.10, 0.85), (0.24, 0.05, 0.95)],
                         0.05, fur_d, sides=8, radii=[0.06, 0.055, 0.05, 0.04]))
    parts.append(mg.part("sphere", belly, loc=(0.24, 0.05, 0.96), scale=(0.06, 0.06, 0.06)))

    mg.join("zc_zombie_cat", parts)
