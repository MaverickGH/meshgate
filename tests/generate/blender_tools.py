"""build(mg) for the Blender-tools check: spline curves (a helix spring, a sagging cable, a closed ring), scatter
(pebbles on a boulder), and modifiers (array planks, displace, solidify, wireframe, shrinkwrap, bevel, smooth)."""
import math


def build(mg):
    stone = mg.color("stone", "#8a877f", rough=0.9)
    pebble_c = mg.color("pebble_stone", "#6f6a60", rough=0.9)
    steel = mg.color("steel", "#9aa0a6", rough=0.35, metal=1.0)
    wood = mg.color("wood", "#7a5232", rough=0.8)
    rubber = mg.color("cable_rubber", "#1d1d1f", rough=0.6)
    leather = mg.color("strap_leather", "#5a3a22", rough=0.6)

    rock = mg.blob([{"ellipsoid": (0, 0, 0.18), "size": (0.3, 0.25, 0.18)}, {"ball": (0.15, 0.05, 0.25), "r": 0.12}],
                   stone, blend=0.6)
    mg.modify(rock, "displace", strength=0.03, scale=0.15)
    pebble = mg.part("ico", pebble_c, loc=(0, 0, 0.02), scale=(0.06, 0.05, 0.04))
    pebbles = mg.scatter(rock, pebble, 24, seed=3, facing=(0, 0, 1), sink=0.004)

    spring = mg.curve([(0.6 + 0.07 * math.cos(t / 8 * math.pi), 0.07 * math.sin(t / 8 * math.pi), 0.02 + t * 0.012)
                       for t in range(0, 49)], 0.008, steel)
    cable = mg.curve([(-0.6, -0.3, 0.3), (-0.3, -0.35, 0.08), (0.0, -0.35, 0.05), (0.3, -0.3, 0.3)], 0.01, rubber)
    ring = mg.curve([(0.6 + 0.1 * math.cos(a), 0.3 + 0.1 * math.sin(a), 0.05) for a in
                     [i * math.pi / 3 for i in range(6)]], 0.012, steel, closed=True)

    plank = mg.part("cube", wood, loc=(-0.7, 0.35, 0.02), scale=(0.08, 0.3, 0.02))
    mg.modify(plank, "array", count=5, offset=(0.1, 0, 0))
    mg.modify(plank, "bevel", width=0.004)

    fin = mg.part("plane", steel, loc=(-0.4, -0.1, 0.4), scale=(0.2, 0.12, 1), rot=(math.pi / 2, 0, 0))
    mg.modify(fin, "solidify", thickness=0.01)
    cage = mg.part("cube", steel, loc=(0.6, -0.35, 0.12), scale=(0.2, 0.2, 0.24))
    mg.modify(cage, "wireframe", thickness=0.012)
    strap = mg.part("torus", leather, loc=(0.02, 0.0, 0.17), scale=(0.36, 0.3, 0.3), major_radius=1.0, minor_radius=0.06)
    mg.modify(strap, "shrinkwrap", target=rock, offset=0.004)
    mg.modify(strap, "smooth", factor=0.5, repeat=3)
    mg.join("tools2", [rock, pebbles, spring, cable, ring, plank, fin, cage, strap])
