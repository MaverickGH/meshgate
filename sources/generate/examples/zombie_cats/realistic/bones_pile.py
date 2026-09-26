"""zc_bones_pile - a small pile of three fish skeletons lying flat on the ground."""
import math


def build(mg):
    mg.mirror_x  # symmetry handled per-fish by placement
    bone = mg.color("bone", (0.85, 0.81, 0.70), rough=0.6, metal=0.0)

    def fish(z0):
        p = []
        # tapering spine running head(-X) to tail(+X)
        p.append(mg.tube([(-0.16, 0, z0), (-0.05, 0, z0 + 0.006), (0.08, 0, z0),
                          (0.2, 0, z0 - 0.002)], 0, bone,
                         radii=[0.013, 0.016, 0.011, 0.006], sides=8))
        # skull: open funnel facing forward, plus a small cranium
        p.append(mg.part("cone", bone, loc=(-0.185, 0, z0 + 0.008),
                         scale=(0.08, 0.08, 0.11), rot=(0, -math.pi / 2, 0),
                         radius1=0.5, radius2=0.13))
        p.append(mg.part("sphere", bone, loc=(-0.15, 0, z0 + 0.012),
                         scale=(0.055, 0.06, 0.05)))
        # jaw stub
        p.append(mg.tube([(-0.2, 0, z0 - 0.01), (-0.13, 0, z0 - 0.006)], 0, bone,
                         radii=[0.006, 0.004], sides=6))
        # ribs fanning out to both sides, angled toward the head
        xs = [-0.06, -0.02, 0.02, 0.06, 0.1]
        for x in xs:
            for s in (1, -1):
                p.append(mg.tube([(x, 0, z0), (x - 0.02, s * 0.05, z0 + 0.012),
                                  (x - 0.035, s * 0.075, z0 + 0.02)], 0, bone,
                                 radii=[0.006, 0.004, 0.0025], sides=6))
        # neural spines along the top on richer tiers
        if mg.at_least("mobile-high"):
            for x in xs:
                p.append(mg.tube([(x, 0, z0 + 0.008), (x - 0.01, 0, z0 + 0.05)], 0,
                                 bone, radii=[0.005, 0.002], sides=6))
        # triangular caudal fin
        p.append(mg.extrude([(0.18, 0), (0.3, 0.1), (0.3, -0.1)], 0.014, bone,
                            loc=(0, 0, z0), rot=(math.pi / 2, 0, 0), bevel=0.003))
        return p

    base = mg.join("fish", fish(0.016))
    c1 = mg.copy(base, loc=(0.05, -0.13, 0.03), rot=(0, 0, -0.6))
    c2 = mg.copy(base, loc=(-0.06, 0.14, 0.05), rot=(0, 0, 0.7))
    mg.join("zc_bones_pile", [base, c1, c2])
