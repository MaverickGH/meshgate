"""Square cracked-asphalt road tile with a yellow fish-shaped lane marking and cracks."""
import math


def build(mg):
    mg.color("asphalt", "#23262b", rough=0.95)
    mg.color("asphalt_dark", "#171a1e", rough=0.95)
    mg.color("paint", "#c9a51f", rough=0.6)

    size, thick = 2.0, 0.1
    parts = []

    # slab body, flat straight edges so tiles line up (tiny top bevel only)
    parts.append(mg.part("cube", "asphalt", loc=(0, 0, thick / 2),
                         scale=(size, size, thick), bevel=0.01))

    top = thick + 0.002

    # --- yellow fish marking in the middle ---
    def fish(cx, cy, length, ang):
        pcs = []
        bl = length * 0.62          # body length
        bw = length * 0.30          # body width
        # oval body (flattened cylinder)
        pcs.append(mg.part("cyl", "paint", loc=(cx, cy, top),
                           scale=(bl, bw, 0.01), rot=(0, 0, ang), vertices=mg.seg(20)))
        # triangular tail behind the body
        tl = length * 0.34
        tx = cx - math.cos(ang) * (bl / 2 + tl * 0.35)
        ty = cy - math.sin(ang) * (bl / 2 + tl * 0.35)
        pcs.append(mg.part("cyl", "paint", loc=(tx, ty, top),
                           scale=(tl, bw * 1.1, 0.01), rot=(0, 0, ang),
                           vertices=3, exact=True))
        return pcs

    parts += fish(0.0, 0.0, 0.75, math.radians(200))
    if mg.at_least("mobile-mid"):
        parts += fish(-0.55, 0.45, 0.55, math.radians(210))

    # --- cracks ---
    if mg.at_least("mobile-high"):
        rng = mg.rng
        for _ in range(5):
            x = rng.uniform(-0.7, 0.7)
            y = rng.uniform(-0.7, 0.7)
            ang = rng.uniform(0, math.pi)
            ln = rng.uniform(0.3, 0.8)
            pts = []
            for t in (-0.5, -0.15, 0.2, 0.5):
                jx = rng.uniform(-0.04, 0.04)
                jy = rng.uniform(-0.04, 0.04)
                pts.append((x + math.cos(ang) * ln * t + jx,
                            y + math.sin(ang) * ln * t + jy,
                            top - 0.005))
            parts.append(mg.tube(pts, 0.012, "asphalt_dark",
                                 sides=4, cap=True, smooth=False))

    mg.join("zc_road_tile", parts)
