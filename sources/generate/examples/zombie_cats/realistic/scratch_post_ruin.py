"""Ruined cat scratching post: carpeted base, sisal-rope pole, tilted top platform, cracked side shelf."""
import math


def build(mg):
    carpet = mg.color("carpet", "#8a5a78", rough=0.92)
    carpet2 = mg.color("carpet_dark", "#734a63", rough=0.92)
    rope = mg.color("rope", "#b3a26a", rough=0.85)
    rope_d = mg.color("rope_dark", "#8f7d4a", rough=0.88)
    wood = mg.color("wood", "#5a4632", rough=0.8)

    parts = []

    # --- carpeted square base ---
    bw = 0.44
    parts.append(mg.part("cube", carpet, loc=(0, 0, 0.025), scale=(bw, bw, 0.05), bevel=0.012))
    # torn corner flap (worn carpet edge)
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet2, loc=(bw * 0.32, -bw * 0.36, 0.052),
                             scale=(0.12, 0.1, 0.012), rot=(0.1, 0, 0.3), bevel=0.004))

    # --- rope-wrapped pole ---
    z0, z1 = 0.05, 0.98
    core_r = 0.05
    parts.append(mg.part("cyl", wood, loc=(0, 0, (z0 + z1) / 2),
                         scale=(core_r * 1.9, core_r * 1.9, z1 - z0), vertices=20))
    n = 11
    for i in range(n):
        z = z0 + (z1 - z0) * (i + 0.5) / n
        parts.append(mg.part("torus", rope, loc=(0, 0, z),
                             major_radius=core_r, minor_radius=0.021))
    # thin rope bridging bands so the wrap reads continuous
    parts.append(mg.part("cyl", rope_d, loc=(0, 0, (z0 + z1) / 2),
                         scale=(core_r * 2.02, core_r * 2.02, z1 - z0), vertices=20))

    # frayed loose rope ends on richer tiers
    if mg.at_least("mobile-high"):
        for k in range(4):
            a = k * 1.7
            zz = z0 + 0.06 + k * 0.02
            r = core_r + 0.01
            p0 = (math.cos(a) * r, math.sin(a) * r, zz)
            p1 = (math.cos(a) * (r + 0.05), math.sin(a) * (r + 0.05), zz - 0.04)
            parts.append(mg.tube([p0, p1], 0.006, rope, sides=6))

    # --- cracked side shelf ---
    sh_z = 0.52
    sh_w = 0.30
    if mg.at_least("pc"):
        # two halves with a gap = the crack
        parts.append(mg.part("cube", carpet, loc=(-0.20, 0.0, sh_z),
                             scale=(sh_w, sh_w * 0.52 - 0.01, 0.045),
                             rot=(0, 0, 0.05), bevel=0.01))
        parts.append(mg.part("cube", carpet, loc=(-0.20, sh_w * 0.28, sh_z + 0.002),
                             scale=(sh_w, sh_w * 0.42, 0.045),
                             rot=(0.02, 0, -0.02), bevel=0.01))
    else:
        parts.append(mg.part("cube", carpet, loc=(-0.20, 0.02, sh_z),
                             scale=(sh_w, sh_w, 0.045), rot=(0, 0, 0.03), bevel=0.01))

    # --- tilted top platform ---
    tp_z = 1.02
    tw = 0.40
    parts.append(mg.part("cube", carpet, loc=(0.03, 0.0, tp_z),
                         scale=(tw, tw, 0.05), rot=(0.14, 0.02, 0.32), bevel=0.014))
    # worn scratch groove on the platform (small darker patch)
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet2, loc=(-0.06, -0.06, tp_z + 0.04),
                             scale=(0.09, 0.05, 0.01), rot=(0.14, 0.02, 0.32), bevel=0.003))

    mg.join("zc_scratch_post_ruin", parts)
