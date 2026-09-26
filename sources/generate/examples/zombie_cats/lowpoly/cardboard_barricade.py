"""zc_cardboard_barricade: stacked cardboard boxes with taped seams; a zombie cat hides in the top box."""
import math


def build(mg):
    mg.mirror_x = False  # asset is intentionally asymmetric (character in one box)
    card = mg.color("card", "#a67c47", rough=0.85)
    card2 = mg.color("card2", "#96703e", rough=0.85)
    tape = mg.color("tape", "#6f5330", rough=0.7)
    fur = mg.color("fur", "#54604f", rough=0.9)
    ear_in = mg.color("ear_in", "#3a4438", rough=0.9)
    eye = mg.color("eye", "#5cff4a", rough=0.3, glow=3.0)

    parts = []

    def box(loc, scale, col=card, rot=(0, 0, 0), tape_on=True):
        w, d, h = scale
        parts.append(mg.part("cube", col, loc=loc, scale=scale, rot=rot, bevel=0.02))
        if tape_on:
            # seam of tape across the top
            parts.append(mg.part("cube", tape,
                                  loc=(loc[0], loc[1], loc[2] + h / 2),
                                  scale=(w + 0.006, 0.09, 0.02), rot=rot))
            if mg.at_least("mobile-mid"):
                # a band wrapping the upper front
                parts.append(mg.part("cube", tape,
                                     loc=(loc[0], loc[1] - d / 2, loc[2] + h * 0.18),
                                     scale=(w + 0.008, 0.02, 0.07), rot=rot))

    # ---- bottom row -------------------------------------------------------
    box((-0.60, 0.02, 0.30), (0.60, 0.60, 0.60), col=card)
    box((0.06, -0.06, 0.32), (0.72, 0.66, 0.64), col=card2, rot=(0, 0, 0.02))
    box((0.66, 0.06, 0.28), (0.55, 0.55, 0.56), col=card, rot=(0, 0, -0.03))

    # ---- top row ----------------------------------------------------------
    box((-0.50, -0.02, 0.90), (0.60, 0.60, 0.62), col=card2, rot=(0, 0, -0.02))

    # cat box (top right)
    cx, cy, cz = 0.40, -0.08, 0.92
    cw, cd, ch = 0.56, 0.56, 0.60
    box((cx, cy, cz), (cw, cd, ch), col=card, rot=(0, 0, 0.02))

    barricade = mg.join("zc_cardboard_barricade", parts)

    # ---- zombie cat hiding inside the top box -----------------------------
    cat = []
    top_z = cz + ch / 2
    front_y = cy - cd / 2
    for ex in (cx - 0.13, cx + 0.13):
        cat.append(mg.part("cone", fur, loc=(ex, cy + 0.02, top_z + 0.02),
                           scale=(0.14, 0.14, 0.30)))
        cat.append(mg.part("cone", ear_in, loc=(ex, cy - 0.02, top_z + 0.03),
                           scale=(0.07, 0.07, 0.22)))
    for ex in (cx - 0.08, cx + 0.08):
        cat.append(mg.part("sphere", eye, loc=(ex, front_y - 0.01, cz + 0.06),
                           scale=(0.05, 0.05, 0.05), segments=10, ring_count=8))
    mg.join("zombie_cat", cat)
