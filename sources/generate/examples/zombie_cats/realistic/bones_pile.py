"""Small pile of three fish skeletons lying flat on the ground, about 0.66 m across: each with a skull, a spine, thin
ribs and a tail fin. Built from the kit's splines: a curving spine of vertebrae, arched tapering ribs, fanned fin rays,
a clay skull with a carved eye socket and an open jaw."""
import math


def build(mg):
    bone = mg.color("fish_bone", "#ddd5bd", rough=0.6, material="bone")
    old = mg.color("old_bone", "#b9ab8a", rough=0.7, material="bone")
    dark = mg.color("socket_shadow", "#4a4032", rough=0.8)

    def fish(length, ox, oy, lift, ang):
        """One skeleton lying on its side (head toward local -X, back toward +Y), turned by ang about Z, moved to
        (ox, oy) and lifted `lift` metres (to lie across the others)."""
        ca, sa = math.cos(ang), math.sin(ang)

        def P(x, y, zz):
            return (ox + x * ca - y * sa, oy + x * sa + y * ca, zz + lift)

        def C(points, radii, sides=6):
            return mg.curve([P(*q) for q in points], 0, bone, radii=radii, sides=sides)

        parts = []
        z = 0.018 * length / 0.5          # the thickest bones rest on the ground
        head = -length / 2
        # spine: a gentle S, from behind the skull to the tail
        n = 9
        spine = [(head + 0.2 * length + (0.72 * length) * i / (n - 1),
                  0.012 * math.sin(i / (n - 1) * math.pi * 1.3), z) for i in range(n)]
        parts.append(C(spine, [0.011, 0.011, 0.01, 0.009, 0.008, 0.007, 0.006, 0.005, 0.004], sides=8))
        # vertebrae: short discs threaded on the spine
        count = {True: 16, False: 9}[mg.at_least("mobile-high")]
        for i in range(count):
            t = (i + 0.5) / count
            k = min(int(t * (n - 1)), n - 2)
            u = t * (n - 1) - k
            a, b = spine[k], spine[k + 1]
            p = [a[j] + (b[j] - a[j]) * u for j in range(3)]
            a_ = math.atan2(b[1] - a[1], b[0] - a[0])
            r = 0.016 - 0.009 * t
            parts.append(mg.part("cyl", bone, loc=P(*p), scale=(r, r, 0.35 * length / count),
                                 rot=(0, math.pi / 2, a_ + ang), vertices=10))
        # ribs from just behind the skull to two thirds down the body: long arcs under the belly (-Y), shorter spines
        # along the back (+Y), all sweeping back toward the tail — the classic fishbone comb
        def at(t):
            k = min(int(t * (n - 1)), n - 2)
            u = t * (n - 1) - k
            return [spine[k][j] + (spine[k + 1][j] - spine[k][j]) * u for j in range(3)]

        ribs = 12 if mg.at_least("mobile-mid") else 7
        for i in range(ribs):
            t = 0.04 + 0.62 * i / (ribs - 1)
            bx, by, _ = at(t)
            belly = 0.2 * length * math.sin(math.pi * (0.25 + 0.75 * (1 - t / 0.7)) * 0.9 + 0.3)
            parts.append(C([(bx, by, z), (bx - 0.005 * length, by - belly * 0.5, z + 0.003),
                            (bx + 0.035 * length, by - belly * 0.9, z),
                            (bx + 0.08 * length, by - belly, z - 0.004)], [0.0045, 0.004, 0.0028, 0.001]))
            back = 0.15 * length * (0.75 + 0.25 * math.sin(math.pi * t / 0.7))
            parts.append(C([(bx, by, z), (bx + 0.02 * length, by + back * 0.55, z + 0.002),
                            (bx + 0.07 * length, by + back, z - 0.003)], [0.004, 0.003, 0.001]))
        # skull: cranium, snout and cheek plates as one piece of clay, an eye socket carved from the top
        sx = head + 0.11 * length
        rot = (0, 0, ang)
        skull = mg.blob([
            {"ellipsoid": P(sx, 0.0, z + 0.004), "size": (0.085 * length, 0.075 * length, 0.028 * length), "rot": rot},
            {"ellipsoid": P(sx - 0.08 * length, -0.005, z), "size": (0.06 * length, 0.035 * length, 0.022 * length), "rot": rot},
            {"ellipsoid": P(sx + 0.05 * length, -0.02, z), "size": (0.05 * length, 0.075 * length, 0.022 * length), "rot": rot},
            {"ball": P(sx - 0.01 * length, 0.012, z + 0.026 * length), "r": 0.028 * length, "cut": True},   # eye socket
        ], bone, blend=0.7)
        mg.paint(skull, old, at=P(sx + 0.04 * length, 0, z), radius=0.07 * length, rough=0.5, seed=round(length * 100))
        mg.paint(skull, dark, at=P(sx - 0.01 * length, 0.012, z + 0.01 * length), radius=0.02 * length)
        mg.sculpt(skull, "crease", path=[P(sx + 0.02 * length, 0.05 * length, z + 0.02 * length),
                                         P(sx + 0.03 * length, -0.05 * length, z + 0.02 * length)],
                  radius=0.004, amount=0.002)
        crest = [P(sx - 0.07 * length, 0.01, z + 0.032 * length), P(sx + 0.07 * length, 0.012, z + 0.03 * length)]
        mg.sculpt(skull, "ridge", path=crest, radius=0.005, amount=0.0025)
        mg.sculpt(skull, "pinch", path=crest, radius=0.005, strength=0.6)
        cheek = P(sx + 0.04 * length, -0.03 * length, z + 0.02 * length)
        mg.sculpt(skull, "layer", at=cheek, radius=0.03 * length, amount=0.0015)
        mg.sculpt(skull, "flatten", at=cheek, radius=0.028 * length, strength=0.5)
        gill = [P(sx + 0.07 * length, 0.05 * length, z + 0.015 * length), P(sx + 0.085 * length, 0.0, z + 0.022 * length),
                P(sx + 0.07 * length, -0.06 * length, z + 0.015 * length)]
        mg.sculpt(skull, "ridge", path=gill, radius=0.004, amount=0.0018)
        mg.sculpt(skull, "pinch", path=gill, radius=0.004, strength=0.6)
        parts.append(skull)
        # the lower jaw hangs open
        parts.append(C([(sx - 0.02 * length, -0.03 * length, z - 0.004), (sx - 0.1 * length, -0.06 * length, z - 0.008),
                        (sx - 0.16 * length, -0.045 * length, z - 0.01)], [0.006, 0.005, 0.003]))
        if mg.at_least("mobile-high"):   # a few needle teeth along the jaw
            for i in range(5):
                tx = sx - (0.06 + 0.02 * i) * length
                parts.append(mg.part("cone", bone, loc=P(tx, -0.05 * length - 0.001 * i, z - 0.004),
                                     scale=(0.004, 0.004, 0.012), rot=(math.pi / 2, 0, ang)))
        # tail fin: a fan of rays from the last vertebra
        tx, ty, _ = spine[-1]
        rays = 9 if mg.at_least("mobile-mid") else 5
        for i in range(rays):
            a = (i / (rays - 1) - 0.5) * 1.4
            ln = 0.2 * length * (0.6 + 0.4 * abs(a) / 0.7)   # forked: the outer rays longest
            parts.append(C([(tx, ty, z), (tx + ln * 0.5 * math.cos(a * 0.8), ty + ln * 0.5 * math.sin(a * 0.8), z),
                            (tx + ln * math.cos(a), ty + ln * math.sin(a), z - 0.002)], [0.003, 0.0022, 0.0008], sides=5))
        # dorsal fin rays along the back
        if mg.at_least("mobile-mid"):
            for i in range(6):
                bx = head + (0.4 + 0.05 * i) * length
                parts.append(C([(bx, 0.07 * length, z), (bx + 0.03 * length, 0.13 * length, z - 0.002)], [0.0022, 0.0008],
                               sides=5))
        return parts

    mg.join("zc_bones_pile", fish(0.52, 0.0, 0.0, 0.0, 0.0)
            + fish(0.47, 0.06, 0.2, 0.0, 2.75)
            + fish(0.42, -0.04, 0.02, 0.024, -0.8))   # the smallest lies across the other two
