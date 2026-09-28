"""zc_toxic_can — giant opened cat-food tin with glowing green goo, purple label, peeled metal lid."""
import math


def build(mg):
    steel = mg.color("steel", "#c0c4cc", rough=0.35, metal=0.7)
    steel_lt = mg.color("steel_light", "#d4d8de", rough=0.3, metal=0.7)
    purple = mg.color("label_purple", (0.62, 0.13, 0.78), rough=0.55, material="cardboard")
    goo = mg.color("goo_green", (0.55, 0.88, 0.12), rough=0.25, glow=2.6, material="plain")
    goo_dk = mg.color("goo_dark", (0.42, 0.72, 0.08), rough=0.3, glow=1.6, material="plain")
    fish = mg.color("fish_blue", (0.16, 0.62, 0.78), rough=0.5, material="plain")
    fish_lt = mg.color("fish_light", (0.55, 0.85, 0.9), rough=0.5, material="plain")

    V = 16
    R = 0.36
    parts = []

    # --- can body: bottom rim, purple label, top rim ---
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.045), scale=(0.76, 0.76, 0.09), vertices=V, smooth=False, bevel=0.008))
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.11), scale=(0.735, 0.735, 0.05), vertices=V, smooth=False))
    parts.append(mg.part("cyl", purple, loc=(0, 0, 0.405), scale=(0.72, 0.72, 0.63), vertices=V, smooth=False))
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.70), scale=(0.735, 0.735, 0.05), vertices=V, smooth=False))
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.775), scale=(0.76, 0.76, 0.10), vertices=V, smooth=False, bevel=0.01))
    # inner rim lip
    parts.append(mg.part("cyl", steel_lt, loc=(0, 0, 0.815), scale=(0.70, 0.70, 0.02), vertices=V, smooth=False))

    # --- goo filling the top and its bubbling surface ---
    parts.append(mg.part("cyl", goo, loc=(0, 0, 0.755), scale=(0.68, 0.68, 0.12), vertices=V, smooth=False))
    parts.append(mg.part("sphere", goo, loc=(0, 0, 0.82), scale=(0.68, 0.68, 0.18), segments=V, smooth=False))
    # surface bubbles poking up
    for i in range(3):
        a = i * 2.1
        rr = 0.14 + 0.05 * i
        parts.append(mg.part("sphere", goo, loc=(rr * math.cos(a), rr * math.sin(a), 0.87 + 0.02 * i),
                             scale=(0.16, 0.16, 0.16), segments=12, smooth=False))

    # --- drips spilling over the rim down the label ---
    drip_ang = [-0.5, 0.1, 0.7, 1.4, -1.2]
    for k, a in enumerate(drip_ang):
        x, y = R * math.cos(a), R * math.sin(a)
        ln = 0.16 + 0.10 * ((k * 7) % 3)
        top = 0.78
        parts.append(mg.part("cyl", goo, loc=(x, y, top - ln / 2), scale=(0.09, 0.06, ln), vertices=8, smooth=False))
        parts.append(mg.part("sphere", goo, loc=(x, y, top - ln), scale=(0.11, 0.08, 0.11), segments=10, smooth=False))
        parts.append(mg.part("sphere", goo, loc=(x, y, top + 0.01), scale=(0.13, 0.09, 0.08), segments=10, smooth=False))

    # --- fish emblem on the front label (-Y) ---
    fout = [(-0.15, 0.0), (-0.02, 0.07), (0.14, 0.10), (0.06, 0.0), (0.14, -0.10), (-0.02, -0.07)]
    parts.append(mg.extrude(fout, 0.03, fish, loc=(0, -0.355, 0.40), smooth=False))
    if mg.at_least("mobile-high"):
        parts.append(mg.part("cyl", fish_lt, loc=(-0.08, -0.375, 0.40), scale=(0.05, 0.02, 0.05),
                             rot=(math.pi / 2, 0, 0), vertices=10, smooth=False))
        parts.append(mg.part("cyl", fish_lt, loc=(0.04, -0.375, 0.40), scale=(0.04, 0.02, 0.10),
                             rot=(math.pi / 2, 0, 0), vertices=8, smooth=False))

    # --- puddles on the ground ---
    pud = [(0.0, 0.55, 0.20), (-0.52, 0.30, 0.15), (0.48, -0.25, 0.14), (0.15, -0.55, 0.13)]
    for (px, py, pr) in pud:
        parts.append(mg.part("sphere", goo_dk, loc=(px, py, 0.02), scale=(pr * 2.2, pr * 2.2, 0.07),
                             segments=12, smooth=False))
        parts.append(mg.part("sphere", goo, loc=(px, py, 0.03), scale=(pr * 1.5, pr * 1.5, 0.06),
                             segments=10, smooth=False))

    # --- rising bubbles between can and lid ---
    for bx, by, bz, br in [(0.02, 0.05, 1.02, 0.13), (-0.1, 0.0, 0.95, 0.08), (0.08, -0.04, 1.14, 0.09), (-0.03, 0.02, 1.22, 0.07)]:
        parts.append(mg.part("sphere", goo, loc=(bx, by, bz), scale=(br, br, br), segments=10, smooth=False))

    can = mg.join("zc_toxic_can", parts)

    # --- the lid, floating well above the goo and tilted, as in the concept ---
    lid_dark = mg.color("steel_dark", "#6a707a", rough=0.4, metal=0.8)
    L, tilt = (0.0, -0.02, 1.5), (0.3, -0.12, 0.0)
    lp = []
    for dz, sc, col, verts in ((-0.01, 0.76, lid_dark, V), (0.02, 0.72, lid_dark, V), (0.04, 0.58, steel, V),
                               (0.055, 0.36, lid_dark, V), (0.065, 0.14, steel, 12)):
        lp.append(mg.part("cyl", col, loc=(L[0], L[1], L[2] + dz), scale=(sc * 0.85, sc * 0.85, 0.03 if dz < 0 else 0.02),
                          rot=tilt, vertices=verts, smooth=False))
    lid = mg.join("zc_toxic_can_lid", lp)
    mg.pivot(lid, L)
    mg.attach(lid, can)
    mg.animate(lid, "bubbles", [(0, L), (45, (L[0], L[1], L[2] + 0.03)), (90, L)], path="location")
