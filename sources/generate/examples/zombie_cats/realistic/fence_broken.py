"""zc_fence_broken — a broken wooden garden fence: dark posts & rails with bolts, cat-ear pickets, snapped and leaning ones."""
import math


def build(mg):
    wood_dark = mg.color("wood_dark", "#4a2c1e", rough=0.85, material="wood")
    wood = mg.color("wood", "#b8824e", rough=0.8, material="wood")
    iron = mg.color("iron", (0.18, 0.18, 0.2), rough=0.45, metal=1.0)
    rust = mg.color("rust", "#7a4a2a", rough=0.75, metal=0.1, material="rust")

    P = 0.93          # post x
    RAIL_Z = (0.85, 0.28)
    parts = []

    # posts (dark wood, slightly chamfered top)
    for x in (-P, P):
        parts.append(mg.part("cube", wood_dark, loc=(x, 0.0, 0.53),
                             scale=(0.1, 0.1, 1.06), bevel=0.01, taper=0.92))

    # two horizontal rails behind the pickets
    for z in RAIL_Z:
        parts.append(mg.part("cube", wood_dark, loc=(0, 0.02, z),
                             scale=(1.86, 0.06, 0.13), bevel=0.008))

    # cat-ear picket top (outline in XZ, base at z=0, ears at z=1.0)
    def ear_top(h):
        s = h - 0.14
        return [(-0.06, 0), (-0.06, s), (-0.03, h), (0.0, s),
                (0.03, h), (0.06, s), (0.06, 0)]

    # full standing pickets
    full_x = [-0.72, -0.5, -0.28, 0.42, 0.66]
    for x in full_x:
        parts.append(mg.extrude(ear_top(1.0), 0.025, wood,
                                loc=(x, -0.05, 0.0), bevel=0.004))

    # snapped-short pickets (jagged broken top)
    snap = [(-0.06, 0), (-0.06, 0.5), (-0.02, 0.58), (0.01, 0.46),
            (0.04, 0.57), (0.06, 0.47), (0.06, 0)]
    for x in (-0.05, 0.18):
        parts.append(mg.extrude(snap, 0.025, wood,
                                loc=(x, -0.05, 0.0), bevel=0.004))

    # leaning broken picket: splintered bottom, cat-ear top, centred then tilted
    diag = [(-0.06, -0.40), (-0.02, -0.45), (0.02, -0.37), (0.06, -0.44),
            (0.06, 0.31), (0.03, 0.45), (0.0, 0.31), (-0.03, 0.45), (-0.06, 0.31)]
    parts.append(mg.extrude(diag, 0.028, wood, loc=(0.16, -0.09, 0.44),
                            rot=(0, 0.62, 0), bevel=0.004))

    # bolt heads along both rails
    bolt_x = [-0.93, -0.6, -0.25, 0.1, 0.45, 0.75, 0.93]
    if not mg.at_least("mobile-mid"):
        bolt_x = [-0.93, -0.45, 0.1, 0.6, 0.93]
    for z in RAIL_Z:
        for x in bolt_x:
            parts.append(mg.part("cyl", iron, loc=(x, -0.075, z),
                                 scale=(0.036, 0.036, 0.02),
                                 rot=(math.pi / 2, 0, 0), vertices=8, bevel=0.004))

    # single rusty nail holding the crooked picket near the top rail
    if mg.at_least("mobile-high"):
        parts.append(mg.part("cyl", rust, loc=(0.33, -0.11, 0.78),
                             scale=(0.02, 0.02, 0.03),
                             rot=(math.pi / 2, 0, 0), vertices=8))

    mg.join("zc_fence_broken", parts)
