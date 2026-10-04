"""Example build code: a cast-iron fire hydrant, about 0.8 m tall (static prop, lathe + cylinders)."""
import math


def build(mg):
    mg.color("red", "#b3261e", rough=0.45, metal=0.3)
    mg.color("red_dark", "#7a1712", rough=0.5, metal=0.3)
    mg.color("steel", (0.62, 0.63, 0.66), rough=0.35, metal=1.0)

    # body: one surface of revolution from the base flange to the dome
    body = mg.lathe([(0.17, 0.0), (0.17, 0.05), (0.12, 0.07), (0.115, 0.55), (0.13, 0.57), (0.13, 0.61),
                     (0.10, 0.63), (0.07, 0.70), (0.0, 0.72)], "red", segments=24)
    parts = [body]
    # side outlets, left and right, and the pumper outlet at the front (-Y)
    arm = mg.part("cyl", "red_dark", loc=(0.15, 0, 0.42), scale=(0.11, 0.11, 0.1), rot=(0, math.pi / 2, 0))
    cap = mg.part("cyl", "steel", loc=(0.21, 0, 0.42), scale=(0.09, 0.09, 0.03), rot=(0, math.pi / 2, 0), bevel=0.004)
    parts += [arm, cap, mg.mirror_x(arm), mg.mirror_x(cap)]
    parts.append(mg.part("cyl", "red_dark", loc=(0, -0.15, 0.36), scale=(0.14, 0.14, 0.1), rot=(math.pi / 2, 0, 0)))
    parts.append(mg.part("cyl", "steel", loc=(0, -0.21, 0.36), scale=(0.12, 0.12, 0.03), rot=(math.pi / 2, 0, 0), bevel=0.004))
    # operating nut on top: a pentagon, as on real hydrants
    parts.append(mg.part("cyl", "steel", loc=(0, 0, 0.74), scale=(0.035, 0.035, 0.05), vertices=5, smooth=False))
    # flange bolts only where the tier affords them
    if mg.at_least("mobile-high"):
        for i in range(8):
            a = 2 * math.pi * i / 8
            parts.append(mg.part("cyl", "steel", loc=(0.145 * math.cos(a), 0.145 * math.sin(a), 0.055),
                                 scale=(0.014, 0.014, 0.02), vertices=6, smooth=False))
    mg.join("fire_hydrant", parts)
