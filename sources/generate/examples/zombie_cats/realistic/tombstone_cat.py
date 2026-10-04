"""zc_tombstone_cat, realistic — the same cat tombstone in weathered grey stone: slab with short ears and a
scooped top, a carved paw print, a two-step base, moss clumps along the base, glowing goo pooling in front."""
import math


def build(mg):
    stone = mg.color("stone_light", "#8e887f", rough=0.88, material="stone")
    base = mg.color("stone_base", "#817b72", rough=0.9, material="stone")
    pad = mg.color("stone_dark", "#3a3836", rough=0.75, material="stone")
    goo = mg.color("goo_ooze", "#7ede2c", rough=0.35, glow=2.2, material="plain")
    moss = mg.color("moss_green", "#3c5222", rough=0.95, material="ground")
    scoop, bevel, pad_sides, goo_seg = 12, 0.014, 24, 20

    parts = []
    depth = 0.13        # slab thickness
    top = 0.95          # the shoulders of the slab (the ears rise above)
    # ---- the slab, seen from the front: a cat's head — two short ears at the corners, a gentle scoop between them
    outline = [(-0.34, 0.12), (-0.34, top), (-0.3, top + 0.15), (-0.19, top + 0.01)]
    for i in range(1, scoop):
        t = i / scoop
        outline.append((-0.19 + 0.38 * t, top + 0.01 - 0.035 * math.sin(math.pi * t)))
    outline += [(0.19, top + 0.01), (0.3, top + 0.15), (0.34, top), (0.34, 0.12)]
    parts.append(mg.extrude(outline, depth, stone, bevel=bevel, smooth=False))
    # ---- a two-step base
    parts.append(mg.part("cube", base, loc=(0, 0, 0.05), scale=(0.84, 0.34, 0.1), bevel=bevel))
    parts.append(mg.part("cube", base, loc=(0, 0, 0.125), scale=(0.74, 0.26, 0.05), bevel=bevel))

    # ---- the paw print, carved dark and set just proud of the front face: one pad, four toes apart from it
    fy = -depth / 2 - 0.004
    parts.append(mg.part("cyl", pad, loc=(0, fy, 0.5), scale=(0.2, 0.2, 0.012), rot=(math.pi / 2, 0, 0),
                         vertices=pad_sides, bevel=0.004))
    for tx, tz in ((-0.115, 0.61), (-0.042, 0.655), (0.042, 0.655), (0.115, 0.61)):
        parts.append(mg.part("cyl", pad, loc=(tx, fy, tz), scale=(0.07, 0.07, 0.012), rot=(math.pi / 2, 0, 0),
                             vertices=pad_sides, bevel=0.003))
    tomb = mg.join("zc_tombstone_cat", parts)

    # ---- glowing goo, one smooth mass: welling out under the slab, running over the base's front edge, pooling
    shapes = [{"ellipsoid": (0.03, -0.12, 0.155), "size": (0.06, 0.045, 0.025)},
              {"capsule": ((0.03, -0.15, 0.15), (0.035, -0.18, 0.02)), "r": 0.03},
              {"ellipsoid": (0.04, -0.29, 0.004), "size": (0.17, 0.12, 0.016)},
              {"capsule": ((0.035, -0.18, 0.012), (0.04, -0.26, 0.006)), "r": 0.022}]
    if mg.at_least("mobile-mid"):
        shapes += [{"ellipsoid": (0.3, -0.36, 0.003), "size": (0.05, 0.04, 0.01)},
                   {"ellipsoid": (-0.3, -0.3, 0.003), "size": (0.04, 0.035, 0.009)}]
    mg.blob(shapes, goo, blend=0.8)

    mg.sculpt(tomb, "noise", amount=0.003, scale=18)   # a worn, uneven stone face
    # moss clumps in the corner between the slab and the base, and on the base's top
    clump = mg.part("ico", moss, loc=(0, 0, 0), scale=(0.11, 0.09, 0.04), subdiv=1)
    corners = ((-0.36, -0.12), (0.36, 0.1), (-0.3, 0.14))
    for k, (cx, cy) in enumerate(corners):   # clumps gathered in a few corners, not sprinkled
        mg.scatter(tomb, clump if k == len(corners) - 1 else mg.copy(clump), 6, seed=int(cx * 100), scale=(0.6, 1.2), facing=(0, 0, 1), below=0.16,
                   at=(cx, cy, 0.15), radius=0.12, sink=0.01)
