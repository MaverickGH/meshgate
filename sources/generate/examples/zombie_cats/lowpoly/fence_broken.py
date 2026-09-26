"""Broken wooden garden fence: dark posts + rails, tan cat-ear pickets, some snapped, one crooked."""
import math


def build(mg):
    dark = mg.color("wood_dark", "#432c17", rough=0.85)
    tan = mg.color("wood_tan", "#a9825408"[:7], rough=0.8)
    tan = mg.color("wood_tan", "#a98254", rough=0.8)
    tan2 = mg.color("wood_tan2", "#946e42", rough=0.82)
    nailc = mg.color("nail", (0.3, 0.3, 0.33), rough=0.45, metal=1.0)

    parts = []

    # ---- posts (dark, chunky, at both ends) ----
    for x in (-0.9, 0.9):
        parts.append(mg.part("cube", dark, loc=(x, 0.0, 0.55),
                             scale=(0.1, 0.13, 1.1), bevel=0.008))
    # right post has a little slot cut near the top (broken look) -> small notch cube skipped, add stub
    parts.append(mg.part("cube", dark, loc=(0.9, -0.08, 0.72),
                         scale=(0.11, 0.03, 0.14), bevel=0.005))

    # ---- two horizontal rails ----
    for z in (0.35, 0.8):
        parts.append(mg.part("cube", dark, loc=(0.0, 0.0, z),
                             scale=(1.85, 0.09, 0.1), bevel=0.008))

    # ---- picket outlines (XZ front view) ----
    full = [(-0.06, 0.0), (-0.06, 0.68), (-0.035, 0.86), (0.0, 0.7),
            (0.035, 0.86), (0.06, 0.68), (0.06, 0.0)]
    short = [(-0.06, 0.0), (-0.06, 0.42), (-0.02, 0.51), (0.015, 0.4),
             (0.06, 0.47), (0.06, 0.0)]
    dep = 0.035
    fy, base_z = -0.06, 0.13

    # full cat-ear pickets
    full_x = [-0.68, -0.43, -0.18, 0.52]
    picket = mg.extrude(full, dep, tan, loc=(0.0, fy, base_z), bevel=0.004)
    parts.append(picket)
    for i, x in enumerate(full_x):
        c = tan if i % 2 else tan2
        parts.append(mg.copy(picket, loc=(x, fy, base_z)))

    # snapped-short pickets
    stub = mg.extrude(short, dep, tan2, loc=(0.0, fy, base_z), bevel=0.004)
    parts.append(stub)
    for x in (0.12, 0.74):
        parts.append(mg.copy(stub, loc=(x, fy, base_z)))

    # crooked hanging picket (leaning, front, from a single nail)
    parts.append(mg.extrude(full, dep, tan, loc=(0.33, -0.1, 0.16),
                            rot=(0.0, 0.32, 0.0), bevel=0.004))
    parts.append(mg.part("cyl", nailc, loc=(0.3, -0.14, 0.42),
                         scale=(0.03, 0.03, 0.04), rot=(math.pi / 2, 0, 0),
                         vertices=8))

    # ---- nails where pickets meet rails (richer tiers) ----
    if mg.at_least("mobile-high"):
        for x in [0.0] + full_x:
            for z in (0.35, 0.8):
                parts.append(mg.part("cyl", nailc, loc=(x + 0.02, -0.082, z),
                                     scale=(0.02, 0.02, 0.035),
                                     rot=(math.pi / 2, 0, 0), vertices=8))

    mg.join("zc_fence_broken", parts)
