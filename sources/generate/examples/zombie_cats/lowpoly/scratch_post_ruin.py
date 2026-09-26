"""Ruined cat scratching post: carpeted base, sisal-rope pole, tilted top platform, side shelf."""
import math


def build(mg):
    carpet = mg.color("carpet", "#8a5470", rough=0.9)
    carpet_dk = mg.color("carpet_dk", "#6d4059", rough=0.9)
    rope = mg.color("rope", "#9a8b5a", rough=0.95)
    rope_dk = mg.color("rope_dk", "#6f6238", rough=0.95)

    parts = []

    # --- carpeted square base ---
    base_w, base_t = 0.62, 0.05
    parts.append(mg.part("cube", carpet, loc=(0, 0, base_t / 2),
                         scale=(base_w, base_w, base_t), bevel=0.012))
    # torn carpet patch on base
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet_dk, loc=(0.12, -0.1, base_t + 0.005),
                             scale=(0.16, 0.12, 0.012), rot=(0, 0, 0.3), bevel=0.005))

    # --- sisal rope pole: stacked frayed rings ---
    pole_r = 0.09
    z0 = base_t
    z_top = 0.95
    n_rings = 7
    ring_h = (z_top - z0) / n_rings
    for i in range(n_rings):
        cz = z0 + ring_h * (i + 0.5)
        col = rope if i % 2 == 0 else rope_dk
        # slightly frayed: vary radius a little
        rr = pole_r * (1.0 + (0.12 if i % 2 == 0 else 0.0))
        parts.append(mg.part("cyl", col, loc=(0, 0, cz),
                             scale=(rr * 2, rr * 2, ring_h * 0.92),
                             vertices=12, smooth=False))
    # inner core so pole reads solid
    parts.append(mg.part("cyl", rope_dk, loc=(0, 0, (z0 + z_top) / 2),
                         scale=(pole_r * 1.6, pole_r * 1.6, z_top - z0),
                         vertices=12, smooth=False))
    # frayed rope bits near top
    if mg.at_least("mobile-high"):
        for k in range(6):
            a = k * math.pi / 3
            parts.append(mg.tube(
                [(pole_r * math.cos(a), pole_r * math.sin(a), z_top - 0.04),
                 (pole_r * 1.5 * math.cos(a), pole_r * 1.5 * math.sin(a), z_top - 0.02 + mg.rng.uniform(-0.02, 0.03))],
                0.012, rope, sides=5, smooth=False))

    # --- cracked side shelf (mid height) ---
    sh_w, sh_d, sh_t = 0.34, 0.26, 0.045
    shz = 0.5
    parts.append(mg.part("cube", carpet, loc=(-0.34, 0.06, shz),
                         scale=(sh_w, sh_d, sh_t), rot=(0, 0.06, 0.05), bevel=0.01))
    if mg.at_least("mobile-mid"):
        # crack line
        parts.append(mg.part("cube", carpet_dk, loc=(-0.34, 0.06, shz + sh_t / 2),
                             scale=(0.02, sh_d * 0.8, 0.02), rot=(0, 0, 0.4)))

    # --- tilted square top platform ---
    top_w, top_t = 0.5, 0.05
    topz = z_top + 0.06
    parts.append(mg.part("cube", carpet, loc=(0.05, 0.02, topz),
                         scale=(top_w, top_w, top_t),
                         rot=(0.13, -0.1, 0.0), bevel=0.014))
    # torn patch on top
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet_dk, loc=(-0.1, -0.05, topz + 0.03),
                             scale=(0.1, 0.06, 0.012), rot=(0.13, -0.1, 0.2), bevel=0.004))

    mg.join("zc_scratch_post_ruin", parts)
