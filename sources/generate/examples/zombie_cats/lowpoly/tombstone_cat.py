"""Cat-shaped tombstone: stone slab with two pointed ears, carved paw print, low base, glowing green goo."""
import math


def build(mg):
    stone = mg.color("stone", "#d8cfc0", rough=0.85)
    stone_dark = mg.color("stone_dark", "#5a564f", rough=0.8)  # carved paw pads
    goo = mg.color("goo_slime", "#8cf03a", rough=0.3, glow=2.5)

    parts = []
    w, t, h = 0.7, 0.22, 1.1
    z0 = 0.14  # top of base

    # main slab, slightly tapered narrower toward top
    parts.append(mg.part("cube", stone, loc=(0, 0, z0 + h / 2), scale=(w, t, h),
                         taper=0.9, bevel=0.01))

    # two pointed cat ears on top (triangular wedges) with a V notch between
    ear_w, ear_h = 0.24, 0.34
    top = z0 + h
    ear = mg.extrude([(0.02, 0), (0.02 + ear_w, 0), (0.05 + ear_w * 0.4, ear_h)],
                     t * 0.92, stone, loc=(0, 0, top), rot=(0, 0, 0))
    parts.append(ear)
    parts.append(mg.mirror_x(ear))

    # low stone base
    parts.append(mg.part("cube", stone, loc=(0, 0, z0 / 2), scale=(w + 0.28, t + 0.28, z0),
                         bevel=0.01))

    # carved paw print on the front face (front faces -Y)
    yf = -t / 2 + 0.01
    pz = z0 + h * 0.62
    # big central pad
    parts.append(mg.part("sphere", stone_dark, loc=(0, yf, pz - 0.06),
                         scale=(0.17, 0.06, 0.15)))
    # four toe pads
    toes = [(-0.13, 0.05), (-0.05, 0.11), (0.05, 0.11), (0.13, 0.05)]
    for tx, tzo in toes:
        parts.append(mg.part("sphere", stone_dark, loc=(tx, yf, pz + tzo),
                             scale=(0.07, 0.05, 0.07)))

    tomb = mg.join("zc_tombstone_cat", parts)

    # glowing green goo puddle at front of base
    goo_parts = []
    goo_parts.append(mg.part("cyl", goo, loc=(0, -t / 2 - 0.12, 0.015),
                             scale=(0.34, 0.4, 0.03), vertices=12))
    goo_parts.append(mg.part("cyl", goo, loc=(0, -t / 2 - 0.05, z0 * 0.5),
                             scale=(0.16, 0.1, z0 * 1.1), vertices=10, taper=0.4))
    if mg.at_least("mobile-mid"):
        goo_parts.append(mg.part("cyl", goo, loc=(0.28, -t / 2 - 0.24, 0.012),
                                 scale=(0.11, 0.13, 0.025), vertices=10))
    mg.join("zc_tombstone_goo", goo_parts)
