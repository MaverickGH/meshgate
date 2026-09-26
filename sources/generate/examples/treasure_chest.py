"""Example build code: a wooden treasure chest with a lid that opens (moving part: pivot + animate)."""
import math


def build(mg):
    mg.color("wood", "#8a5a2b", rough=0.8)
    mg.color("wood_dark", "#5b3a1a", rough=0.85)
    mg.color("iron", (0.25, 0.25, 0.27), rough=0.5, metal=1.0)
    mg.color("gold", "#e8b923", rough=0.25, metal=1.0, glow=0.6)

    w, d, h = 0.8, 0.5, 0.35
    base = [mg.part("cube", "wood", loc=(0, 0, h / 2), scale=(w, d, h), bevel=0.01)]
    for x in (-0.3, 0.3):   # iron bands
        base.append(mg.part("cube", "iron", loc=(x, 0, h / 2), scale=(0.05, d + 0.01, h + 0.01)))
    base.append(mg.part("cube", "iron", loc=(0, -d / 2 - 0.01, h - 0.06), scale=(0.1, 0.03, 0.12), bevel=0.005))
    if mg.at_least("mobile-mid"):   # coins peeking out, only when there is budget for them
        for i in range(6):
            base.append(mg.part("cyl", "gold", loc=(mg.rng.uniform(-0.3, 0.3), mg.rng.uniform(-0.15, 0.15), h + 0.005),
                                scale=(0.05, 0.05, 0.01), vertices=12))
    body = mg.join("chest_base", base)

    # lid: half cylinder along X, hinged at the back top edge
    lid_parts = [mg.part("cyl", "wood_dark", loc=(0, 0, h), scale=(d, d, w), rot=(0, math.pi / 2, 0), vertices=16),
                 mg.part("cyl", "iron", loc=(-0.3, 0, h), scale=(d + 0.02, d + 0.02, 0.05), rot=(0, math.pi / 2, 0), vertices=16),
                 mg.part("cyl", "iron", loc=(0.3, 0, h), scale=(d + 0.02, d + 0.02, 0.05), rot=(0, math.pi / 2, 0), vertices=16)]
    lid = mg.join("chest_lid", lid_parts)
    mg.pivot(lid, (0, d / 2, h))
    mg.attach(lid, body)
    mg.animate(lid, "open", [(1, (0, 0, 0)), (20, (-1.9, 0, 0)), (40, (-1.9, 0, 0)), (60, (0, 0, 0))])
