"""build(mg) for the sculpting check: clay (blob with a carved socket), skin, cut, bend, twist and sculpt brushes.
The horn (a 0.6 m cone at x = -0.45) bends a right angle toward +X from its base: its tip ends 0.6·2/π ≈ 0.38 m up."""
import math


def build(mg):
    stone = mg.color("stone", "#8d8a82", rough=0.9)
    wood = mg.color("wood", "#7a5232", rough=0.8)
    horn = mg.color("bone", "#d9cfb4", rough=0.6)
    slab = mg.part("cube", stone, loc=(0, 0, 0.3), scale=(0.5, 0.15, 0.6), bevel=0.02)
    paw = mg.blob([{"ellipsoid": (0, -0.08, 0.35), "size": (0.07, 0.03, 0.06)},
                   *[{"ball": (x, -0.08, 0.44), "r": 0.022} for x in (-0.05, -0.017, 0.017, 0.05)]], stone)
    mg.cut(slab, paw)
    mg.sculpt(slab, "noise", amount=0.006, scale=18)
    post = mg.part("cyl", wood, loc=(0.45, 0, 0.3), scale=(0.06, 0.06, 0.6))
    mg.twist(post, 2.0)
    h = mg.part("cone", horn, loc=(-0.45, 0, 0.3), scale=(0.08, 0.08, 0.6))
    mg.bend(h, math.pi / 2, along="Z", toward="X")
    head = mg.blob([{"ball": (0, -0.02, 0.72), "r": 0.1}, {"ball": (0, -0.1, 0.7), "r": 0.05},
                    {"ball": (0, -0.12, 0.74), "r": 0.025, "cut": True}], horn)
    mg.sculpt(head, "grab", at=(0, -0.14, 0.7), to=(0, -0.02, 0), radius=0.06)
    mg.sculpt(head, "crease", path=[(-0.05, -0.1, 0.76), (0.05, -0.1, 0.76)], radius=0.015, amount=0.008)
    iris = mg.color("eye_glow", "#9dff3a", glow=2.0)
    eye = mg.eye((0.035, -0.105, 0.74), 0.018, iris, look=(0.2, -1, 0), pupil="slit")
    tail = mg.skin([(0.2, 0.05, 0.62), (0.3, 0.05, 0.7), (0.35, 0.05, 0.8)], [0.03, 0.025, 0.015], wood)
    mg.join("tools", [slab, post, h, head, eye, tail])
