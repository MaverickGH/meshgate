"""zc_tombstone_cat: cat-eared arched tombstone with carved paw print, stone base and glowing green goo."""
import math


def build(mg):
    stone = mg.color("stone", "#8f9195", rough=0.85)
    stone_d = mg.color("stone_dark", "#5a5d61", rough=0.9)
    moss = mg.color("moss", "#6f8a3a", rough=0.9)
    goo = mg.color("goo", "#6cff2a", rough=0.3, glow=2.0)

    hw = 0.35          # slab half width
    zb = 0.14          # top of base
    zs = 0.74          # shoulder where dome/ears begin
    depth = 0.16       # slab thickness (Y)
    parts = []

    # --- headstone silhouette (arch + two pointed ears) as one extruded profile ---
    n = max(4, mg.seg(10))
    arc = []
    for i in range(n + 1):
        t = math.pi * (1 - i / n)          # pi -> 0, left to right
        arc.append((0.17 * math.cos(t), 0.82 + 0.17 * math.sin(t)))
    outline = [(-hw, zb), (-hw, zs), (-0.29, 1.08), (-0.17, 0.82)]
    outline += arc[1:-1]
    outline += [(0.17, 0.82), (0.29, 1.08), (hw, zs), (hw, zb)]
    parts.append(mg.extrude(outline, depth, stone, bevel=0.01))

    front = -depth / 2   # front face y

    # --- carved paw print on the front (dark recessed pads) ---
    def pad(x, z, rx, rz):
        parts.append(mg.part("sphere", stone_d, loc=(x, front + 0.005, z),
                             scale=(rx, 0.05, rz), segments=mg.seg(12)))
    pad(0.0, 0.47, 0.15, 0.15)                       # main pad
    for tx, tz in ((-0.13, 0.60), (-0.045, 0.67), (0.045, 0.67), (0.13, 0.60)):
        pad(tx, tz, 0.055, 0.065)                    # toe beans

    # --- low stone base (larger footprint) ---
    parts.append(mg.part("cube", stone, loc=(0, 0, 0.075),
                         scale=(0.88, 0.42, 0.15), bevel=0.02))
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", stone, loc=(0, 0, 0.14),
                             scale=(0.78, 0.34, 0.05), bevel=0.015))

    # --- moss patches (small detail) ---
    if mg.at_least("mobile-high"):
        spots = [(-0.31, front + 0.02, 0.30, 0.09, 0.14),
                 (0.30, front + 0.02, 0.55, 0.07, 0.11),
                 (-0.22, front + 0.02, 0.90, 0.10, 0.08),
                 (0.24, front + 0.02, 0.86, 0.08, 0.07),
                 (-0.38, -0.10, 0.07, 0.10, 0.06),
                 (0.36, 0.12, 0.07, 0.09, 0.06)]
        for x, y, z, rx, rz in spots:
            parts.append(mg.part("sphere", moss, loc=(x, y, z),
                                 scale=(rx, 0.06, rz), segments=mg.seg(10)))

    stone_mesh = mg.join("zc_tombstone_cat", parts)

    # --- glowing green goo ---
    gparts = []
    gparts.append(mg.part("sphere", goo, loc=(0.02, -0.13, 0.155),
                         scale=(0.22, 0.20, 0.05), segments=mg.seg(14)))
    gparts.append(mg.part("sphere", goo, loc=(0.06, -0.21, 0.11),
                         scale=(0.10, 0.06, 0.11), segments=mg.seg(12)))
    gparts.append(mg.tube([(0.02, front + 0.01, 0.28), (0.03, -0.10, 0.16)],
                          0.028, goo, sides=mg.seg(8)))
    if mg.at_least("mobile-mid"):
        gparts.append(mg.part("sphere", goo, loc=(0.16, -0.28, 0.02),
                             scale=(0.06, 0.06, 0.025), segments=mg.seg(10)))
        gparts.append(mg.part("sphere", goo, loc=(-0.06, -0.24, 0.02),
                             scale=(0.04, 0.04, 0.02), segments=mg.seg(8)))
    goo_mesh = mg.join("zc_goo", gparts)
    mg.attach(goo_mesh, stone_mesh)
