"""zc_bones_pile — a fish skeleton on the ground, like the concept art: a big skull with an eye socket and an open jaw,
a spine with ribs up and down, a tail fin, and a couple of loose little bones beside it. It stands on its belly ribs,
side on to the viewer, the way cartoon fishbones are drawn."""
import math


def build(mg):
    bone = mg.color("bone", "#e6e0cf", rough=0.7, material="bone")
    bone_d = mg.color("bone_dark", "#cfc6ae", rough=0.75, material="bone")
    hollow = mg.color("socket_dark", "#3a3230", rough=0.9)
    sides = 8 if mg.at_least("mobile-mid") else 6
    smooth = True

    parts = []
    z = 0.11                                   # the spine's height above the ground
    x0, x1 = -0.15, 0.22                       # from behind the skull to the tail
    n = 7
    spine = [(x0 + (x1 - x0) * i / (n - 1), 0.0, z + 0.012 * math.sin(i / (n - 1) * math.pi)) for i in range(n)]
    parts.append(mg.tube(spine, 0.0, bone, radii=[0.016, 0.015, 0.013, 0.011, 0.009, 0.007, 0.005], sides=sides,
                         smooth=smooth))

    # the skull: a rounded head with a dark eye socket and an open jaw pointing forward (-X)
    parts.append(mg.part("sphere", bone, loc=(-0.2, 0.0, z + 0.01), scale=(0.15, 0.075, 0.13), smooth=smooth))
    parts.append(mg.part("sphere", hollow, loc=(-0.215, -0.028, z + 0.03), scale=(0.045, 0.03, 0.045), smooth=smooth))
    parts.append(mg.part("cone", bone_d, loc=(-0.3, 0.0, z + 0.025), scale=(0.07, 0.05, 0.11),
                         rot=(0, -math.pi / 2 - 0.25, 0), smooth=smooth))                       # upper jaw
    parts.append(mg.part("cone", bone_d, loc=(-0.29, 0.0, z - 0.04), scale=(0.06, 0.045, 0.1),
                         rot=(0, -math.pi / 2 + 0.35, 0), smooth=smooth))                       # lower jaw, open
    if mg.at_least("mobile-mid"):
        for k in range(3):   # a few teeth on the upper jaw
            parts.append(mg.part("cone", bone, loc=(-0.32 + k * 0.025, -0.005, z + 0.0), scale=(0.012, 0.012, 0.025),
                                 rot=(math.pi, 0, 0), smooth=smooth))

    # ribs: long curved bones down to the ground and shorter ones up along the back, sweeping back to the tail
    ribs = 7 if mg.at_least("mobile-mid") else 5
    for i in range(ribs):
        t = i / (ribs - 1)
        x = -0.1 + 0.26 * t
        down = 0.1 * (1.0 - 0.45 * t)
        up = 0.07 * (1.0 - 0.5 * t)
        parts.append(mg.tube([(x, 0.0, z), (x + 0.02, 0.0, z - down * 0.6), (x + 0.045, 0.0, max(z - down, 0.008))], 0.0,
                             bone, radii=[0.007, 0.006, 0.004], sides=6, smooth=smooth))
        parts.append(mg.tube([(x, 0.0, z), (x + 0.02, 0.0, z + up * 0.6), (x + 0.05, 0.0, z + up)], 0.0,
                             bone, radii=[0.006, 0.005, 0.003], sides=6, smooth=smooth))

    # the tail fin: a fan standing up at the end of the spine
    parts.append(mg.extrude([(0.0, 0.0), (0.1, 0.085), (0.07, 0.0), (0.1, -0.085)], 0.016, bone,
                            loc=(x1 - 0.005, 0.0, z + 0.005), bevel=0.004))
    fish = mg.join("zc_bones_pile", parts)
    # a second, smaller skeleton lying across behind it: a pile, as in the concept
    mg.attach(mg.copy(fish, loc=(0.02, 0.06, 0.0), rot=(0, 0, 1.2), scale=(0.75, 0.75, 0.75)), fish)

    # two loose little bones on the ground beside it
    for (bx, by, a, ln) in ((0.22, -0.12, 0.6, 0.12), (-0.22, 0.2, -0.3, 0.09)):
        dx, dy = math.cos(a) * ln / 2, math.sin(a) * ln / 2
        loose = [mg.tube([(bx - dx, by - dy, 0.012), (bx + dx, by + dy, 0.012)], 0.009, bone_d, sides=6, smooth=smooth)]
        for s in (-1, 1):
            loose.append(mg.part("sphere", bone_d, loc=(bx + s * dx, by + s * dy, 0.014), scale=(0.028, 0.028, 0.026),
                                 smooth=smooth))
        mg.join("loose_bone", loose)
