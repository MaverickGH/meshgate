"""Ruined cat scratching post: pink carpeted base, sisal-rope-wrapped pole, tilted top platform, cracked side shelf."""
import math


def build(mg):
    fabric = mg.color("fabric", "#d94a9e", rough=0.9, material="fabric")          # pink carpet
    fabric_w = mg.color("fabric_worn", "#e6a7cf", rough=0.95, material="fabric")   # faded worn edges
    rope = mg.color("rope", "#c9a56a", rough=0.85, material="fabric")              # sisal rope
    rope_d = mg.color("rope_dark", "#9c7b46", rough=0.9, material="fabric")        # shaded/dirty rope
    wood = mg.color("wood", "#b08a5a", rough=0.8, material="wood")                 # exposed board
    metal = mg.color("iron", (0.35, 0.35, 0.38), rough=0.45, metal=1.0)           # staples/screws

    parts = []

    def platform(cx, cy, cz, w, d, t, rx=0.0, ry=0.0, worn=True):
        pl = []
        pl.append(mg.part("cube", fabric, loc=(cx, cy, cz), scale=(w, d, t), rot=(rx, ry, 0), bevel=0.008))
        if worn and mg.at_least("mobile-mid"):
            # worn/torn lighter rim strips along the edges
            pl.append(mg.part("cube", fabric_w, loc=(cx, cy - d / 2, cz + t * 0.1),
                              scale=(w * 0.96, 0.02, t * 0.5), rot=(rx, ry, 0)))
            pl.append(mg.part("cube", fabric_w, loc=(cx, cy + d / 2, cz + t * 0.1),
                              scale=(w * 0.96, 0.02, t * 0.5), rot=(rx, ry, 0)))
        return pl

    # ---- base ----
    bw = 0.52
    parts += platform(0, 0, 0.03, bw, bw, 0.06)
    # torn carpet patch exposing board on base corner
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", wood, loc=(0.17, 0.16, 0.055),
                             scale=(0.12, 0.12, 0.02), rot=(0, 0, 0.3), bevel=0.005))

    # ---- rope pole ----
    z0, z1 = 0.06, 1.02
    rp = 0.058          # pole core radius / helix radius
    rope_r = 0.026      # rope thickness
    # core cylinder so gaps between coils never see through
    parts.append(mg.part("cyl", rope_d, loc=(0, 0, (z0 + z1) / 2),
                         scale=(rp * 1.5, rp * 1.5, z1 - z0), vertices=16))
    # helical wrapped rope
    coils = 22
    per = max(6, mg.seg(12))
    steps = coils * per
    pts, radii = [], []
    for i in range(steps + 1):
        a = i / per * 2 * math.pi
        z = z0 + (z1 - z0) * i / steps
        pts.append((rp * math.cos(a), rp * math.sin(a), z))
        radii.append(rope_r)
    parts.append(mg.tube(pts, 0, rope, radii=radii, sides=max(6, mg.seg(8))))

    # frayed loose rope bits
    if mg.at_least("mobile-high"):
        for _ in range(6):
            a = mg.rng.uniform(0, 2 * math.pi)
            z = mg.rng.uniform(z0 + 0.1, z1 - 0.1)
            bx, by = rp * math.cos(a), rp * math.sin(a)
            ex = bx + math.cos(a) * mg.rng.uniform(0.04, 0.09)
            ey = by + math.sin(a) * mg.rng.uniform(0.04, 0.09)
            ez = z + mg.rng.uniform(-0.03, 0.03)
            parts.append(mg.tube([(bx, by, z), (ex, ey, ez)], 0,
                                 rope, radii=[0.012, 0.002], sides=6))

    # ---- cracked side shelf (viewer's left = -X) ----
    sx, sz = -0.30, 0.50
    sw = 0.36
    # split into two boards with a crack gap, exposing wood between
    parts.append(mg.part("cube", wood, loc=(sx, 0, sz), scale=(sw, 0.30, 0.05), bevel=0.006))
    parts.append(mg.part("cube", fabric, loc=(sx - 0.10, 0, sz + 0.005),
                        scale=(sw * 0.42, 0.29, 0.055), bevel=0.006))
    parts.append(mg.part("cube", fabric, loc=(sx + 0.11, 0, sz + 0.005),
                        scale=(sw * 0.40, 0.29, 0.055), rot=(0, 0.12, 0), bevel=0.006))
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", fabric_w, loc=(sx, 0, sz + 0.03),
                            scale=(sw * 0.96, 0.02, 0.02)))

    # ---- tilted top platform ----
    tw, td = 0.46, 0.52
    tz = 1.12
    tilt = 0.11
    parts += platform(0, -0.03, tz, tw, td, 0.055, rx=tilt)
    # staples / small metal fittings on top
    if mg.at_least("mobile-high"):
        for dx, dy in [(-0.05, 0.02), (-0.02, 0.03)]:
            parts.append(mg.part("cube", metal, loc=(dx, dy, tz + 0.03 + dy * math.tan(tilt)),
                                scale=(0.03, 0.02, 0.012), rot=(tilt, 0, 0.2)))

    mg.join("zc_scratch_post_ruin", parts)
