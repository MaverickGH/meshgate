"""Zombie cat scout, a chibi character about 1 m tall standing in an A-pose, after a character sheet: a big head of grey
fur with a cream stripe down the middle and a cream muzzle, fluffy cheeks, big ears with torn pink insides, one glowing
lime eye with a slit pupil and one dead milky eye in dark sockets, stitched scars, little fangs, long whiskers; a red
bandana, a torn olive shirt open over the cream chest with ragged sleeves and hem, brown suspenders with brass buckles,
a belt with two pouches, torn brown shorts flaring at the hem with a patch, cream arms and legs with brown stripes, a
bandage wound round the wrist, toes and claws, a thick grey tail with cream bands swinging low to its right and turning
up, a brown backpack with a skull badge; the stripe runs over the crown down the back of the head, a cream patch round
the glowing eye, the shirt worn thin with faded patches and holes. Colours from the sheet's palette. The sheet is drawn
low-poly: build it with --style lowpoly (the head, a cube with a wide two-step bevel, turns many-sided); no animation."""
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
    faded = mg.color("shirt_faded", "#9ca079", rough=0.9, material="fabric")
    parts = []

    def along(a, b):
        """Centre, length and rotation of a block laid from point a to point b (its own Z along a → b)."""
        a, b = mathutils.Vector(a), mathutils.Vector(b)
        d = b - a
        pitch = math.atan2(math.hypot(d.x, d.y), d.z)
        yaw = math.atan2(d.y, d.x)
        return tuple((a + b) / 2), d.length, (0.0, pitch, yaw)

    def lerp(a, b, t):
        return tuple(x + (y - x) * t for x, y in zip(a, b))

    # ---- legs and feet: short cream legs with brown stripes, big feet with toes and claws
    with mg.section("legs"):
        for sx in (-1, 1):
            leg = mg.part("cube", cream, loc=(sx * 0.082, 0.0, 0.1), scale=(0.095, 0.11, 0.16), bevel=0.03, subdiv=1, smooth=True,
                          taper=1.1)
            foot = mg.part("cube", cream, loc=(sx * 0.1, -0.045, 0.034), scale=(0.15, 0.22, 0.07), bevel=0.025, subdiv=1,
                           smooth=True, taper=0.8)
            parts += [leg, foot]
            for t in (0.35, 0.65):   # stripes that stand off the fur a little
                parts.append(mg.wrap(leg, stripe, (sx * 0.082, 0, 0.02), (sx * 0.082, 0, 0.18), t, width=0.022, thickness=0.003))
            for k in (-1, 0, 1):   # three toes, each with a claw
                tx = sx * 0.1 + k * 0.043
                parts.append(mg.part("sphere", cream, loc=(tx, -0.155, 0.03), scale=(0.044, 0.05, 0.045)))
                parts.append(mg.part("cone", bone, loc=(tx, -0.185, 0.022), scale=(0.02, 0.02, 0.04), rot=(math.pi / 2 + 0.3, 0, 0)))

    # ---- torn brown shorts flaring at the hem, a sewn patch, a belt with two pouches
    with mg.section("shorts"):
        shorts = mg.part("cube", shorts_c, loc=(0, 0.0, 0.205), scale=(0.3, 0.2, 0.13), bevel=0.035, subdiv=1, smooth=True,
                         taper_bottom=1.1)
        parts += [shorts, mg.fringe(shorts, shorts_c, 0.15, depth=0.035, width=0.032, seed=3)]
        parts.append(mg.patch(shorts, leather, at=(0.085, -0.1, 0.19), size=(0.055, 0.05), thickness=0.004))
        parts.append(mg.stitch(shorts, dark, [(0.058, -0.12, 0.215), (0.112, -0.12, 0.215)], ticks=3, width=0.012))
        parts.append(mg.wrap(shorts, leather, (0, 0, 0.14), (0, 0, 0.27), 0.93, width=0.032, thickness=0.008))   # the belt
        parts.append(mg.buckle(brass, (0, -0.108, 0.262), size=0.042))
        for sx in (-1, 1):   # pouches on the hips, flaps buckled down
            parts.append(mg.pouch(shorts, leather, (sx * 0.125, -0.1, 0.225), size=(0.06, 0.065, 0.04), flap=shorts_c,
                                  buckle=brass))

    # ---- the body: cream fur, and over it a torn olive shirt, open down the front over the chest
    with mg.section("torso"):
        torso = mg.part("cube", cream, loc=(0, 0.0, 0.365), scale=(0.31, 0.18, 0.24), bevel=0.05, subdiv=1, smooth=True,
                        taper=0.84)   # wider at the hem
        shirt_body = mg.garment(torso, shirt, above=0.245, below=0.49, open_front=0.075, thickness=0.012, gap=0.004)
        parts += [torso, shirt_body, mg.fringe(shirt_body, shirt, 0.258, depth=0.045, width=0.036, seed=7)]
        parts.append(mg.patch(torso, wound, at=(-0.012, -0.1, 0.33), size=(0.025, 0.018), thickness=0.006))  # a wound
        # the shirt is worn thin: faded patches, holes with the fur showing through, a few blood stains, front and back
        for at, size, col, facing in (((-0.12, -0.1, 0.42), (0.07, 0.06), faded, (0, -1, 0)), ((0.12, -0.1, 0.31), (0.06, 0.05), faded, (0, -1, 0)),
                                      ((-0.1, -0.1, 0.3), (0.035, 0.03), cream, (0, -1, 0)), ((0.1, -0.1, 0.44), (0.025, 0.02), wound, (0, -1, 0)),
                                      ((0.1, 0.1, 0.44), (0.08, 0.06), faded, (0, 1, 0)), ((-0.11, 0.1, 0.3), (0.05, 0.045), faded, (0, 1, 0)),
                                      ((-0.16, 0.0, 0.4), (0.05, 0.05), faded, (-1, 0, 0)), ((0.16, 0.0, 0.33), (0.04, 0.035), cream, (1, 0, 0))):
            parts.append(mg.patch(shirt_body, col, at=at, size=size, facing=facing, thickness=0.004))
        # suspenders: over each shoulder from the belt in front to the belt behind, brass buckles on the chest
        for sx in (-1, 1):
            x = sx * 0.075
            parts.append(mg.strap(shirt_body, leather, [(x, -0.12, 0.27), (x, -0.12, 0.44), (x * 1.15, -0.02, 0.5),
                                                        (x * 1.15, 0.06, 0.49), (x, 0.12, 0.44), (x, 0.12, 0.27)],
                                  width=0.028, thickness=0.006))
            parts.append(mg.buckle(brass, (x, -0.118, 0.41), size=0.036))

    # ---- arms in an A-pose: flared, torn olive sleeves; striped cream forearms; a wound bandage; clawed hands
    with mg.section("arms", anchor=(0.14, 0.0, 0.46)):   # both arms grow from their shoulders
        for sx in (-1, 1):
            sh = (sx * 0.14, 0.0, 0.46)
            drop = math.radians(45)
            d = tuple(c / math.hypot(math.cos(drop), 0.15, math.sin(drop)) for c in (sx * math.cos(drop), -0.15, -math.sin(drop)))   # reaching a little forward
            el = tuple(s + k * 0.12 for s, k in zip(sh, d))
            wr = tuple(s + k * 0.22 for s, k in zip(sh, d))
            tip = tuple(s + k * 0.28 for s, k in zip(sh, d))
            c, n, r = along(sh, el)
            upper = mg.part("cube", cream, loc=c, scale=(0.07, 0.075, n + 0.04), rot=r, bevel=0.02, subdiv=1, smooth=True,
                            taper=1.15)
            # the sleeve: a layer over the arm down to past the elbow, flaring and torn at its end
            sleeve = mg.garment(upper, shirt, along=(sh, el), span=(-0.3, 1.05), thickness=0.012, gap=0.005)
            parts += [upper, sleeve, mg.fringe(sleeve, shirt, at=lerp(sh, el, 1.0), axis=tuple(-x for x in d), depth=0.03,
                                               width=0.025, seed=11 + sx)]
            c, n, r = along(el, wr)
            fore = mg.part("cube", cream, loc=c, scale=(0.07, 0.072, n + 0.03), rot=r, bevel=0.015, subdiv=1, smooth=True)
            parts.append(fore)
            parts.append(mg.wrap(fore, stripe, el, wr, 0.3, width=0.018, thickness=0.003))
            for k, t in enumerate((0.62, 0.74, 0.86)):   # the bandage, wound at an angle, one turn of it red
                parts.append(mg.wrap(fore, bandana if k == 1 else bone, el, wr, t, width=0.02, thickness=0.004, slant=0.3))
            c, n, r = along(wr, tip)
            parts.append(mg.part("cube", cream, loc=c, scale=(0.088, 0.078, n + 0.015), rot=r, bevel=0.02, subdiv=1, smooth=True))
            base = lerp(wr, tip, 1.05)
            for k in (-1, 0, 1):   # claws
                root = (base[0], base[1] + k * 0.024, base[2])
                c, n, r = along(root, tuple(b + o * 0.045 for b, o in zip(root, d)))
                parts.append(mg.part("cone", bone, loc=c, scale=(0.02, 0.02, n), rot=r))
            c = lerp(el, wr, 0.4)
            parts.append(mg.patch(fore, wound, at=(c[0], c[1] - 0.036, c[2]), size=(0.025, 0.02), thickness=0.004))

    # ---- the bandana: a red band round the neck and a triangle over the chest
    with mg.section("neck"):
        parts.append(mg.part("torus", bandana, loc=(0, 0.0, 0.475), scale=(0.15, 0.105, 0.06), major_radius=1.0, minor_radius=0.2))
        parts.append(mg.part("cone", bandana, loc=(0, -0.105, 0.425), scale=(0.24, 0.03, 0.13), rot=(math.pi, 0, 0), vertices=3))

    # ---- the head: seen from the front a soft hexagon (a narrow crown between the ears, the widest at the cheeks, a
    # narrower chin), fluffy cheeks; a cream stripe down the middle and a cream muzzle
    hz = 0.7
    with mg.section("head", anchor=(0, -0.01, 0.52)):   # it grows from the neck
        # a wide two-step bevel: in the low-poly finish a many-sided head (as the sheet draws it) with flat front planes
        head = mg.part("cube", grey, loc=(0, -0.01, hz), scale=(0.6, 0.44, 0.38), bevel=0.13, bevel_segments=2, subdiv=2,
                       taper=0.82, taper_bottom=0.66, smooth=True)
        mg.cast(head, "sphere", 0.25)
        parts.append(head)
        lo, hi = mg.bounds(head)   # the face, cheeks and ears sit on the head as it really is
        face, htop, hw = lo[1], hi[2], hi[0]
        mg.focus((0, face, hz - 0.03), 0.15)   # the face is where players look
        for sx in (-1, 1):   # fluffy cheeks: tufts sticking out at the jaw, breaking the head's outline as in the sheet
            for dz, sc in ((0.0, 1.0), (-0.045, 0.8)):
                parts.append(mg.part("cone", grey, loc=(sx * (hw - 0.01), -0.03, hz - 0.05 + dz), scale=(0.042 * sc, 0.04, 0.075 * sc),
                                     rot=(0.15, sx * 1.95, 0), vertices=4))
        parts.append(mg.patch(head, cream, at=(0.0, face, hz + 0.05), size=(0.085, 0.24), thickness=0.004))     # the stripe
        # …that runs on over the crown and down the back of the head, widening, as the back view shows
        parts.append(mg.wrap(head, cream, (-0.5, -0.01, hz + 0.02), (0.5, -0.01, hz + 0.02), 0.5, width=0.11, thickness=0.004))
        parts.append(mg.patch(head, cream, at=(0.0, 0.2, hz + 0.02), size=(0.17, 0.3), facing=(0, 1, 0), thickness=0.004))
        # a cream patch round the glowing eye, reaching up the forehead and down the cheek
        parts.append(mg.patch(head, cream, at=(-0.13, face, hz + 0.02), size=(0.19, 0.24), thickness=0.0035))
        parts.append(mg.patch(head, cream, at=(0.0, face, hz - 0.095), size=(0.21, 0.11), thickness=0.005, dome=0.01))   # muzzle
        # eyes: a glowing lime one with a slit pupil (the cat's right) and a dead milky one, both in dark square sockets
        for sx in (-1, 1):
            parts.append(mg.patch(head, dark, at=(sx * 0.105, face, hz - 0.01), size=(0.125, 0.11), thickness=0.003))
        parts.append(mg.eye((-0.105, face + 0.026, hz - 0.01), 0.05, lime, look=(-0.1, -1, 0), pupil="slit", pupil_size=0.3))
        parts.append(mg.part("sphere", dead, loc=(0.105, face + 0.026, hz - 0.01), scale=(0.096, 0.096, 0.096)))
        # nose, mouth and fangs
        parts.append(mg.part("cone", nose_c, loc=(0, face - 0.012, hz - 0.075), scale=(0.035, 0.02, 0.025), rot=(math.pi, 0, 0),
                             vertices=3))
        for sx in (-1, 1):
            parts.append(mg.part("cone", bone, loc=(sx * 0.025, face - 0.012, hz - 0.13), scale=(0.016, 0.012, 0.03),
                                 rot=(math.pi, 0, 0)))
        parts.append(mg.part("cube", dark, loc=(0, face - 0.008, hz - 0.113), scale=(0.07, 0.006, 0.006)))   # the mouth line
        # stitched scars on the forehead and a cheek
        parts.append(mg.stitch(head, dark, [(-0.15, face, hz + 0.13), (-0.1, face, hz + 0.06)], ticks=3, width=0.03))
        parts.append(mg.stitch(head, dark, [(0.115, face, hz + 0.135), (0.115, face, hz + 0.065)], ticks=3, width=0.03))
        parts.append(mg.stitch(head, dark, [(0.17, face, hz - 0.06), (0.2, face, hz - 0.1)], ticks=2, width=0.02))
        # whiskers
        for sx in (-1, 1):
            for dz, dx in ((0.012, 0.0), (-0.01, 0.02)):
                parts.append(mg.tube([(sx * 0.07, face - 0.01, hz - 0.085 + dz), (sx * 0.33, face + 0.03, hz - 0.12 + dz * 3 + dx)],
                                     0.0016, cream, sides=4))
    with mg.section("ears", anchor=(0.17, 0.0, htop - 0.02)):
        # ears: big, tilted out, pink inside; the right one torn
        for sx in (-1, 1):
            ear = mg.part("cone", grey, loc=(sx * 0.17, 0.02, htop + 0.06), scale=(0.22, 0.16, 0.26), rot=(-0.3, sx * 0.45, 0),
                          vertices=4)
            inner = mg.part("cone", pink, loc=(sx * 0.168, -0.03, htop + 0.05), scale=(0.16, 0.03, 0.2), rot=(-0.3, sx * 0.45, 0),
                            vertices=4)
            if sx > 0:
                for dz in (0.0, 0.05):   # notches bitten out of the torn ear
                    mg.cut(ear, mg.part("cube", grey, loc=(0.29, 0.0, htop + 0.04 + dz), scale=(0.05, 0.12, 0.025), rot=(0, 0.6, 0)))
            parts += [ear, inner]
            if sx > 0:
                ear_r = [ear, inner]

    # ---- the backpack with a skull badge, straps over the shoulders
    with mg.section("backpack"):
        pack = mg.part("cube", leather, loc=(0, 0.14, 0.38), scale=(0.2, 0.09, 0.2), bevel=0.02, subdiv=1, smooth=True)
        parts.append(pack)
        parts.append(mg.part("cube", shorts_c, loc=(0, 0.186, 0.43), scale=(0.19, 0.01, 0.09), bevel=0.004))         # the flap
        parts.append(mg.part("cube", brass, loc=(0, 0.19, 0.39), scale=(0.03, 0.008, 0.02), bevel=0.002))            # its clasp
        parts.append(mg.patch(pack, cream, at=(0, 0.186, 0.33), size=(0.08, 0.075), facing=(0, 1, 0), thickness=0.005))   # skull
        for sx in (-1, 1):
            parts.append(mg.part("sphere", dark, loc=(sx * 0.017, 0.192, 0.338), scale=(0.02, 0.01, 0.02)))
            parts.append(mg.part("cube", leather, loc=(sx * 0.12, 0.05, 0.47), scale=(0.035, 0.12, 0.015), rot=(0.25, 0, 0)))   # strap
            parts.append(mg.part("cube", leather, loc=(sx * 0.105, 0.195, 0.36), scale=(0.02, 0.012, 0.16)))   # side straps

    # ---- the striped tail curling up behind
    # low behind the cat, towards its right side, the tip turned up — as the back and side views show
    with mg.section("tail", anchor=(0, 0.1, 0.2)):
        pts = [(0, 0.1, 0.2), (-0.03, 0.2, 0.12), (-0.08, 0.3, 0.08), (-0.14, 0.37, 0.12), (-0.18, 0.39, 0.22), (-0.19, 0.36, 0.32)]
        # thick and blocky, grey with cream bands (as the side and back views show)
        tail = mg.skin(pts, [0.05, 0.05, 0.048, 0.045, 0.042, 0.038], grey)   # back, down, then up, as the side view shows
        for z0, z1 in ((0.1, 0.13), (0.17, 0.21), (0.26, 0.3)):
            mg.paint(tail, cream, above=z0, below=z1)
        mg.paint(tail, cream, at=pts[-1], radius=0.05)
        parts.append(tail)

    # ---- the character creator: sliders kept in the file as morph targets (Studio moves them live, a game can too)
    neck = 0.52
    mg.morph("head_size", "Head size", at=(0, -0.01, hz - 0.12), scale=1.15, above=neck, blend=0.05)
    mg.morph("head_width", "Head width", at=(0, -0.01, hz), scale=(1.2, 1.0, 1.0), above=neck, blend=0.05)
    mg.morph("ear_size", "Ear size", at=(0.17, 0.0, htop - 0.02), radius=0.3, scale=1.35, pieces=ear_r, mirror=True)
    mg.morph("eye_size", "Eye size", at=(0.105, face + 0.02, hz - 0.01), radius=0.1, scale=1.3, mirror=True)
    mg.morph("muzzle", "Muzzle", at=(0, face, hz - 0.1), radius=0.12, scale=(1.2, 1.4, 1.15))
    mg.morph("belly", "Belly", at=(0, -0.02, 0.33), radius=0.24, inflate=0.035, below=neck - 0.03)
    mg.morph("leg_length", "Leg length", at=(0, 0, 0), stretch=(0.06, 0.2, 0.07))
    mg.morph("tail_length", "Tail length", at=(0, 0.1, 0.2), radius=0.45, scale=1.3,
             pieces=[tail])

    mg.join("zombie_cat_scout", parts)
