"""Broken wooden garden fence: dark posts + rails, light cat-ear pickets, some snapped, one crooked."""
import math


def build(mg):
    mg.mirror_x  # symmetry not enforced (broken fence is asymmetric)
    post_wd = mg.color("post_wd", "#3d281700"[:7], rough=0.85)
    post_wd = mg.color("post_wd", "#3d2817", rough=0.85)
    rail_wd = mg.color("rail_wd", "#463019", rough=0.85)
    pick_wd = mg.color("pick_wd", "#9c7238", rough=0.8)
    pick_wd2 = mg.color("pick_wd2", "#8c6430", rough=0.8)
    nail = mg.color("nail", (0.22, 0.2, 0.19), rough=0.5, metal=1.0)

    parts = []

    # --- posts ---
    for x in (-0.95, 0.95):
        parts.append(mg.part("cube", post_wd, loc=(x, 0.0, 0.56),
                             scale=(0.09, 0.09, 1.12), bevel=0.008))
    # small broken notch on the right post
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", rail_wd, loc=(0.955, -0.03, 0.72),
                             scale=(0.05, 0.05, 0.05), rot=(0, 0.3, 0)))

    # --- rails ---
    for z in (0.82, 0.32):
        parts.append(mg.part("cube", rail_wd, loc=(0.0, -0.045, z),
                             scale=(1.95, 0.05, 0.065), bevel=0.005))

    # --- picket outlines (front view, XZ) ---
    fw = 0.062
    full = [(-fw, 0), (fw, 0), (fw, 0.85), (0.038, 1.02),
            (0.0, 0.88), (-0.038, 1.02), (-fw, 0.85)]
    short = [(-fw, 0), (fw, 0), (fw, 0.5), (0.03, 0.6),
             (-0.01, 0.47), (-fw, 0.56)]

    depth = 0.032

    # full pickets with cat ears
    for x in (-0.78, -0.54, -0.30, 0.32):
        col = pick_wd if (int(x * 100) % 2 == 0) else pick_wd2
        parts.append(mg.extrude(full, depth, col, loc=(x, 0.0, 0.0), bevel=0.004))

    # snapped-short pickets
    for x in (0.02, 0.62):
        parts.append(mg.extrude(short, depth, pick_wd2, loc=(x, 0.0, 0.0), bevel=0.004))

    # crooked hanging picket (leaning, tilted forward, hanging from a nail)
    parts.append(mg.extrude(full, depth, pick_wd, loc=(-0.02, -0.075, 0.12),
                            rot=(0.06, 0.55, 0.0), bevel=0.004))

    # --- nails at rail/picket crossings ---
    if mg.at_least("mobile-high"):
        for x in (-0.78, -0.54, -0.30, 0.32, 0.02, 0.62):
            for z in (0.82, 0.32):
                parts.append(mg.part("cyl", nail, loc=(x + 0.02, -0.075, z),
                                     scale=(0.012, 0.012, 0.02),
                                     rot=(math.pi / 2, 0, 0), vertices=6))

    mg.join("zc_fence_broken", parts)
