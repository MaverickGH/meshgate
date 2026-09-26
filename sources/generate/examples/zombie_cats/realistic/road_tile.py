"""Square road tile: cracked asphalt slab with a yellow fish-shaped lane marking and a few cracks."""
import math


def build(mg):
    asphalt = mg.color("asphalt", (0.085, 0.088, 0.10), rough=0.92, metal=0.0)
    paint = mg.color("paint_yellow", (0.86, 0.68, 0.12), rough=0.55, metal=0.0)
    crack = mg.color("crack_dark", (0.03, 0.03, 0.035), rough=0.95, metal=0.0)

    size, thick = 2.0, 0.10
    parts = []

    # base slab, flat straight edges so tiles line up (only a tiny top chamfer)
    parts.append(mg.part("cube", asphalt, loc=(0, 0, thick / 2),
                         scale=(size, size, thick), bevel=0.004))

    # yellow fish-shaped lane marking, painted flush in the centre (thin flat plate)
    fish = [
        (0.40, 0.0), (0.28, 0.11), (0.08, 0.15), (-0.14, 0.11),
        (-0.30, 0.09), (-0.50, 0.22), (-0.40, 0.0),
        (-0.50, -0.22), (-0.30, -0.09), (-0.14, -0.11),
        (0.08, -0.15), (0.28, -0.11),
    ]
    marking = mg.extrude(fish, 0.004, paint, loc=(0, 0, thick + 0.001),
                         rot=(math.pi / 2, 0, 0))
    parts.append(marking)

    # a few cracks scored across the asphalt (richer tiers only)
    if mg.at_least("mobile-high"):
        rng = mg.rng
        n = 5 if mg.at_least("pc") else 3
        for i in range(n):
            cx = rng.uniform(-0.7, 0.7)
            cy = rng.uniform(-0.7, 0.7)
            length = rng.uniform(0.4, 1.0)
            ang = rng.uniform(0, math.pi)
            parts.append(mg.part("cube", crack,
                                 loc=(cx, cy, thick - 0.006),
                                 scale=(length, 0.012, 0.02),
                                 rot=(0, 0, ang)))

    mg.join("zc_road_tile", parts)
