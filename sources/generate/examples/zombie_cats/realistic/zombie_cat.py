"""Zombie cat character: upright bipedal cat, grey-green fur, stitched head scar, torn ear, glowing green eyes, arms forward."""
import math


def build(mg):
    fur = mg.color("fur", (0.42, 0.48, 0.37), rough=0.85)
    light = mg.color("fur_light", (0.66, 0.70, 0.60), rough=0.85)
    pink = mg.color("inner_ear", (0.78, 0.52, 0.55), rough=0.8)
    nose = mg.color("nose", (0.72, 0.45, 0.50), rough=0.7)
    eye = mg.color("eye", (0.35, 0.95, 0.25), rough=0.3, glow=2.5)
    stitch = mg.color("stitch", (0.07, 0.07, 0.07), rough=0.6)
    whisk = mg.color("whisker", (0.85, 0.85, 0.82), rough=0.5)

    p = []

    # torso (surface of revolution)
    torso = [(0.0, 0.42), (0.11, 0.43), (0.15, 0.52), (0.14, 0.62),
             (0.11, 0.70), (0.08, 0.75), (0.0, 0.78)]
    p.append(mg.lathe(torso, fur, loc=(0, 0, 0), segments=mg.seg(20)))
    # belly patch
    p.append(mg.part("sphere", light, loc=(0, -0.11, 0.55), scale=(0.16, 0.10, 0.24)))
    # neck
    p.append(mg.part("cyl", fur, loc=(0, 0, 0.76), scale=(0.13, 0.13, 0.12), taper=0.85))

    # head
    p.append(mg.part("sphere", fur, loc=(0, 0, 0.90), scale=(0.32, 0.30, 0.32)))
    # muzzle
    p.append(mg.part("sphere", light, loc=(0, -0.14, 0.855), scale=(0.13, 0.10, 0.09)))
    # nose
    p.append(mg.part("sphere", nose, loc=(0, -0.185, 0.865), scale=(0.04, 0.035, 0.03)))
    # glowing eyes (slightly different sizes)
    p.append(mg.part("sphere", eye, loc=(-0.065, -0.145, 0.915), scale=(0.055, 0.05, 0.06)))
    p.append(mg.part("sphere", eye, loc=(0.075, -0.145, 0.905), scale=(0.045, 0.04, 0.048)))

    # ears (left intact, right torn)
    ear_l = [(-0.03, 0.0), (0.03, 0.0), (0.0, 0.13)]
    p.append(mg.extrude(ear_l, 0.05, fur, loc=(-0.11, 0.02, 1.03), rot=(0.1, 0, 0.25)))
    p.append(mg.extrude([(-0.017, 0.0), (0.017, 0.0), (0.0, 0.08)], 0.03, pink,
                        loc=(-0.11, -0.02, 1.04), rot=(0.1, 0, 0.25)))
    ear_r = [(-0.03, 0.0), (0.03, 0.0), (0.02, 0.07), (0.0, 0.045), (-0.01, 0.09)]  # torn
    p.append(mg.extrude(ear_r, 0.05, fur, loc=(0.11, 0.02, 1.02), rot=(0.1, 0, -0.25)))
    p.append(mg.extrude([(-0.017, 0.0), (0.015, 0.0), (0.0, 0.05)], 0.03, pink,
                        loc=(0.11, -0.02, 1.02), rot=(0.1, 0, -0.25)))

    # stitched scar across forehead
    p.append(mg.part("cube", stitch, loc=(0, -0.12, 0.985), scale=(0.13, 0.012, 0.012)))
    if mg.at_least("mobile-mid"):
        for i in range(5):
            x = -0.05 + i * 0.025
            p.append(mg.part("cube", stitch, loc=(x, -0.135, 0.985),
                             scale=(0.008, 0.02, 0.03), rot=(0, mg.rng.uniform(-0.2, 0.2), 0)))

    # legs + paws
    for sx in (-1, 1):
        p.append(mg.tube([(sx * 0.07, 0.01, 0.44), (sx * 0.08, 0.03, 0.26),
                          (sx * 0.08, 0.0, 0.07)], 0, fur,
                         radii=[0.058, 0.052, 0.045], sides=mg.seg(10)))
        p.append(mg.part("sphere", light, loc=(sx * 0.08, -0.05, 0.035),
                         scale=(0.09, 0.16, 0.07)))
    # arms stretched forward + hands
    for sx in (-1, 1):
        p.append(mg.tube([(sx * 0.13, 0.0, 0.72), (sx * 0.16, -0.14, 0.66),
                          (sx * 0.16, -0.27, 0.60)], 0, fur,
                         radii=[0.05, 0.045, 0.04], sides=mg.seg(10)))
        p.append(mg.part("sphere", light, loc=(sx * 0.16, -0.31, 0.585),
                         scale=(0.07, 0.09, 0.07)))
    # shoulder cuff on one arm
    p.append(mg.part("sphere", light, loc=(-0.135, -0.02, 0.71), scale=(0.08, 0.08, 0.08)))

    # tail curving up, light tip
    p.append(mg.tube([(0.0, 0.13, 0.48), (0.06, 0.18, 0.60), (0.09, 0.14, 0.72),
                      (0.06, 0.04, 0.80)], 0, fur,
                     radii=[0.05, 0.045, 0.035, 0.022], sides=mg.seg(8)))
    p.append(mg.part("sphere", light, loc=(0.05, 0.02, 0.82), scale=(0.05, 0.05, 0.05)))

    # whiskers
    if mg.at_least("mobile-high"):
        for sx in (-1, 1):
            for dz in (0.02, 0.0, -0.02):
                p.append(mg.tube([(sx * 0.05, -0.17, 0.865 + dz),
                                  (sx * 0.22, -0.19, 0.87 + dz * 2)], 0.004, whisk,
                                 sides=4, exact=True))

    mg.join("zc_zombie_cat", p)
