"""zc_bones_pile — a small pile of three fish skeletons lying flat (skull, spine, ribs, tail fin)."""
import math


def build(mg):
    bone = mg.color("bone", "#dcd7c4", rough=0.72)
    bone_d = mg.color("bone_dark", "#c7bfa6", rough=0.75)

    def make_fish(length, z0):
        parts = []
        half = length / 2.0
        n = 7
        spine = [(-half + length * (i / (n - 1)), 0.0, z0) for i in range(n)]
        radii = [0.021, 0.021, 0.018, 0.015, 0.012, 0.009, 0.006]
        parts.append(mg.tube(spine, 0.0, bone, radii=radii, sides=8))

        # skull: open scoop cone, wide mouth facing outward
        parts.append(mg.part("cone", bone_d, loc=(-half - 0.02, 0.0, z0),
                             scale=(0.095, 0.095, 0.15), rot=(0, math.pi / 2, 0), smooth=True))
        # little jaw bone under the skull
        parts.append(mg.part("cyl", bone_d, loc=(-half - 0.01, 0.0, z0 - 0.02),
                             scale=(0.02, 0.02, 0.09), rot=(0, math.pi / 2, 0), vertices=6))
        # a couple of eye-socket rings on the skull
        if mg.at_least("mobile-mid"):
            parts.append(mg.part("torus", bone_d, loc=(-half + 0.02, 0.0, z0 + 0.02),
                                 scale=(0.055, 0.055, 0.04), rot=(0, math.pi / 2, 0),
                                 major_radius=0.5, minor_radius=0.12))

        # ribs: thin curved bones angled back and down on both sides
        ts = [0.24, 0.36, 0.48, 0.60, 0.72]
        if mg.at_least("mobile-mid"):
            ts = [0.22, 0.31, 0.40, 0.49, 0.58, 0.67, 0.76]
        for t in ts:
            xr = -half + length * t
            reach = 0.075 * (1.0 - 0.4 * t)
            for s in (1, -1):
                base = (xr, 0.0, z0)
                tip = (xr - 0.025, s * reach, z0 - 0.012)
                parts.append(mg.tube([base, tip], 0.0055, bone, sides=6))

        # tail fin: fanned fishtail, laid flat on the ground
        fin = [(0.0, 0.0), (0.11, 0.065), (0.075, 0.0), (0.11, -0.065)]
        parts.append(mg.extrude(fin, 0.012, bone, loc=(half - 0.02, 0.0, z0),
                                rot=(math.pi / 2, 0, 0), bevel=0.004))
        return parts

    fish1 = mg.join("fish1", make_fish(0.5, 0.022))
    fish2 = mg.copy(fish1, loc=(0.03, 0.075, 0.0), rot=(0, 0, -0.55), scale=(0.95, 0.95, 0.95))
    fish3 = mg.copy(fish1, loc=(-0.04, -0.05, 0.042), rot=(0, 0, 1.35), scale=(0.86, 0.86, 0.86))
    mg.join("zc_bones_pile", [fish1, fish2, fish3])
