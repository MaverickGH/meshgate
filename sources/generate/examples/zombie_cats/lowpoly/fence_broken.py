"""Broken wooden garden fence: 2 posts, 2 rails, cat-ear pickets, one crooked, two snapped short."""
import math


def build(mg):
    mg.color("wood_post", "#4a2c1e", rough=0.85, material="wood")
    mg.color("wood_rail", "#4a2c1e", rough=0.85, material="wood")
    mg.color("wood_cap", "#5a3624", rough=0.8, material="wood")
    mg.color("wood_picket", "#c08a55", rough=0.75, material="wood")
    mg.color("nail", "#2e2117", rough=0.7, metal=0.4, material="rust")

    parts = []
    w = 0.13           # picket width
    pd = 0.03          # picket thickness (depth along Y)
    py = -0.035        # picket front plane
    ry = 0.02          # rail plane
    post_y = 0.05
    H = 1.1

    # --- cat-ear picket outlines (XZ, centered on x=0) ---
    def full_top(base):
        return [(-w/2, base), (w/2, base), (w/2, 0.88),
                (w/4, 1.0), (0, 0.80), (-w/4, 1.0), (-w/2, 0.88)]

    def snapped():
        # jagged snapped bottom, cat-ear top, short
        return [(-w/2, 0.42), (-w/4, 0.33), (0.0, 0.45), (w/4, 0.34),
                (w/2, 0.42), (w/2, 0.88), (w/4, 1.0), (0, 0.80), (-w/4, 1.0), (-w/2, 0.88)]

    # --- posts ---
    for x in (-1.0, 1.0):
        parts.append(mg.part("cube", "wood_post", loc=(x, post_y, H/2),
                             scale=(0.09, 0.08, H), bevel=0.006))
        parts.append(mg.part("cube", "wood_cap", loc=(x, post_y, H - 0.03),
                             scale=(0.095, 0.085, 0.06), bevel=0.006))

    # --- rails (slightly tilted for a broken look) ---
    for z in (0.78, 0.40):
        parts.append(mg.part("cube", "wood_rail", loc=(0, ry, z),
                             scale=(1.94, 0.05, 0.085), rot=(0, 0.015, 0), bevel=0.005))

    # --- upright full pickets ---
    full_x = [-0.80, -0.55, -0.30, -0.05]
    for x in full_x:
        parts.append(mg.extrude(full_top(0.02), pd, "wood_picket",
                                loc=(x, py, 0), bevel=0.004))

    # --- one crooked picket hanging from a single nail (leaning) ---
    parts.append(mg.extrude(full_top(0.02), pd, "wood_picket",
                            loc=(0.24, py - 0.02, 0.0), rot=(0, 0.33, 0), bevel=0.004))

    # --- two snapped-short pickets on the right ---
    for x in (0.55, 0.78):
        parts.append(mg.extrude(snapped(), pd, "wood_picket",
                                loc=(x, py, 0), bevel=0.004))

    # --- nail heads at rail crossings ---
    if mg.at_least("mobile-mid"):
        nail_x = full_x + [0.24, 0.55, 0.78]
        for x in nail_x:
            for z in (0.78, 0.40):
                if z == 0.40 and x in (0.55, 0.78):
                    continue  # snapped ones broken off below top rail
                parts.append(mg.part("cyl", "nail", loc=(x, py - 0.03, z),
                                     scale=(0.024, 0.024, 0.03), rot=(math.pi/2, 0, 0),
                                     vertices=8))

    mg.join("zc_fence_broken", parts)
