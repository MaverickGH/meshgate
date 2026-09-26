"""Zombie cat character standing upright on two legs, ~1.05 m tall."""
import math


def build(mg):
    fur = mg.color("fur", "#5f7059", rough=0.9)
    fur_d = mg.color("fur_d", "#4a5745", rough=0.9)
    belly = mg.color("belly", "#9caa8f", rough=0.9)
    pink = mg.color("pink", "#c98a92", rough=0.7)
    nose = mg.color("nose", "#b96d78", rough=0.6)
    paw = mg.color("paw", "#cdd6c4", rough=0.85)
    eye = mg.color("eye", "#6fe23a", rough=0.3, glow=2.5)
    stitch = mg.color("stitch", "#15150f", rough=0.6)
    whisk = mg.color("whisk", "#e8e8e0", rough=0.5)

    parts = []

    # ---- legs ----
    for sx in (-1, 1):
        hipx = sx * 0.11
        parts.append(mg.tube([(hipx, 0, 0.06), (hipx, 0.01, 0.24), (hipx, -0.01, 0.42)],
                             0, fur, radii=[0.075, 0.07, 0.065], sides=10))
        # foot
        parts.append(mg.part("sphere", paw, loc=(hipx, -0.05, 0.05),
                             scale=(0.11, 0.19, 0.09), subdiv=1))

    # ---- torso ----
    parts.append(mg.lathe([(0.0, 0.40), (0.14, 0.45), (0.17, 0.55),
                           (0.16, 0.63), (0.12, 0.70), (0.0, 0.73)],
                          fur, loc=(0, 0, 0), segments=mg.seg(18)))
    # belly patch
    parts.append(mg.part("sphere", belly, loc=(0, -0.13, 0.55),
                         scale=(0.17, 0.09, 0.24), subdiv=1))
    # chest fill
    parts.append(mg.part("sphere", fur, loc=(0, 0, 0.66), scale=(0.2, 0.19, 0.18), subdiv=1))

    # ---- arms stretched forward ----
    for sx in (-1, 1):
        sh = (sx * 0.16, -0.02, 0.66)
        el = (sx * 0.19, -0.22, 0.62)
        hd = (sx * 0.18, -0.40, 0.60)
        arm = mg.tube([sh, el, hd], 0, fur, radii=[0.075, 0.055, 0.05], sides=9)
        parts.append(arm)
        parts.append(mg.part("sphere", paw, loc=(sx * 0.18, -0.44, 0.60),
                             scale=(0.07, 0.09, 0.07), subdiv=1))

    # ---- neck ----
    parts.append(mg.part("cyl", fur, loc=(0, -0.01, 0.73), scale=(0.13, 0.13, 0.1), vertices=12))

    # ---- head ----
    parts.append(mg.part("sphere", fur, loc=(0, -0.01, 0.86),
                         scale=(0.27, 0.26, 0.27), subdiv=1))
    # muzzle
    parts.append(mg.part("sphere", belly, loc=(0, -0.24, 0.82),
                         scale=(0.11, 0.08, 0.08), subdiv=1))
    parts.append(mg.part("sphere", nose, loc=(0, -0.29, 0.85),
                         scale=(0.035, 0.03, 0.028), subdiv=1))

    # eyes (glowing green)
    for sx in (-1, 1):
        parts.append(mg.part("sphere", eye, loc=(sx * 0.11, -0.24, 0.91),
                             scale=(0.045, 0.045, 0.055), subdiv=1))

    # stitched scar across head
    parts.append(mg.tube([(-0.13, -0.22, 0.99), (0.13, -0.2, 1.0)], 0.006, stitch, sides=6))
    for i in range(5):
        t = i / 4
        cx = -0.11 + 0.22 * t
        cy = -0.215 - 0.01 * math.sin(t * math.pi)
        parts.append(mg.part("cube", stitch, loc=(cx, cy, 0.995),
                             scale=(0.008, 0.05, 0.008), rot=(0, math.pi * 0.06, 0)))

    # ---- ears ----
    def ear(sx, torn):
        e = []
        base = (sx * 0.15, -0.02, 1.02)
        tip = (sx * 0.19, -0.01, 1.14)
        e.append(mg.tube([base, tip], 0, fur, radii=[0.09, 0.015], sides=8))
        e.append(mg.part("sphere", pink, loc=(sx * 0.15, -0.07, 1.06),
                         scale=(0.05, 0.02, 0.06), subdiv=1))
        if torn:
            e.append(mg.part("cube", fur_d, loc=(sx * 0.18, -0.01, 1.11),
                             scale=(0.03, 0.06, 0.03), rot=(0, math.pi / 4, 0)))
        return e
    parts += ear(1, False)
    parts += ear(-1, True)

    # ---- tail ----
    tail = mg.tube([(0.1, 0.13, 0.55), (0.2, 0.2, 0.62), (0.22, 0.12, 0.5),
                    (0.19, 0.05, 0.42)], 0, fur, radii=[0.055, 0.05, 0.045, 0.04], sides=8)
    parts.append(tail)
    parts.append(mg.part("sphere", paw, loc=(0.19, 0.05, 0.41), scale=(0.05, 0.05, 0.05), subdiv=1))

    # ---- whiskers ----
    if mg.at_least("mobile-mid"):
        for sx in (-1, 1):
            for dz in (0.02, 0.0, -0.02):
                parts.append(mg.tube([(sx * 0.09, -0.27, 0.83 + dz),
                                      (sx * 0.24, -0.33, 0.84 + dz * 1.5)],
                                     0.004, whisk, sides=4))

    mg.join("zc_zombie_cat", parts)
