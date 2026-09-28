"""zc_cardboard_barricade, realistic: the same stack of cardboard boxes with a zombie cat peeking from the top box —
kraft cardboard, packing tape and printed shipping labels (this way up, recycle)."""
import math


def build(mg):
    card = mg.color("cardboard", "#a86f3c", rough=0.9, material="cardboard")
    card_l = mg.color("cardboard_light", "#b47a45", rough=0.9, material="cardboard")
    card_d = mg.color("cardboard_dark", "#93602f", rough=0.88, material="cardboard")
    tape = mg.color("packing_tape", "#b98c55", rough=0.35, material="plain")
    ink = mg.color("print_ink", "#3a2a1e", rough=0.8, material="plain")
    ear = mg.color("ear_green", "#6f7c61", rough=0.7, material="plain")
    eye = mg.color("eye_glow", (0.35, 1.0, 0.25), rough=0.3, glow=3.0, material="plain")

    P = []

    def box(cx, cz, w, h, d=0.56, cy=0.0):
        P.append(mg.part("cube", card, loc=(cx, cy, cz), scale=(w, d, h), bevel=0.025))
        if mg.at_least("mobile-mid"):
            # folded top flaps (lighter)
            P.append(mg.part("cube", card_l, loc=(cx, cy, cz + h / 2 - 0.015),
                             scale=(w * 0.97, d * 0.97, 0.05), bevel=0.01))
            # tape seam strip across the top
            P.append(mg.part("cube", tape, loc=(cx, cy, cz + h / 2 + 0.005),
                             scale=(0.09, d * 0.97, 0.03)))
            # packing-tape patch on the front (-Y) face
            P.append(mg.part("cube", card_d, loc=(cx, cy - d / 2 - 0.004, cz - h * 0.05),
                             scale=(w * 0.30, 0.012, h * 0.55), bevel=0.005))

    # bottom row (three boxes)
    box(-0.60, 0.28, 0.56, 0.55)
    box(0.00, 0.27, 0.56, 0.53)
    box(0.60, 0.28, 0.56, 0.55, cy=0.02)

    # top row: left box and the cat box (right)
    box(-0.45, 0.83, 0.54, 0.53)
    cx, cz, cw, ch, cd = 0.42, 0.83, 0.55, 0.53, 0.54
    box(cx, cz, cw, ch, d=cd)

    # crumpled paper balls (decorative, dented)
    P.append(mg.part("ico", card_l, loc=(-0.42, 0.0, 1.20), scale=(0.18, 0.18, 0.17),
                     subdiv=1, bevel=0.01))
    P.append(mg.part("ico", card_l, loc=(cx + 0.36, -0.10, 0.86), scale=(0.15, 0.15, 0.15),
                     subdiv=1, bevel=0.01))

    # zombie cat: pointed ears on top of the cat box
    top = cz + ch / 2
    for dx in (-0.14, 0.14):
        P.append(mg.part("cone", ear, loc=(cx + dx, 0.06, top + 0.11),
                         scale=(0.13, 0.13, 0.26), radius2=0.0))

    # glowing green eyes on the front face
    fy = cx * 0 - cd / 2 - 0.02
    for dx in (-0.11, 0.11):
        P.append(mg.part("sphere", eye, loc=(cx + dx, fy, 0.86), scale=(0.09, 0.06, 0.09)))

    # cardboard-roll "wheels" at the front base corners
    for wx in (-0.80, 0.80):
        P.append(mg.part("cyl", card_d, loc=(wx, -0.31, 0.13), scale=(0.24, 0.24, 0.12),   # clear of the box front
                         rot=(math.pi / 2, 0, 0), vertices=16))

    # printed shipping labels: "this way up" arrows and a recycle mark, a little proud of the front faces
    if mg.at_least("mobile-mid"):
        def arrow(x, z):
            P.append(mg.extrude([(-0.018, 0), (0.018, 0), (0.018, 0.05), (0.038, 0.05), (0, 0.09), (-0.038, 0.05),
                                 (-0.018, 0.05)], 0.004, ink, loc=(x, -0.283, z)))
        arrow(-0.52, 0.93)
        arrow(-0.44, 0.93)
        for bx, bz in ((0.72, 0.12), (0.52, 0.72)):   # recycle triangles
            P.append(mg.extrude([(-0.05, 0), (0.05, 0), (0, 0.085)], 0.004, ink, loc=(bx, -0.283, bz)))
            P.append(mg.extrude([(-0.028, 0.015), (0.028, 0.015), (0, 0.063)], 0.006, card, loc=(bx, -0.285, bz)))

    # dented corner accents (only when there is budget)
    if mg.at_least("mobile-high"):
        for (dx, dz) in ((-0.86, 0.05), (0.86, 0.05), (-0.70, 1.06)):
            P.append(mg.part("cube", card_d, loc=(dx, -0.24, dz),
                             scale=(0.09, 0.09, 0.09), bevel=0.03))

    mg.join("zc_cardboard_barricade", P)
