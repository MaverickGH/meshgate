"""Small pile of three low-poly fish skeletons lying flat on the ground."""
import math


def build(mg):
    bone = mg.color("bone", "#e9e2d0", rough=0.7)
    bone_d = mg.color("bone_dark", "#b8ad93", rough=0.75)

    L = 0.40          # spine length
    zc = 0.022        # spine height off the ground (also ~ its radius)

    def make_fish():
        p = []
        # spine: a gently arched round bar
        spine = [(-L / 2, 0, zc),
                 (-L / 6, 0, zc * 1.06),
                 (L / 6, 0, zc * 1.06),
                 (L / 2, 0, zc)]
        p.append(mg.tube(spine, 0.014, bone, sides=6, exact=True))

        # skull: chunky cone pointing forward (+X), wide mouth facing the spine
        p.append(mg.part("cone", bone, loc=(L / 2 + 0.03, 0, zc + 0.006),
                         scale=(0.085, 0.07, 0.12), rot=(0, math.pi / 2, 0),
                         vertices=8, exact=True))
        # eye socket
        p.append(mg.part("sphere", bone_d, loc=(L / 2 + 0.02, 0.028, zc + 0.03),
                         scale=(0.02, 0.02, 0.02), segments=6, ring_count=4, exact=True))

        # tail fin: flat triangular fan at the tail (-X)
        tail = [(0, 0), (-0.10, 0.075), (-0.10, -0.075)]
        p.append(mg.extrude(tail, 0.018, bone, loc=(-L / 2, 0, zc),
                            rot=(-math.pi / 2, 0, 0)))

        # ribs: thin bones fanning back from the spine in the flat plane
        n = 6 if mg.at_least("mobile-mid") else 4
        xs = [(-0.14) + i * (0.30 / (n - 1)) for i in range(n)]
        for xi in xs:
            reach = 0.09 * (0.5 + 0.5 * (1 - abs(xi) / 0.2))
            for side in (1, -1):
                a = (xi, 0, zc)
                b = (xi - 0.035, side * reach, zc - 0.002)
                p.append(mg.tube([a, b], 0, bone, radii=[0.009, 0.003],
                                 sides=4, exact=True))

            # small dorsal neural spines on richer tiers
            if mg.at_least("mobile-high"):
                p.append(mg.part("cyl", bone, loc=(xi, 0, zc + 0.03),
                                 scale=(0.006, 0.006, 0.05),
                                 vertices=6, exact=True))
        return mg.join("fish", p)

    fish = make_fish()
    f2 = mg.copy(fish, loc=(-0.04, 0.07, 0.020), rot=(0, 0, 2.55))
    f3 = mg.copy(fish, loc=(0.05, -0.05, 0.040), rot=(0, 0, -0.85))

    mg.join("zc_bones_pile", [fish, f2, f3])
