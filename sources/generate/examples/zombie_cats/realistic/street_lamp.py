"""Street lamp: round base, thin metal pole with a low rust band, a curved arm holding a fish-shaped warm-glowing lantern."""
import math


def build(mg):
    steel = mg.color("steel", (0.55, 0.57, 0.60), rough=0.42, metal=1.0)
    steel_d = mg.color("steel_d", (0.42, 0.44, 0.47), rough=0.5, metal=1.0)
    rust = mg.color("rust", (0.52, 0.28, 0.15), rough=0.78, metal=0.1)
    brass = mg.color("brass", (0.74, 0.56, 0.26), rough=0.35, metal=1.0)
    glow = mg.color("lamp", (1.0, 0.82, 0.45), rough=0.4, glow=2.6)

    parts = []
    pole_r = 0.045
    pole_top = 2.98

    # --- base ---
    parts.append(mg.part("cyl", steel_d, loc=(0, 0, 0.045), scale=(0.44, 0.44, 0.09), bevel=0.01))
    parts.append(mg.part("cyl", steel_d, loc=(0, 0, 0.12), scale=(0.24, 0.24, 0.07), taper=0.7, bevel=0.008))

    # --- pole ---
    parts.append(mg.part("cyl", steel, loc=(0, 0, (0.15 + pole_top) / 2),
                         scale=(pole_r * 2, pole_r * 2, pole_top - 0.15)))

    # --- rust band low on the pole ---
    parts.append(mg.part("cyl", rust, loc=(0, 0, 0.55),
                         scale=(pole_r * 2 + 0.012, pole_r * 2 + 0.012, 0.16)))

    # --- curved arm ---
    arm_pts = [(0, 0, pole_top - 0.05), (0, 0, pole_top + 0.06), (0.10, 0, pole_top + 0.14),
               (0.32, 0, pole_top + 0.16), (0.55, 0, pole_top + 0.12), (0.66, 0, pole_top + 0.05)]
    parts.append(mg.tube(arm_pts, pole_r * 0.9, steel, sides=12))

    # --- lantern hanger ---
    fx, fz = 0.62, 2.62
    parts.append(mg.part("cyl", steel, loc=(fx, 0, (fz + 0.24 + pole_top + 0.05) / 2 + 0.02),
                         scale=(0.02, 0.02, (pole_top + 0.05) - (fz + 0.24))))

    # --- fish-shaped lantern ---
    body = mg.part("sphere", glow, loc=(fx, 0, fz), scale=(0.52, 0.30, 0.30),
                   segments=mg.seg(24), taper=None)
    parts.append(body)
    # head slightly fuller toward the pole side
    parts.append(mg.part("sphere", glow, loc=(fx - 0.16, 0, fz), scale=(0.30, 0.28, 0.28)))
    # brass rim where the light shines out (bottom)
    parts.append(mg.part("cyl", brass, loc=(fx, 0, fz - 0.12), scale=(0.34, 0.24, 0.05), bevel=0.006))
    parts.append(mg.part("cyl", glow, loc=(fx, 0, fz - 0.15), scale=(0.30, 0.20, 0.03)))

    # tail fin
    tail = [(0.0, 0.10), (0.26, 0.20), (0.30, 0.02), (0.30, -0.14), (0.02, -0.06)]
    parts.append(mg.extrude(tail, 0.04, glow, loc=(fx + 0.26, 0, fz), bevel=0.005))

    if mg.at_least("mobile-high"):
        # small top and bottom fins
        topfin = [(0.0, 0.0), (0.12, 0.14), (0.20, 0.10), (0.10, -0.02)]
        parts.append(mg.extrude(topfin, 0.03, glow, loc=(fx + 0.02, 0, fz + 0.15), bevel=0.004))
        parts.append(mg.part("torus", brass, loc=(fx, 0, fz - 0.12),
                             scale=(0.68, 0.5, 0.5), minor_radius=0.02))
        # bolts on the base
        for i in range(6):
            a = i / 6 * math.tau
            parts.append(mg.part("cyl", steel_d, loc=(0.33 * math.cos(a), 0.33 * math.sin(a), 0.09),
                                 scale=(0.03, 0.03, 0.02), vertices=6))

    mg.join("zc_street_lamp", parts)
