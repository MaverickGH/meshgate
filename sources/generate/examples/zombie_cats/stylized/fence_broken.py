"""Broken wooden garden fence section: dark posts & rails, tan pickets with cat-ear tops, snapped and crooked ones."""
import math


def build(mg):
    dark = mg.color("wood_dark", "#4a2c17", rough=0.85)
    tan = mg.color("wood_light", "#a9763f", rough=0.8)
    tan2 = mg.color("wood_light2", "#946334", rough=0.82)
    nail_c = mg.color("nail", (0.22, 0.2, 0.19), rough=0.5, metal=1.0)

    parts = []

    # --- posts (two ends) ---
    post_h = 1.1
    for sx in (-1, 1):
        px = 0.92 * sx
        parts.append(mg.part("cube", dark, loc=(px, 0, post_h / 2),
                             scale=(0.1, 0.1, post_h), bevel=0.012, taper=0.9))
    # a little broken notch chip on the right post
    parts.append(mg.part("cube", dark, loc=(0.86, -0.04, 0.62),
                         scale=(0.04, 0.05, 0.12), bevel=0.005))

    # --- rails (two horizontal beams) ---
    rail_len = 1.9
    for rz in (0.72, 0.36):
        parts.append(mg.part("cube", dark, loc=(0, 0, rz),
                             scale=(rail_len, 0.07, 0.09), bevel=0.012))

    # --- picket builders ---
    def eared_outline(w, body_h, ear_h):
        return [(-w / 2, 0), (-w / 2, body_h), (-w / 4, body_h + ear_h),
                (0, body_h + ear_h * 0.35), (w / 4, body_h + ear_h),
                (w / 2, body_h), (w / 2, 0)]

    def snapped_outline(w, h):
        return [(-w / 2, 0), (-w / 2, h), (-w / 6, h + 0.05),
                (w / 6, h - 0.03), (w / 2, h + 0.02), (w / 2, 0)]

    pw, pt = 0.13, 0.03
    py = -0.075

    # eared full pickets
    for x, col in ((-0.72, tan), (-0.45, tan2), (-0.18, tan), (0.60, tan2)):
        parts.append(mg.extrude(eared_outline(pw, 0.9, 0.13), pt, col,
                                loc=(x, py, 0.06), bevel=0.006, smooth=False))

    # two snapped short pickets
    for x, h, col in ((0.12, 0.52, tan2), (0.36, 0.66, tan)):
        parts.append(mg.extrude(snapped_outline(pw, h), pt, col,
                                loc=(x, py, 0.06), bevel=0.006, smooth=False))
    # snapped-off fallen tip lying near the ground front
    parts.append(mg.part("cube", tan, loc=(0.2, -0.12, 0.07),
                         scale=(0.11, 0.03, 0.3), rot=(0, 0.9, 0), bevel=0.005))

    # crooked picket hanging from a single nail on the lower rail
    crook = mg.extrude(eared_outline(pw, 0.8, 0.11), pt, tan2,
                       loc=(0, 0, 0), bevel=0.006, smooth=False)
    mg.pivot(crook, (0, py - 0.02, 0.62))
    crook = mg.copy(crook, loc=(0.30, py - 0.02, 0.62), rot=(0, 0.42, 0))
    parts.append(crook)

    # nails / bolts on richer tiers
    if mg.at_least("mobile-high"):
        for x in (-0.72, -0.45, -0.18, 0.60):
            for rz in (0.72, 0.36):
                parts.append(mg.part("cyl", nail_c, loc=(x + 0.03, py - 0.02, rz),
                                     scale=(0.03, 0.03, 0.02),
                                     rot=(math.pi / 2, 0, 0), vertices=8))
        # the single nail the crooked picket hangs from
        parts.append(mg.part("cyl", nail_c, loc=(0.30, py + 0.01, 0.62),
                             scale=(0.035, 0.035, 0.03),
                             rot=(math.pi / 2, 0, 0), vertices=8))

    mg.join("zc_fence_broken", parts)
