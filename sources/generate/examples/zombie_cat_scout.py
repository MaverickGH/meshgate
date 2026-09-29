"""Zombie cat scout, a chibi character about 1 m tall standing in an A-pose, after a character sheet: a big head of grey
fur with a cream stripe down the middle and a cream muzzle, big ears with torn pink insides, one glowing lime eye with a
slit pupil and one dead milky eye, stitches on the forehead, little fangs, long whiskers; a red bandana, a torn olive
shirt open over the cream chest, brown suspenders with brass buckles and a belt, torn brown shorts with a patch, cream
arms and legs with brown stripes, a bandage at the wrist, claws on the hands and feet, a striped tail curling up
behind, a brown backpack with a skull badge. Colours from the sheet's palette. Stylized: soft blocks, clean colours, no
animation."""
import math

import mathutils


def build(mg):
    grey = mg.color("fur_grey", "#786968", rough=0.85, material="fur")
    cream = mg.color("fur_cream", "#dac2aa", rough=0.85, material="fur")
    stripe = mg.color("fur_stripe", "#91756a", rough=0.85, material="fur")
    pink = mg.color("ear_pink", "#c95c62", rough=0.6)
    shirt = mg.color("shirt_olive", "#787e5b", rough=0.9, material="fabric")
    shorts_c = mg.color("shorts_brown", "#624f45", rough=0.9, material="fabric")
    leather = mg.color("leather_brown", "#745044", rough=0.7, material="fabric")
    dark = mg.color("stitch_dark", "#524143", rough=0.8, material="fabric")
    bandana = mg.color("bandana_red", "#823a3b", rough=0.85, material="fabric")
    brass = mg.color("buckle_brass", "#c9a45a", rough=0.35, metal=1.0)
    lime = mg.color("eye_lime", "#d9f55f", rough=0.25, glow=2.0)
    dead = mg.color("eye_dead", "#c1bea7", rough=0.3)
    nose_c = mg.color("nose_pink", "#d4808a", rough=0.4)
    bone = mg.color("fang_white", "#f2eee2", rough=0.4)
    wound = mg.color("wound_red", "#823a3b", rough=0.6)
    ball = {}
    parts = []

    def along(a, b):
        """Centre, length and rotation of a block laid from point a to point b (its own Z along a → b)."""
        a, b = mathutils.Vector(a), mathutils.Vector(b)
        d = b - a
        length = d.length
        pitch = math.atan2(math.hypot(d.x, d.y), d.z)
        yaw = math.atan2(d.y, d.x)
        return tuple((a + b) / 2), length, (0.0, pitch, yaw)

    # ---- legs and feet: short cream legs with brown stripes, big clawed feet
    for sx in (-1, 1):
        leg = mg.part("cube", cream, loc=(sx * 0.09, 0.0, 0.1), scale=(0.1, 0.1, 0.16), bevel=0.03, subdiv=1, smooth=True)
        for z0, z1 in ((0.07, 0.095), (0.125, 0.15)):
            mg.paint(leg, stripe, above=z0, below=z1)
        foot = mg.part("cube", cream, loc=(sx * 0.1, -0.035, 0.034), scale=(0.15, 0.19, 0.07), bevel=0.025, subdiv=1,
                       smooth=True)
        parts += [leg, foot]
        for k in (-1, 0, 1):   # three claws poking out of the front of each foot
            parts.append(mg.part("cone", cream, loc=(sx * 0.1 + k * 0.042, -0.135, 0.022), scale=(0.032, 0.032, 0.055),
                                 rot=(math.pi / 2 + 0.25, 0, 0)))

    # ---- torn brown shorts with a patch
    shorts = mg.part("cube", shorts_c, loc=(0, 0.0, 0.205), scale=(0.31, 0.2, 0.13), bevel=0.035, subdiv=1, smooth=True)
    parts.append(shorts)
    for i in range(9):   # the torn hem: little flaps hanging off the bottom edge, front and back
        x = -0.13 + i * 0.0325
        for y in (-0.1, 0.1):
            parts.append(mg.part("cone", shorts_c, loc=(x, y * 0.98, 0.135 - 0.008 * (i % 2)), scale=(0.032, 0.012, 0.04),
                                 rot=(math.pi, 0, 0), vertices=3))
    parts.append(mg.patch(shorts, leather, at=(0.08, -0.1, 0.19), size=(0.05, 0.045), thickness=0.004))   # a sewn patch

    # ---- the torso in a torn olive shirt, open over the cream chest
    torso = mg.part("cube", shirt, loc=(0, 0.0, 0.365), scale=(0.33, 0.19, 0.24), bevel=0.05, subdiv=1, smooth=True,
                    taper=0.84)   # wider at the hem
    parts.append(torso)
    parts.append(mg.patch(torso, cream, at=(0, -0.095, 0.37), size=(0.085, 0.2), thickness=0.004))       # the open front
    parts.append(mg.patch(torso, wound, at=(-0.012, -0.1, 0.33), size=(0.025, 0.018), thickness=0.006))  # a wound
    for i in range(9):   # torn shirt hem over the shorts
        x = -0.15 + i * 0.0375
        for y in (-0.097, 0.097):
            parts.append(mg.part("cone", shirt, loc=(x, y, 0.245 - 0.01 * (i % 2)), scale=(0.034, 0.012, 0.045),
                                 rot=(math.pi, 0, 0), vertices=3))
    # suspenders with brass buckles and a belt
    for sx in (-1, 1):
        parts.append(mg.part("cube", leather, loc=(sx * 0.07, -0.1, 0.37), scale=(0.028, 0.012, 0.24)))
        parts.append(mg.part("cube", leather, loc=(sx * 0.07, 0.1, 0.37), scale=(0.028, 0.012, 0.24)))
        parts.append(mg.part("cube", brass, loc=(sx * 0.07, -0.108, 0.41), scale=(0.036, 0.008, 0.03), bevel=0.003))
    parts.append(mg.part("cube", leather, loc=(0, 0.0, 0.262), scale=(0.29, 0.205, 0.03), bevel=0.005))       # belt
    parts.append(mg.part("cube", brass, loc=(0, -0.106, 0.262), scale=(0.045, 0.01, 0.034), bevel=0.003))   # buckle

    # ---- arms in an A-pose: olive sleeves, cream forearms with a bandage and a wound, clawed hands
    for sx in (-1, 1):
        sh = (sx * 0.14, 0.0, 0.46)
        drop = math.radians(55)
        d = (sx * math.cos(drop), 0.0, -math.sin(drop))
        el = tuple(s + k * 0.12 for s, k in zip(sh, d))
        wr = tuple(s + k * 0.22 for s, k in zip(sh, d))
        tip = tuple(s + k * 0.28 for s, k in zip(sh, d))
        c, n, r = along(sh, el)
        parts.append(mg.part("cube", shirt, loc=c, scale=(0.08, 0.085, n + 0.04), rot=r, bevel=0.02, subdiv=1, smooth=True))
        c, n, r = along(el, wr)
        fore = mg.part("cube", cream, loc=c, scale=(0.075, 0.075, n + 0.02), rot=r, bevel=0.015, subdiv=1, smooth=True)
        parts.append(fore)
        c, n, r = along(tuple(a + (b - a) * 0.75 for a, b in zip(el, wr)), wr)
        parts.append(mg.part("cube", bone, loc=c, scale=(0.083, 0.083, n), rot=r, bevel=0.01))         # the bandage
        c, n, r = along(wr, tip)
        parts.append(mg.part("cube", cream, loc=c, scale=(0.088, 0.078, n + 0.015), rot=r, bevel=0.02, subdiv=1, smooth=True))
        for k in (-1, 0, 1):   # claws
            base = tuple(t + dd * 0.005 for t, dd in zip(tip, d))
            off = (0.0, k * 0.022, 0.0)
            c, n, r = along(tuple(b + o for b, o in zip(base, off)), tuple(b + o + dd * 0.04 for b, o, dd in zip(base, off, d)))
            parts.append(mg.part("cone", cream, loc=c, scale=(0.02, 0.02, n), rot=r))
        c = tuple(a + (b - a) * 0.4 for a, b in zip(el, wr))
        parts.append(mg.patch(fore, wound, at=(c[0], c[1] - 0.034, c[2]), size=(0.025, 0.02), thickness=0.004))

    # ---- the bandana: a red band round the neck and a triangle over the chest
    parts.append(mg.part("torus", bandana, loc=(0, 0.0, 0.475), scale=(0.15, 0.105, 0.06), major_radius=1.0, minor_radius=0.2))
    parts.append(mg.part("cone", bandana, loc=(0, -0.105, 0.425), scale=(0.24, 0.03, 0.13), rot=(math.pi, 0, 0), vertices=3))

    # ---- the head: a wide soft box, narrower at the top; a cream stripe down the middle and a cream muzzle
    hz = 0.7
    # seen from the front the head is a soft hexagon: a narrow crown between the ears, the widest at the cheeks, a
    # narrower chin (a box tapered at the top and the bottom), rounded a little
    head = mg.part("cube", grey, loc=(0, -0.01, hz), scale=(0.6, 0.38, 0.36), bevel=0.1, subdiv=2, taper=0.74,
                   taper_bottom=0.66, smooth=True)
    mg.cast(head, "sphere", 0.2)
    parts.append(head)
    lo, hi = mg.bounds(head)   # the face and the ears sit on the head as it really is
    face, htop = lo[1], hi[2]
    mg.focus((0, face, hz - 0.03), 0.15)   # the face is where players look
    parts.append(mg.patch(head, cream, at=(0.0, face, hz + 0.05), size=(0.085, 0.24), thickness=0.004))     # the stripe
    parts.append(mg.patch(head, cream, at=(0.0, face, hz - 0.095), size=(0.2, 0.1), thickness=0.005, dome=0.01))   # muzzle
    # ears: big, tilted out, pink inside; the right one torn
    for sx in (-1, 1):
        ear = mg.part("cone", grey, loc=(sx * 0.17, 0.0, htop + 0.06), scale=(0.22, 0.07, 0.26), rot=(0.05, sx * 0.45, 0), vertices=4)
        inner = mg.part("cone", pink, loc=(sx * 0.168, -0.025, htop + 0.05), scale=(0.16, 0.02, 0.2), rot=(0.05, sx * 0.45, 0),
                        vertices=4)
        if sx > 0:
            for dz in (0.0, 0.05):   # notches bitten out of the torn ear
                mg.cut(ear, mg.part("cube", grey, loc=(0.29, 0.0, htop + 0.04 + dz), scale=(0.05, 0.12, 0.025), rot=(0, 0.6, 0)))
        parts += [ear, inner]
    # eyes: a glowing lime one with a slit pupil (the cat's right) and a dead milky one, both in dark square sockets
    for sx in (-1, 1):
        parts.append(mg.patch(head, dark, at=(sx * 0.105, face, hz - 0.01), size=(0.125, 0.11), thickness=0.003))
    parts.append(mg.eye((-0.105, face + 0.026, hz - 0.01), 0.05, lime, look=(-0.1, -1, 0), pupil="slit", pupil_size=0.3))
    parts.append(mg.part("sphere", dead, loc=(0.105, face + 0.026, hz - 0.01), scale=(0.096, 0.096, 0.096), **ball))
    # nose, mouth and fangs
    parts.append(mg.part("cone", nose_c, loc=(0, face - 0.012, hz - 0.075), scale=(0.035, 0.02, 0.025), rot=(math.pi, 0, 0),
                         vertices=3))
    for sx in (-1, 1):
        parts.append(mg.part("cone", bone, loc=(sx * 0.025, face - 0.012, hz - 0.13), scale=(0.016, 0.012, 0.03),
                             rot=(math.pi, 0, 0)))
    parts.append(mg.part("cube", dark, loc=(0, face - 0.008, hz - 0.113), scale=(0.07, 0.006, 0.006)))   # the mouth line
    # stitches on the forehead: a scar with cross stitches over each eye
    for sx, tilt in ((-1, 0.5), (1, 0.0)):
        cx, cz = sx * 0.115, hz + 0.09
        parts.append(mg.part("cube", dark, loc=(cx, face - 0.004, cz), scale=(0.012, 0.008, 0.075), rot=(0, tilt, 0)))
        for k in (-1, 0, 1):
            parts.append(mg.part("cube", dark, loc=(cx + k * 0.02 * math.sin(tilt), face - 0.006, cz + k * 0.022 * math.cos(tilt)),
                                 scale=(0.04, 0.007, 0.007), rot=(0, tilt, 0)))
    # whiskers
    for sx in (-1, 1):
        for dz, dx in ((0.012, 0.0), (-0.01, 0.02)):
            parts.append(mg.tube([(sx * 0.07, face - 0.01, hz - 0.085 + dz), (sx * 0.33, face + 0.03, hz - 0.12 + dz * 3 + dx)],
                                 0.0016, cream, sides=4))

    # ---- the backpack with a skull badge
    pack = mg.part("cube", leather, loc=(0, 0.14, 0.38), scale=(0.2, 0.09, 0.2), bevel=0.02, subdiv=1, smooth=True)
    parts.append(pack)
    parts.append(mg.part("cube", shorts_c, loc=(0, 0.186, 0.43), scale=(0.19, 0.01, 0.09), bevel=0.004))         # the flap
    parts.append(mg.patch(pack, cream, at=(0, 0.186, 0.37), size=(0.08, 0.075), facing=(0, 1, 0), thickness=0.005))   # skull
    for sx in (-1, 1):
        parts.append(mg.part("sphere", dark, loc=(sx * 0.017, 0.192, 0.378), scale=(0.02, 0.01, 0.02), **ball))

    # ---- the striped tail curling up behind
    pts = [(0, 0.1, 0.2), (0.03, 0.22, 0.17), (0.08, 0.3, 0.22), (0.12, 0.33, 0.33), (0.13, 0.3, 0.44)]
    tail = mg.skin(pts, [0.035, 0.034, 0.032, 0.03, 0.026], cream)
    for z0, z1 in ((0.16, 0.19), (0.24, 0.28), (0.34, 0.38)):
        mg.paint(tail, stripe, above=z0, below=z1)
    mg.paint(tail, stripe, at=pts[-1], radius=0.04)
    parts.append(tail)

    mg.join("zombie_cat_scout", parts)
