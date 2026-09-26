"""zc_cardboard_barricade: stacked cardboard boxes with taped seams; a zombie cat's ears and glowing eyes peek from the top box."""
import math


def build(mg):
    card_a = mg.color("cardboard_a", "#b0865200"[:7] if False else "#b08652", rough=0.88)
    card_b = mg.color("cardboard_b", "#a2794a", rough=0.9)
    card_c = mg.color("cardboard_c", "#b58f5c", rough=0.86)
    tape = mg.color("tape", "#7f6440", rough=0.55)
    fur = mg.color("cat_fur", "#5f6d58", rough=0.92)
    fur_dk = mg.color("cat_fur_dk", "#454f40", rough=0.92)
    eye = mg.color("eye_glow", (0.35, 1.0, 0.35), rough=0.3, glow=3.0)

    cards = [card_a, card_b, card_c]

    def add_box(parts, loc, scale, ci, seed, tape_axis="x"):
        r = mg.rng
        yaw = r.uniform(-0.035, 0.035)
        rot = (0.0, 0.0, yaw)
        w, d, h = scale
        parts.append(mg.part("cube", cards[ci % 3], loc=loc, scale=(w, d, h),
                             rot=rot, bevel=0.02))
        # dented / softened extra corner chamfer on rich tiers
        bev = 0.035 if mg.at_least("mobile-high") else 0.02
        # top tape seam
        top = loc[2] + h / 2
        if tape_axis == "x":
            parts.append(mg.part("cube", tape, loc=(loc[0], loc[1], top + 0.005),
                                 scale=(w * 1.005, 0.1, 0.02), rot=rot, bevel=0.004))
        else:
            parts.append(mg.part("cube", tape, loc=(loc[0], loc[1], top + 0.005),
                                 scale=(0.1, d * 1.005, 0.02), rot=rot, bevel=0.004))
        # front seam tape on some boxes
        if mg.at_least("mobile-mid") and seed % 2 == 0:
            fy = loc[1] - d / 2 - 0.004
            parts.append(mg.part("cube", tape, loc=(loc[0], fy, loc[2]),
                                 scale=(0.1, 0.02, h * 0.98), rot=rot, bevel=0.004))

    parts = []
    # bottom row
    add_box(parts, (0.05, -0.05, 0.32), (0.85, 0.66, 0.64), 0, 0, "x")
    add_box(parts, (-0.6, 0.06, 0.28), (0.56, 0.56, 0.56), 1, 1, "y")
    add_box(parts, (0.68, -0.1, 0.27), (0.5, 0.5, 0.52), 2, 2, "x")
    # top row (non-cat)
    add_box(parts, (-0.35, 0.05, 0.9), (0.62, 0.62, 0.62), 2, 3, "x")

    barricade = mg.join("boxes", parts)

    # --- cat box (top-right) with ears and glowing eyes ---
    cx, cy, cz = 0.4, -0.05, 0.9
    cw, cd, ch = 0.56, 0.56, 0.6
    cat = []
    cat.append(mg.part("cube", card_c, loc=(cx, cy, cz), scale=(cw, cd, ch), bevel=0.025))
    top = cz + ch / 2
    cat.append(mg.part("cube", tape, loc=(cx, cy, top + 0.005),
                       scale=(cw * 1.005, 0.1, 0.02), bevel=0.004))

    # ears: pointed cones poking up past the top flaps
    for ex in (-0.13, 0.13):
        cat.append(mg.part("cone", fur, loc=(cx + ex, cy + 0.11, top + 0.09),
                           scale=(0.12, 0.12, 0.24), vertices=12))
        if mg.at_least("mobile-high"):
            cat.append(mg.part("cone", fur_dk, loc=(cx + ex, cy + 0.09, top + 0.07),
                               scale=(0.06, 0.05, 0.16), vertices=10))

    # eyes: two small glowing green spheres on the front (-Y) face
    fy = cy - cd / 2 - 0.005
    for ex in (-0.09, 0.09):
        cat.append(mg.part("sphere", eye, loc=(cx + ex, fy, top - 0.14),
                           scale=(0.06, 0.05, 0.06)))

    cat_mesh = mg.join("cat_box", cat)
    mg.join("zc_cardboard_barricade", [barricade, cat_mesh])
