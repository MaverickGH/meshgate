"""zc_cardboard_barricade: stacked taped cardboard boxes hiding a zombie cat (ears + glowing eyes)."""
import math


def build(mg):
    # cardboard shades (clean base colours, weathering baked by MeshGate)
    mg.color("cardboard", "#b8955f", rough=0.9, material="cardboard")
    mg.color("cardboard_b", "#ad8a56", rough=0.9, material="cardboard")
    mg.color("cardboard_c", "#c1a06b", rough=0.9, material="cardboard")
    mg.color("tape", "#d9c9a2", rough=0.45, material="plain")
    mg.color("ear_green", "#59653d", rough=0.7, material="plain")
    mg.color("eye_green", "#7dff55", rough=0.4, glow=3.0, material="plain")

    parts = []

    def box(cx, cz, w, d, h, col, yaw=0.0, cy=0.0, dent=True):
        b = 0.02 + (0.01 if dent else 0.0)
        parts.append(mg.part("cube", col, loc=(cx, cy, cz), scale=(w, d, h),
                             rot=(0, 0, yaw), bevel=b))
        if mg.at_least("mobile-mid"):
            # packing tape band around the middle seam
            parts.append(mg.part("cube", "tape", loc=(cx, cy, cz),
                                 scale=(w + 0.014, d + 0.014, 0.09), rot=(0, 0, yaw)))
            # tape running over the top flaps
            parts.append(mg.part("cube", "tape", loc=(cx, cy, cz + h / 2),
                                 scale=(0.11, d + 0.014, 0.02), rot=(0, 0, yaw)))
        if mg.at_least("mobile-high"):
            # dented / crushed corner accents (small pushed-in cubes)
            for sx in (-1, 1):
                parts.append(mg.part("cube", col,
                                     loc=(cx + sx * (w / 2 - 0.03), cy - d / 2 + 0.02, cz - h / 2 + 0.05),
                                     scale=(0.09, 0.06, 0.09), rot=(0, 0, yaw + sx * 0.25), bevel=0.015))

    r = mg.rng
    # ---- bottom row (z 0 .. 0.55) ----
    box(-0.52, 0.28, 0.70, 0.70, 0.55, "cardboard",   yaw=r.uniform(-0.03, 0.03))
    box( 0.16, 0.27, 0.72, 0.74, 0.53, "cardboard_c", yaw=r.uniform(-0.03, 0.03))
    box( 0.74, 0.26, 0.52, 0.62, 0.51, "cardboard_b", yaw=r.uniform(-0.05, 0.05))

    # ---- top row (z 0.55 .. ~1.17) ----
    # tall left box (the "arrows" box)
    box(-0.50, 0.86, 0.66, 0.68, 0.62, "cardboard_b", yaw=r.uniform(-0.04, 0.04))
    # cat box on the right
    cx, cz, cw, cd, ch = 0.36, 0.85, 0.72, 0.72, 0.60
    box(cx, cz, cw, cd, ch, "cardboard", yaw=0.02)

    # crumpled paper ball resting on the left box
    parts.append(mg.part("ico", "cardboard_c", loc=(-0.50, 0.02, 1.23),
                         scale=(0.17, 0.17, 0.15), subdiv=1, bevel=0.01, smooth=False))

    # ---- zombie cat parts on the cat box ----
    top_z = cz + ch / 2
    front_y = -cd / 2
    # pointed ears peeking over the top
    for i, sx in enumerate((-1, 1)):
        parts.append(mg.part("cone", "ear_green",
                             loc=(cx + sx * 0.16, 0.06, top_z + 0.12),
                             scale=(0.14, 0.14, 0.34), rot=(sx * 0.12, 0, 0),
                             vertices=16))
    # glowing green eyes just proud of the front face
    for sx in (-1, 1):
        parts.append(mg.part("sphere", "eye_green",
                             loc=(cx + sx * 0.14, front_y + 0.02, cz - 0.02),
                             scale=(0.11, 0.11, 0.11)))
    # lumpy paw / paper blob peeking at the right side
    parts.append(mg.part("ico", "cardboard_b",
                         loc=(cx + cw / 2 + 0.03, front_y + 0.18, cz + 0.16),
                         scale=(0.17, 0.17, 0.16), subdiv=1, bevel=0.01, smooth=False))

    mg.join("zc_cardboard_barricade", parts)
