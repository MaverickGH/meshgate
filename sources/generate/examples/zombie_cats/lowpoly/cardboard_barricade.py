"""Zombie-cat cardboard barricade: stacked taped boxes, cat ears + glowing eyes peek from the top box."""
import math


def build(mg):
    # cardboard shades and packing tape
    card_a = mg.color("cardboard_a", "#d8b381", rough=0.85, material="cardboard")
    card_b = mg.color("cardboard_b", "#c9a06c", rough=0.85, material="cardboard")
    card_c = mg.color("cardboard_c", "#e0bd8f", rough=0.85, material="cardboard")
    tape = mg.color("cardboard_tape", "#b0854f", rough=0.7, material="cardboard")
    fur = mg.color("fabric_catfur", "#5f7d4a", rough=0.8, material="fabric")
    fur_dk = mg.color("fabric_catfur_dark", "#47613a", rough=0.8, material="fabric")
    eye = mg.color("eye_glow", (0.45, 1.0, 0.25), rough=0.4, glow=3.5, material="plain")

    shades = [card_a, card_b, card_c]

    def box(parts, cx, cy, cz, w, d, h, main, yaw=0.0):
        parts.append(mg.part("cube", main, loc=(cx, cy, cz), scale=(w, d, h),
                             rot=(0, 0, yaw), bevel=0.025))
        # horizontal packing-tape seam around the middle
        parts.append(mg.part("cube", tape, loc=(cx, cy, cz), scale=(w + 0.01, d + 0.01, 0.07),
                             rot=(0, 0, yaw)))
        if mg.at_least("mobile-mid"):
            # tape strip closing the top flaps
            parts.append(mg.part("cube", tape, loc=(cx, cy, cz + h / 2), scale=(0.05, d + 0.01, 0.012),
                                 rot=(0, 0, yaw)))
        if mg.at_least("mobile-high"):
            # short vertical tape tab down the front seam
            parts.append(mg.part("cube", tape, loc=(cx, cy - d / 2, cz + h / 4), scale=(0.05, 0.012, 0.2),
                                 rot=(0, 0, yaw)))

    w, d, h = 0.62, 0.55, 0.6
    parts = []

    # bottom row of three boxes
    box(parts, -0.60, 0.02, 0.30, w, d, h, shades[0], yaw=mg.rng.uniform(-0.04, 0.04))
    box(parts, 0.00, -0.04, 0.30, w, d, h, shades[1], yaw=mg.rng.uniform(-0.04, 0.04))
    box(parts, 0.60, 0.02, 0.30, w, d, h, shades[2], yaw=mg.rng.uniform(-0.04, 0.04))

    # top-left stacked box (tallest column)
    box(parts, -0.58, 0.02, 0.90, w, d, h, shades[1], yaw=mg.rng.uniform(-0.05, 0.05))

    # top-right box that hides the cat
    cx, cy, cz = 0.52, -0.03, 0.90
    box(parts, cx, cy, cz, w, d, h, shades[0], yaw=mg.rng.uniform(-0.03, 0.03))

    # cat ears: two pointed cones peeking from the top of the box
    top = cz + h / 2
    for ex in (-0.15, 0.15):
        parts.append(mg.part("cone", fur, loc=(cx + ex, cy + 0.02, top + 0.12),
                             scale=(0.15, 0.15, 0.26), vertices=8))
        if mg.at_least("mobile-mid"):
            parts.append(mg.part("cone", fur_dk, loc=(cx + ex, cy - 0.03, top + 0.10),
                                 scale=(0.09, 0.09, 0.16), vertices=8))

    barricade = mg.join("zc_cardboard_barricade", parts)

    # glowing green eyes on the front face of the cat box
    ez = cz + 0.05
    for ex in (-0.13, 0.13):
        mg.part("cyl", eye, loc=(cx + ex, cy - d / 2 - 0.01, ez),
                scale=(0.09, 0.09, 0.05), rot=(math.pi / 2, 0, 0), vertices=10)
    eyes = mg.join("zc_cat_eyes", [p for p in [mg.part("cyl", eye,
                   loc=(cx - 0.13, cy - d / 2 - 0.02, ez), scale=(0.09, 0.09, 0.04),
                   rot=(math.pi / 2, 0, 0), vertices=10),
                   mg.part("cyl", eye, loc=(cx + 0.13, cy - d / 2 - 0.02, ez),
                   scale=(0.09, 0.09, 0.04), rot=(math.pi / 2, 0, 0), vertices=10)]])
    mg.join("zc_cardboard_barricade_full", [barricade, eyes])
