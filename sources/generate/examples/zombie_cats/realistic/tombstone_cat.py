"""Cat-shaped tombstone: stone slab with two pointed cat ears, a carved paw print, on a low stone base with glowing green goo."""
import math


def build(mg):
    stone = mg.color("stone_light", "#cbc3ab", rough=0.85, material="stone")
    stone_dark = mg.color("stone_dark", "#38383a", rough=0.7, material="stone")
    stone_base = mg.color("stone_base", "#c2baa0", rough=0.88, material="stone")
    goo = mg.color("goo_ooze", "#7ede2c", rough=0.35, glow=2.2, material="plain")

    parts = []

    # ---- low stone base (two stacked tiers) ----
    parts.append(mg.part("cube", stone_base, loc=(0, 0, 0.045), scale=(0.82, 0.46, 0.09), bevel=0.012))
    parts.append(mg.part("cube", stone_base, loc=(0, 0, 0.12), scale=(0.55, 0.36, 0.07), bevel=0.01))

    # ---- main slab with cat-ear silhouette (front view outline, front faces -Y) ----
    outline = [
        (-0.35, 0.12),
        (-0.35, 0.70),
        (-0.31, 1.02),   # left ear tip
        (-0.09, 0.80),   # valley
        (0.09, 0.80),
        (0.31, 1.05),    # right ear tip
        (0.35, 0.70),
        (0.35, 0.12),
    ]
    slab = mg.extrude(outline, 0.22, stone, loc=(0, 0, 0), bevel=0.018, smooth=False)
    parts.append(slab)

    fy = -0.10  # front face plane (protruding pads)

    # ---- paw print: large central pad ----
    parts.append(mg.part("sphere", stone_dark, loc=(0, fy, 0.47),
                         scale=(0.17, 0.07, 0.13), smooth=True))

    # ---- four toe beans in an arc above ----
    toe = mg.part("sphere", stone_dark, loc=(-0.14, fy, 0.585),
                  scale=(0.085, 0.055, 0.08), smooth=True)
    parts.append(toe)
    parts.append(mg.mirror_x(toe))
    toe2 = mg.part("sphere", stone_dark, loc=(-0.05, fy, 0.665),
                   scale=(0.085, 0.055, 0.085), smooth=True)
    parts.append(toe2)
    parts.append(mg.mirror_x(toe2))

    # ---- glowing green goo ----
    # blob nestled in the ear valley
    parts.append(mg.part("sphere", goo, loc=(0, 0.79, -0.02), scale=(0.14, 0.16, 0.06), smooth=True))
    # puddle spreading on the base
    parts.append(mg.part("sphere", goo, loc=(0.02, 0.06, 0.10), scale=(0.34, 0.24, 0.05), smooth=True))
    # bright blob spilling off the right side of the base
    parts.append(mg.part("sphere", goo, loc=(0.42, -0.02, 0.06), scale=(0.12, 0.12, 0.11), smooth=True))

    if mg.at_least("mobile-mid"):
        # smaller drips down the front and across the base
        for x, y, z, s in [(-0.30, -0.12, 0.09, 0.05), (0.30, 0.10, 0.09, 0.045),
                           (-0.24, -0.11, 0.32, 0.035), (0.10, -0.13, 0.20, 0.03),
                           (0.46, 0.06, 0.05, 0.05)]:
            parts.append(mg.part("sphere", goo, loc=(x, y, z),
                                 scale=(s, s * 0.9, s * 0.8), smooth=True))

    if mg.at_least("mobile-high"):
        # fine speckles of ooze near the ground
        for _ in range(10):
            x = mg.rng.uniform(-0.36, 0.46)
            y = mg.rng.uniform(-0.15, 0.15)
            r = mg.rng.uniform(0.012, 0.03)
            parts.append(mg.part("sphere", goo, loc=(x, y, 0.10),
                                 scale=(r, r, r * 0.6), smooth=True))

    mg.join("zc_tombstone_cat", parts)
