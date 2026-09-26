"""zc_tombstone_cat — cat-shaped stone tombstone with paw print and glowing green goo."""
import math


def build(mg):
    stone = mg.color("stone", "#cfc8ba", rough=0.85, material="stone")
    stone_base = mg.color("stone_base", "#c3bcae", rough=0.9, material="stone")
    pad = mg.color("stone_pad", "#5c5c58", rough=0.8, material="stone")
    goo = mg.color("goo_green", "#8ef23a", rough=0.25, glow=2.6, material="plain")

    depth = 0.12  # slab thickness

    # --- slab silhouette (front view XZ) with cat ears and scooped top ---
    outline = [(-0.35, 0.05), (-0.35, 0.82), (-0.31, 1.08), (-0.16, 0.80)]
    n = 9
    for i in range(1, n):  # concave scoop between the ears
        t = i / n
        x = -0.16 + 0.32 * t
        z = 0.80 - 0.12 * math.sin(math.pi * t)
        outline.append((x, z))
    outline += [(0.16, 0.80), (0.31, 1.08), (0.35, 0.82), (0.35, 0.05)]

    parts = []
    parts.append(mg.extrude(outline, depth, stone, bevel=0.012, smooth=False))

    # --- low stone base ---
    parts.append(mg.part("cube", stone_base, loc=(0, 0, 0.075),
                         scale=(0.82, 0.36, 0.15), bevel=0.015))
    parts.append(mg.part("cube", stone_base, loc=(0, 0, 0.165),
                         scale=(0.72, 0.30, 0.05), bevel=0.012))

    body = mg.join("zc_tombstone_cat", parts)

    # --- carved paw print on the front face ---
    fy = -depth / 2  # front surface
    paw = []
    # main pad
    paw.append(mg.part("cyl", pad, loc=(0, fy - 0.005, 0.44),
                       scale=(0.19, 0.19, 0.035), rot=(math.pi / 2, 0, 0),
                       vertices=12, bevel=0.01))
    # four toe pads in an arc
    toes = [(-0.15, 0.57, 0.07), (-0.055, 0.64, 0.075),
            (0.055, 0.64, 0.075), (0.15, 0.57, 0.07)]
    for tx, tz, r in toes:
        paw.append(mg.part("cyl", pad, loc=(tx, fy - 0.004, tz),
                           scale=(r * 2, r * 2, 0.03), rot=(math.pi / 2, 0, 0),
                           vertices=10, bevel=0.006))
    mg.join("paw", paw)

    # --- glowing green goo puddle at the base ---
    blob = []
    blob.append(mg.part("sphere", goo, loc=(0.02, -0.16, 0.02),
                        scale=(0.34, 0.28, 0.045)))
    blob.append(mg.part("sphere", goo, loc=(-0.02, -0.05, 0.02),
                        scale=(0.16, 0.14, 0.04)))
    # drip running down the front of the base
    blob.append(mg.part("sphere", goo, loc=(0.06, -0.18, 0.11),
                        scale=(0.10, 0.05, 0.10)))
    if mg.at_least("mobile-mid"):
        drops = [(0.30, -0.22, 0.015, 0.08), (-0.26, -0.10, 0.015, 0.06),
                 (0.20, -0.30, 0.012, 0.05), (0.14, 0.30, 0.013, 0.05)]
        for dx, dy, dz, r in drops:
            blob.append(mg.part("sphere", goo, loc=(dx, dy, dz),
                                scale=(r, r * 0.85, r * 0.5)))
    mg.join("goo", blob)
