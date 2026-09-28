"""zc_scratch_post_ruin, realistic — the same scratching post, well used: carpeted base, sisal-wrapped post, top\nplatform, a side step on a bracket with a toy hanging from it, loose carpet tufts."""
import math


def build(mg):
    carpet = mg.color("fabric", "#c06ac0", rough=0.9, material="fabric")
    carpet_dk = mg.color("fabric_worn", "#a7509f", rough=0.95, material="fabric")
    rope = mg.color("rope", "#c9a56a", rough=0.85, material="fabric")
    rope_dk = mg.color("rope_dark", "#9c7b46", rough=0.9, material="fabric")
    metal = mg.color("iron", (0.35, 0.35, 0.38), rough=0.45, metal=1.0)
    toy = mg.color("toy_pompom", "#e8c440", rough=0.9, material="fabric")
    toy_d = mg.color("toy_feather", "#e2dac8", rough=0.9, material="fabric")
    segs, minor, coils, bevel = 32, 8, 28, 0.015

    parts = []
    top_z = 1.0                      # underside of the top platform
    core_r = 0.075
    # ---- the base: a carpeted board, the post standing on its centre
    parts.append(mg.part("cube", carpet, loc=(0, 0, 0.045), scale=(0.56, 0.56, 0.09), bevel=bevel))
    # ---- the post: a core wrapped in sisal rope all the way from the base to the top platform
    parts.append(mg.part("cyl", rope_dk, loc=(0, 0, (0.09 + top_z) / 2), scale=(core_r * 2, core_r * 2, top_z - 0.09),
                         vertices=segs))
    n = coils
    for i in range(n):
        z = 0.09 + (top_z - 0.09) * (i + 0.5) / n
        parts.append(mg.part("torus", rope if i % 2 == 0 else rope_dk, loc=(0, 0, z), major_radius=core_r + 0.004,
                             minor_radius=(top_z - 0.09) / n * 0.5, major_segments=segs, minor_segments=minor))
    # ---- the top platform resting on the post, with a staple in the carpet
    parts.append(mg.part("cube", carpet, loc=(0.02, 0.0, top_z + 0.03), scale=(0.5, 0.42, 0.06), rot=(0, 0, 0.08), bevel=bevel))
    parts.append(mg.part("sphere", metal, loc=(0.04, -0.05, top_z + 0.064), scale=(0.025, 0.025, 0.012)))
    # ---- the side step: fixed to the post on a bracket, a toy on a string hanging from its edge
    sx = -(core_r + 0.13)
    parts.append(mg.part("cube", carpet, loc=(sx, -0.02, 0.56), scale=(0.27, 0.24, 0.05), bevel=bevel))
    parts.append(mg.part("cube", carpet_dk, loc=(-core_r - 0.03, -0.02, 0.51), scale=(0.07, 0.09, 0.08), bevel=bevel))  # bracket
    parts.append(mg.tube([(sx - 0.08, -0.08, 0.535), (sx - 0.085, -0.085, 0.4)], 0.004, rope_dk, sides=6))
    parts.append(mg.part("sphere", toy, loc=(sx - 0.085, -0.085, 0.37), scale=(0.07, 0.07, 0.07)))
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cone", toy_d, loc=(sx - 0.085, -0.085, 0.31), scale=(0.035, 0.035, 0.08), rot=(math.pi, 0, 0)))
        for (bx, by) in ((0.18, 0.2), (-0.2, 0.16), (0.21, -0.19)):   # loose carpet tufts on the base: well used
            parts.append(mg.part("cube", carpet_dk, loc=(bx, by, 0.1), scale=(0.035, 0.03, 0.02), rot=(0, 0, bx * 5)))
    post = mg.join("zc_scratch_post_ruin", parts)

    mg.sculpt(post, "noise", amount=0.002, scale=40)   # worn, fuzzy carpet and rope
