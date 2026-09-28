"""zc_toxic_can — a giant opened cat-food tin, after the concept: purple label with a teal fish, silver rims,
glowing green goo spilling over the rim and down the side into puddles, bubbles rising, the dark lid pushed up askew by the goo."""
import math


def build(mg):
    metal = mg.color("metal_steel", "#b8bcc2", rough=0.35, metal=1.0)
    metal_d = mg.color("metal_dark", "#4a5058", rough=0.45, metal=1.0)
    label = mg.color("cardboard_purple", "#7d2fb0", rough=0.7)
    label_d = mg.color("cardboard_purple_dark", "#3d1a5a", rough=0.72)
    fish = mg.color("cardboard_teal", "#2fb6c9", rough=0.6)
    goo = mg.color("goo_green", "#8ee02a", rough=0.3, glow=1.6)
    segs, smooth, bub_seg = 40, True, 16

    R, H = 0.33, 0.62      # can radius and height
    # ---- the tin: silver rims top and bottom, a purple label band, an inner lip the goo sits in
    body = [mg.lathe([(0.0, 0.0), (R - 0.012, 0.0), (R + 0.012, 0.012), (R + 0.012, 0.06), (R, 0.07), (R, H - 0.07),
                      (R + 0.012, H - 0.06), (R + 0.012, H), (R - 0.018, H + 0.006), (R - 0.026, H - 0.05), (0.0, H - 0.05)],
                     metal, segments=segs, smooth=smooth, cap=True)]
    body.append(mg.lathe([(R + 0.001, 0.078), (R + 0.005, 0.088), (R + 0.005, H - 0.088), (R + 0.001, H - 0.078)],
                         label, segments=segs, smooth=smooth, cap=False))
    # the fish on the front (-Y), a little proud of the label
    body.append(mg.extrude([(-0.13, 0.0), (-0.05, 0.065), (0.05, 0.045), (0.12, 0.1), (0.055, 0.0), (0.12, -0.1),
                            (0.05, -0.045), (-0.05, -0.065)], 0.012, fish, loc=(0.0, -(R + 0.008), 0.29), bevel=0.003))
    body.append(mg.part("sphere", label_d, loc=(-0.075, -(R + 0.016), 0.305), scale=(0.022, 0.012, 0.022)))
    can = mg.join("zc_toxic_can", body)

    # ---- the goo, one smooth mass: a dome in the tin, spilling over the rim, running down the side past the fish,
    # pooling on the ground round the foot
    shapes = [{"ellipsoid": (0.0, 0.0, H - 0.015), "size": (R - 0.01, R - 0.01, 0.06)}]
    for bx, by in ((-0.1, 0.05), (0.08, -0.07), (0.03, 0.12)):   # lumps on its surface
        shapes.append({"ball": (bx, by, H + 0.03), "r": 0.035})
    r_out = R + 0.016
    for deg, z_end in ((-55, 0.03), (-128, 0.4), (-20, 0.34), (160, 0.3), (40, 0.46)):
        a = math.radians(deg)
        x, y = math.cos(a), math.sin(a)
        shapes += [{"ellipsoid": (x * R, y * R, H), "size": (0.07, 0.07, 0.035)},                       # over the rim
                   {"capsule": ((x * r_out, y * r_out, H - 0.01), (x * r_out, y * r_out, z_end + 0.03)), "r": 0.026},
                   {"ball": (x * (r_out + 0.004), y * (r_out + 0.004), z_end + 0.02), "r": 0.036}]        # its drop
    a = math.radians(-55)
    shapes.append({"ellipsoid": (math.cos(a) * (R + 0.13), math.sin(a) * (R + 0.13), 0.004), "size": (0.16, 0.12, 0.014)})
    for deg, dist, rx in ((-150, 0.1, 0.1), (100, 0.08, 0.08), (30, 0.12, 0.07)):   # more puddles round the foot
        a = math.radians(deg)
        shapes.append({"ellipsoid": (math.cos(a) * (R + dist), math.sin(a) * (R + dist), 0.003), "size": (rx, rx * 0.8, 0.011)})
    goo_mass = mg.blob(shapes, goo, blend=0.85)
    mg.attach(goo_mass, can)
    # bubbles rising out of the gap under the lid
    for bx, by, bz, br in ((0.05, -0.22, H + 0.1, 0.03), (-0.06, -0.3, H + 0.2, 0.026), (0.02, -0.34, H + 0.29, 0.02)):
        mg.attach(mg.part("sphere", goo, loc=(bx, by, bz), scale=(br * 2,) * 3, segments=bub_seg), can)

    # ---- the lid, dark, pushed up askew: its back edge rests on the rim, the front lifts on the goo; it rattles a
    # little (the pack calls the clip "bubbles")
    Rl = R + 0.005
    lid = mg.join("zc_toxic_lid", [
        mg.lathe([(0.0, 0.0), (Rl - 0.02, 0.0), (Rl, 0.012), (Rl, 0.026), (Rl - 0.02, 0.034), (0.0, 0.03)], metal_d,
                 segments=segs, smooth=smooth, cap=True),
        mg.lathe([(0.12, 0.031), (0.13, 0.036), (0.14, 0.031)], metal, segments=segs, smooth=smooth, cap=False),
        mg.part("cyl", metal, loc=(0, 0, 0.04), scale=(0.07, 0.07, 0.02), vertices=bub_seg)])
    mg.attach(lid, can)
    L = (0.0, 0.05, H + 0.085)
    mg.animate(lid, "bubbles", [(1, (-0.25, 0.0, 0.2)), (30, (-0.29, 0.0, 0.2)), (60, (-0.25, 0.0, 0.2))], path="rotation_euler")
    mg.animate(lid, "bubbles", [(1, L), (30, (L[0], L[1], L[2] + 0.012)), (60, L)], path="location")
