"""Toxic cat-food can, written by an AI model that saw only the MeshGate prompt and toxic_can_picture.png
(a render of the Zombie Cats pack asset). Built cleanly on the first attempt: 1.5k tris on mobile-low, 24k on pc.
"""
import math


def build(mg):
    purple = mg.color("purple_paint", "#5a2a88", rough=0.45, metal=0.1)
    grey = mg.color("band_grey", "#55585e", rough=0.5, metal=0.15)
    lid_grey = mg.color("lid_grey", "#a8aaad", rough=0.5, metal=0.15)
    goo = mg.color("goo", "#6cbd3c", rough=0.3)
    blue = mg.color("emblem_blue", "#4b87c6", rough=0.5)
    steel = mg.color("steel", "#8c8f94", rough=0.35, metal=1.0)

    R = 0.15      # body radius
    H = 0.47      # top of the upper band
    parts = []

    # bottom grey band
    parts.append(mg.lathe([(0, 0), (R - 0.008, 0), (R + 0.002, 0.01), (R + 0.005, 0.02),
                           (R + 0.005, 0.07), (R - 0.002, 0.085), (0, 0.085)], grey, segments=32))
    # purple painted body with a gentle bulge
    parts.append(mg.lathe([(0, 0.07), (R - 0.004, 0.07), (R + 0.002, 0.15), (R + 0.004, 0.23),
                           (R + 0.002, 0.31), (R - 0.004, 0.385), (0, 0.385)], purple, segments=32))
    # top grey band with a recessed rim that holds the goo
    parts.append(mg.lathe([(0, 0.37), (R - 0.002, 0.37), (R + 0.006, 0.38), (R + 0.007, 0.455),
                           (R + 0.002, H), (R - 0.012, H), (R - 0.014, H - 0.01), (0, H - 0.01)],
                          grey, segments=32))
    # goo surface, slightly domed above the rim
    parts.append(mg.lathe([(0, H - 0.012), (R - 0.01, H - 0.012), (R - 0.006, H + 0.004),
                           (R - 0.03, H + 0.014), (0, H + 0.018)], goo, segments=32))

    # bubbles on the goo
    bubbles = [(-0.06, -0.07, 0.016), (0.02, -0.09, 0.015), (0.08, 0.02, 0.014), (-0.02, 0.05, 0.013)]
    if mg.at_least("mobile-mid"):
        bubbles += [(0.05, -0.04, 0.01), (-0.09, 0.0, 0.009), (0.0, 0.0, 0.011)]
    for x, y, r in bubbles:
        parts.append(mg.part("sphere", goo, loc=(x, y, H + 0.012), scale=(2 * r, 2 * r, 2 * r),
                             segments=12, ring_count=8))

    # emblem on the front: blue blob with a triangle tail (a simple fish-like symbol)
    parts.append(mg.part("sphere", blue, loc=(-0.02, -R + 0.004, 0.205), scale=(0.065, 0.02, 0.035),
                         segments=16, ring_count=8))
    parts.append(mg.extrude([(0.012, 0.205), (0.052, 0.185), (0.052, 0.225)], 0.022, blue,
                            loc=(0, -R + 0.005, 0), bevel=0.002))

    # hinge at the back of the top band
    hinge_y, hinge_z = R + 0.012, H + 0.006
    parts.append(mg.tube([(-0.05, hinge_y, hinge_z), (0.05, hinge_y, hinge_z)], 0.008, steel, sides=8))
    parts.append(mg.part("cube", steel, loc=(0, R + 0.006, H - 0.012), scale=(0.08, 0.012, 0.04), bevel=0.003))

    # lid standing open, tilted back around the hinge (static pose as in the reference)
    rl = R + 0.012
    a = -2.0
    cx_y = hinge_y - rl * math.cos(a)
    cx_z = hinge_z - rl * math.sin(a)
    parts.append(mg.part("cyl", lid_grey, loc=(0, cx_y, cx_z), scale=(2 * rl, 2 * rl, 0.014),
                         rot=(a, 0, 0), vertices=32, bevel=0.004))
    if mg.at_least("mobile-mid"):
        # raised lip ring on the lid's outer face
        ny, nz = -math.sin(a), math.cos(a)
        parts.append(mg.part("torus", lid_grey, loc=(0, cx_y - ny * 0.007, cx_z - nz * 0.007),
                             rot=(a, 0, 0), major_radius=rl - 0.02, minor_radius=0.006))

    # rolled edges on the bands
    if mg.at_least("mobile-high"):
        for z, r in ((0.083, R + 0.001), (0.372, R + 0.003), (H - 0.002, R + 0.001)):
            parts.append(mg.part("torus", grey, loc=(0, 0, z), major_radius=r, minor_radius=0.005))

    # rivets on the bands
    if mg.at_least("pc"):
        n = 12
        for i in range(n):
            t = 2 * math.pi * (i + 0.5) / n
            for z in (0.045, 0.415):
                parts.append(mg.part("sphere", steel, loc=((R + 0.006) * math.cos(t), (R + 0.006) * math.sin(t), z),
                                     scale=(0.012, 0.012, 0.012), segments=8, ring_count=6))

    # goo puddles on the ground around the base
    puddles = [(0.13, -0.19, 0.2, 0.14), (-0.03, -0.12, 0.13, 0.1), (-0.18, -0.04, 0.12, 0.09)]
    if mg.at_least("mobile-high"):
        puddles.append((0.2, -0.08, 0.06, 0.05))
    for x, y, sx, sy in puddles:
        parts.append(mg.part("cyl", goo, loc=(x, y, 0.008), scale=(sx, sy, 0.016), vertices=24, bevel=0.006))

    mg.join("toxic_can", parts)
