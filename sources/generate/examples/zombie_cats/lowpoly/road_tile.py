"""Square road tile: cracked dark asphalt with a yellow fish-shaped lane marking and a few cracks."""
import math


def build(mg):
    mg.color("asphalt", "#22242a", rough=0.95)
    mg.color("asphalt2", "#191b20", rough=0.95)
    mg.color("paint", "#c9a227", rough=0.55)

    size = 2.0
    thick = 0.1
    parts = []

    # slab body
    parts.append(mg.part("cube", "asphalt", loc=(0, 0, thick / 2), scale=(size, size, thick)))

    top = thick + 0.001  # surface z for markings

    # a few darker patches to read as worn/cracked asphalt
    if mg.at_least("mobile-mid"):
        for i in range(4):
            px = mg.rng.uniform(-0.7, 0.7)
            py = mg.rng.uniform(-0.7, 0.7)
            s = mg.rng.uniform(0.3, 0.6)
            parts.append(mg.part("cube", "asphalt2",
                                 loc=(px, py, thick - 0.005),
                                 scale=(s, s * 0.7, 0.012),
                                 rot=(0, 0, mg.rng.uniform(0, math.pi))))

    # cracks: thin dark grooves
    if mg.at_least("mobile-high"):
        for i in range(5):
            x0 = mg.rng.uniform(-0.8, 0.8)
            y0 = mg.rng.uniform(-0.8, 0.8)
            ang = mg.rng.uniform(0, math.pi)
            length = mg.rng.uniform(0.4, 0.9)
            parts.append(mg.part("cube", "asphalt2",
                                 loc=(x0, y0, thick - 0.002),
                                 scale=(length, 0.03, 0.02),
                                 rot=(0, 0, ang)))

    body = mg.join("zc_road_tile", parts)

    # yellow fish-shaped lane marking in the middle (built separately, then joined)
    fish = []
    # body: flat ellipse
    fish.append(mg.part("cyl", "paint", loc=(0, 0, top),
                        scale=(0.9, 0.45, 0.02), vertices=16))
    # tail: triangle (cube tapered to a point), pointing -X
    fish.append(mg.part("cube", "paint", loc=(-0.62, 0, top),
                        scale=(0.35, 0.4, 0.02), taper=0.0,
                        rot=(0, 0, -math.pi / 2)))
    marking = mg.join("zc_road_tile_paint", fish)

    mg.join("zc_road_tile_final", [body, marking])
