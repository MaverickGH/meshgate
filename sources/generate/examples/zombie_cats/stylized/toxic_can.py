"""Giant opened cat-food tin with purple fish label, glowing green toxic goo spilling over the rim, and a peeled-back lid floating above."""
import math


def build(mg):
    metal = mg.color("metal_steel", "#b8bcc2", rough=0.35, metal=1.0)
    metal_d = mg.color("metal_dark", "#6e747c", rough=0.45, metal=1.0)
    label = mg.color("cardboard_purple", "#7d2fb0", rough=0.7)
    label_d = mg.color("cardboard_purple_dark", "#5f1f8a", rough=0.72)
    fish = mg.color("cardboard_teal", "#2fb6c9", rough=0.6)
    goo = mg.color("goo_green", "#8ee02a", rough=0.3, glow=1.6)

    R = 0.35          # can radius
    H = 0.62          # can body height
    rim = 0.03

    parts = []
    # can body profile (lathe) with slight rims top and bottom
    prof = [
        (R - 0.015, 0.0),
        (R, 0.02),
        (R, rim),                 # bottom rim top
        (R - 0.01, rim + 0.005),
        (R - 0.01, H - rim - 0.005),
        (R, H - rim),             # top rim
        (R, H),
        (R - 0.02, H + 0.005),
        (R - 0.03, H + 0.005),    # inner wall lip
        (R - 0.03, H - 0.08),     # goes down inside
    ]
    parts.append(mg.lathe(prof, metal, segments=48, cap=True))
    # inner bottom (toxic surface base) - dark metal interior floor
    parts.append(mg.part("cyl", metal_d, loc=(0, 0, H - 0.10), scale=(2 * (R - 0.03), 2 * (R - 0.03), 0.02), vertices=48))

    # purple label band
    band = [
        (R + 0.001, 0.12),
        (R + 0.006, 0.14),
        (R + 0.006, H - 0.14),
        (R + 0.001, H - 0.12),
    ]
    parts.append(mg.lathe(band, label, segments=48, cap=False))
    # label edge trims
    for z in (0.13, H - 0.13):
        parts.append(mg.lathe([(R + 0.004, z - 0.008), (R + 0.008, z), (R + 0.004, z + 0.008)], label_d, segments=48, cap=False))

    # fish emblem on the front (-Y), bowtie fish shape via extrude, wrapped flat outward
    fy = -(R + 0.012)
    fz = H * 0.5
    fish_out = [(-0.11, 0.0), (-0.02, 0.05), (0.06, 0.06), (0.12, 0.10),
                (0.12, -0.10), (0.06, -0.06), (-0.02, -0.05)]
    parts.append(mg.extrude([(x, z) for x, z in fish_out], 0.02, fish,
                            loc=(0.0, fy, fz), rot=(math.pi / 2, 0, 0), bevel=0.004))
    # eye dot
    parts.append(mg.part("sphere", label_d, loc=(-0.05, fy - 0.006, fz + 0.01), scale=(0.02, 0.02, 0.02)))

    can = mg.join("zc_toxic_can", parts)

    # ---- toxic goo: surface inside + drips over the rim ----
    goo_parts = []
    goo_z = H - 0.09
    goo_parts.append(mg.part("cyl", goo, loc=(0, 0, goo_z), scale=(2 * (R - 0.035), 2 * (R - 0.035), 0.04), vertices=48))
    # lumpy blobs on the goo surface
    for i in range(5):
        a = i * 1.3
        rr = mg.rng.uniform(0.05, 0.16)
        goo_parts.append(mg.part("sphere", goo,
                                 loc=(rr * math.cos(a), rr * math.sin(a), goo_z + 0.03),
                                 scale=(mg.rng.uniform(0.08, 0.13),) * 3))
    # big drip spilling down the front
    drip = [
        (0.06, H - 0.05), (0.07, H - 0.12), (0.05, H - 0.22),
        (0.055, H - 0.32), (0.03, H - 0.42), (0.045, H - 0.5), (0.0, H - 0.55),
    ]
    goo_parts.append(mg.tube([(x, fy - 0.005, z) for x, z in drip], 0.0,
                             radii=[0.05, 0.045, 0.04, 0.045, 0.035, 0.04, 0.02], color=goo, sides=10))
    goo_parts.append(mg.part("sphere", goo, loc=(0.0, fy - 0.01, H - 0.55), scale=(0.05, 0.05, 0.05)))
    # a couple of smaller side drips over the rim
    for sx in (-0.18, 0.20):
        goo_parts.append(mg.tube([(sx, fy + 0.02, H - 0.04), (sx * 0.95, fy + 0.02, H - 0.16)],
                                 0.0, radii=[0.035, 0.025], color=goo, sides=8))

    # floating bubbles above the can
    if mg.at_least("mobile-mid"):
        for bx, by, bz, br in [(-0.02, -0.05, H + 0.18, 0.06), (0.05, 0.03, H + 0.32, 0.045),
                               (-0.08, 0.02, H + 0.10, 0.05), (0.04, -0.02, H + 0.48, 0.05)]:
            goo_parts.append(mg.part("sphere", goo, loc=(bx, by, bz), scale=(br * 2,) * 3))

    # puddles on the ground
    for px, py, sc in [(-0.42, 0.38, 0.11), (0.34, 0.42, 0.13), (0.02, 0.55, 0.12), (-0.05, 0.5, 0.08)]:
        goo_parts.append(mg.part("sphere", goo, loc=(px, py, 0.015), scale=(sc * 2, sc * 2.4, 0.05)))

    goo_all = mg.join("zc_toxic_goo", goo_parts)

    # ---- lid: peeled back, floating above, tilted ----
    lid_parts = []
    lr = R + 0.02
    lid_prof = [
        (0.0, 0.0), (lr - 0.03, 0.0), (lr - 0.02, 0.012),
        (lr, 0.018), (lr, 0.03), (lr - 0.02, 0.036), (0.0, 0.03),
    ]
    lid_parts.append(mg.lathe(lid_prof, metal, segments=48, cap=True))
    # concentric ring detail on lid top
    if mg.at_least("mobile-high"):
        lid_parts.append(mg.lathe([(0.10, 0.03), (0.11, 0.032), (0.10, 0.034)], metal_d, segments=48, cap=False))
        lid_parts.append(mg.lathe([(0.24, 0.03), (0.25, 0.032), (0.24, 0.034)], metal_d, segments=48, cap=False))
    lid = mg.join("zc_toxic_lid", lid_parts)
    mg.attach(lid, can)
    # place it floating above, tilted like the reference
    mg.animate(lid, "float", [(1, (0, 0, 0)), (30, (0, 0, 0)), (60, (0, 0, 0))])
    mg.animate(lid, "float", [(1, (0.35, -0.15, 0.25)), (60, (0.35, -0.15, 0.25))],
               path="rotation_euler")
    mg.animate(lid, "float", [(1, (0, -0.02, H + 0.42)), (30, (0, -0.02, H + 0.47)),
                              (60, (0, -0.02, H + 0.42))], path="location")
