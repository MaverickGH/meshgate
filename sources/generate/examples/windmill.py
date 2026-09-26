"""Stylized wooden smock windmill: octagonal tapered tower, gallery, domed cap and four rotating sails.

Written by an AI model from the MeshGate prompt alone ("Деревянная ветряная мельница с вращающимися лопастями"),
built cleanly on the first attempt: 1.4k tris on mobile-low, 22k on pc, a looping "spin" clip.
"""
import math


def build(mg):
    pi = math.pi
    lvl = mg.level
    mg.color("wood", "#b27a45", rough=0.8)
    mg.color("wood_mid", "#94613a", rough=0.8)
    mg.color("wood_dark", "#6b4226", rough=0.85)
    mg.color("wood_light", "#d9ad72", rough=0.75)
    mg.color("roof", "#a8452f", rough=0.75)
    mg.color("canvas", "#f1e6c8", rough=0.9)
    mg.color("paint", "#4f7f6a", rough=0.7)
    mg.color("stone", "#9a958c", rough=0.9)
    mg.color("stone_dark", "#77736c", rough=0.9)
    mg.color("iron", "#3b3b40", rough=0.45, metal=1.0)
    mg.color("glass", "#4a7394", rough=0.15)
    mg.color("sack", "#d8c49a", rough=0.95)
    mg.color("lamp", "#ffcf70", rough=0.3, glow=3.0)

    # tower dimensions (meters)
    z0, H, r0, tp = 0.5, 7.5, 2.6, 0.6
    r1 = r0 * tp
    zt = z0 + H
    zg = 3.0                      # gallery floor
    zh = 8.9                      # windshaft height
    ys = -3.3                     # sail plane (in front of the gallery)
    L = 6.8                       # sail length from the axle
    c8 = math.cos(pi / 8)
    orot = (0, 0, pi / 8)         # puts a flat octagon face towards -Y
    lean = math.atan((r0 - r1) * c8 / H)

    def rad(z):
        return r0 - (r0 - r1) * (z - z0) / H

    def apo(z):
        return rad(z) * c8

    def prism(color, z, h, r, **kw):
        return mg.part("cyl", color, loc=(0, 0, z), scale=(2 * r, 2 * r, h), rot=orot,
                       vertices=8, smooth=False, **kw)

    def opening(phi, zb, w, h, color, cross=False, hinges=False):
        zc = zb + h / 2
        a = apo(zc)
        dx, dy = math.cos(phi), math.sin(phi)
        rot = (-lean, 0, phi + pi / 2)

        def at(r, z):
            return (dx * r, dy * r, z)

        out = [mg.part("cube", "wood_dark", loc=at(a - 0.1, zc), scale=(w + 0.2, 0.6, h + 0.2), rot=rot, bevel=0.03),
               mg.part("cube", color, loc=at(a - 0.13, zc), scale=(w, 0.6, h), rot=rot, bevel=0.01)]
        if cross and mg.at_least("mobile-mid"):
            out.append(mg.part("cube", "wood_dark", loc=at(a + 0.17, zc), scale=(w, 0.05, 0.06), rot=rot))
            out.append(mg.part("cube", "wood_dark", loc=at(a + 0.17, zc), scale=(0.06, 0.05, h), rot=rot))
        if hinges and mg.at_least("mobile-high"):
            for f in (0.22, 0.78):
                zz = zb + h * f
                out.append(mg.part("cube", "iron", loc=at(apo(zz) + 0.17, zz), scale=(w * 0.85, 0.05, 0.08),
                                   rot=rot, bevel=0.005))
        return out

    # ---- stone plinth, tower, trims ----
    body = [prism("stone", z0 / 2, z0, 3.0, bevel=0.04),
            mg.part("cyl", "wood", loc=(0, 0, z0 + H / 2), scale=(2 * r0, 2 * r0, H), rot=orot,
                    vertices=8, smooth=False, taper=tp),
            prism("wood_dark", z0 + 0.12, 0.25, r0 + 0.08),
            prism("wood_dark", zt - 0.1, 0.25, r1 + 0.1),
            mg.part("cube", "stone", loc=(0, -3.05, 0.12), scale=(1.5, 0.7, 0.24), bevel=0.03)]
    if mg.at_least("mobile-high"):   # weatherboard lines
        step = 0.5 if lvl == 2 else 0.34
        z = z0 + 0.45
        while z < zt - 0.3:
            body.append(prism("wood_mid", z, 0.06, rad(z) + 0.02))
            z += step

    # ---- doors and windows ----
    body += opening(-pi / 2, z0, 1.1, 2.0, "paint", hinges=True)
    body += opening(-pi / 2, zg, 0.9, 1.75, "paint", hinges=True)
    body += opening(-pi / 2, 5.7, 0.7, 0.9, "glass", cross=True)
    if mg.at_least("mobile-mid"):
        for phi in (0.0, pi):
            body += opening(phi, 4.4, 0.7, 0.9, "glass", cross=True)
    if mg.at_least("pc"):
        for phi in (pi / 4, 3 * pi / 4):
            body += opening(phi, 6.0, 0.6, 0.8, "glass", cross=True)

    # ---- gallery ----
    body.append(prism("wood_dark", zg - 0.1, 0.2, 2.8, bevel=0.02))
    if mg.at_least("mobile-mid"):
        n = 8 if lvl == 1 else 16
        pts = []
        for i in range(n):
            th = 2 * pi * i / n + pi / n
            px, py = 2.5 * math.cos(th), 2.5 * math.sin(th)
            pts.append((px, py))
            body.append(mg.part("cyl", "wood_dark", loc=(px, py, zg + 0.47), scale=(0.1, 0.1, 0.95), vertices=6))
        heights = [zg + 0.95] + ([zg + 0.5] if mg.at_least("mobile-high") else [])
        for hz in heights:
            loop = [(p[0], p[1], hz) for p in pts]
            body.append(mg.tube(loop + [loop[0]], 0.05, "wood_dark", sides=6))
    if mg.at_least("mobile-high"):   # braces under the gallery, skipping the front door face
        for k in range(8):
            if k == 6:
                continue
            phi = k * pi / 4
            dx, dy = math.cos(phi), math.sin(phi)
            zb = zg - 1.1
            ra = apo(zb) - 0.05
            body.append(mg.tube([(dx * ra, dy * ra, zb), (dx * 2.45, dy * 2.45, zg - 0.12)], 0.07, "wood_dark", sides=6))

    # ---- cap: curb ring, shingled dome, finial, breast box ----
    body.append(mg.part("cyl", "wood_dark", loc=(0, 0, zt + 0.15), scale=(3.6, 3.6, 0.3), vertices=16, bevel=0.03))
    R, Hd, zd = 1.72, 1.9, zt + 0.3
    stepped = mg.at_least("mobile-mid")
    rows = [6, 5, 7, 9][lvl]
    prof = [(R, 0.0)]
    for i in range(rows):
        t0, t1 = i / rows, (i + 1) / rows
        if stepped:
            prof.append((R * math.cos(t0 * pi / 2) + 0.07, Hd * math.sin(t0 * pi / 2)))
        r = 0.0 if i == rows - 1 else R * math.cos(t1 * pi / 2)
        prof.append((r, Hd * math.sin(t1 * pi / 2)))
    body.append(mg.lathe(prof, "roof", loc=(0, 0, zd), smooth=not stepped))
    body.append(mg.tube([(0, 0, zd + Hd - 0.1), (0, 0, zd + Hd + 0.35)], 0.05, "iron", sides=6))
    body.append(mg.part("sphere", "iron", loc=(0, 0, zd + Hd + 0.42), scale=(0.22, 0.22, 0.22)))
    if mg.at_least("pc"):
        body.append(mg.part("cone", "iron", loc=(0, 0, zd + Hd + 0.62), scale=(0.08, 0.08, 0.3)))
    body.append(mg.part("cube", "wood_dark", loc=(0, -2.0, zh), scale=(0.9, 1.4, 0.9), bevel=0.04))
    if mg.at_least("mobile-mid"):
        body.append(mg.extrude([(-0.62, 0), (0.62, 0), (0, 0.42)], 1.5, "roof", loc=(0, -1.95, zh + 0.45)))

    # ---- tail pole with chain wheel (rests on the gallery rail) ----
    if mg.at_least("mobile-mid"):
        top, bot = (0, 1.2, 8.7), (0, 2.4, zg + 0.9)

        def lerp(t):
            return tuple(top[j] + (bot[j] - top[j]) * t for j in range(3))

        body.append(mg.tube([top, bot], 0.11, "wood_dark", sides=8))
        for s in (-1, 1):
            body.append(mg.tube([(s * 0.9, 1.1, 8.3), lerp(0.35)], 0.06, "wood_dark", sides=6))
        if mg.at_least("pc"):
            wx, wy, wz = lerp(0.8)
            body.append(mg.part("torus", "wood_dark", loc=(0.2, wy, wz), scale=(0.4, 0.4, 0.4), rot=(0, pi / 2, 0)))
            body.append(mg.part("cube", "wood_dark", loc=(0.2, wy, wz), scale=(0.06, 0.8, 0.06)))
            body.append(mg.part("cube", "wood_dark", loc=(0.2, wy, wz), scale=(0.06, 0.06, 0.8)))
            body.append(mg.part("cyl", "iron", loc=(0.08, wy, wz), scale=(0.08, 0.08, 0.3), rot=(0, pi / 2, 0)))

    # ---- props around the base ----
    if mg.at_least("mobile-mid"):   # lantern beside the door
        a = apo(2.25)
        body.append(mg.tube([(0.8, -a + 0.1, 2.55), (0.8, -a - 0.35, 2.55), (0.8, -a - 0.35, 2.42)], 0.03, "iron", sides=6))
        body.append(mg.part("cube", "lamp", loc=(0.8, -a - 0.35, 2.28), scale=(0.16, 0.16, 0.24)))
        body.append(mg.part("cone", "iron", loc=(0.8, -a - 0.35, 2.44), scale=(0.26, 0.26, 0.1)))
        body.append(mg.part("cube", "iron", loc=(0.8, -a - 0.35, 2.15), scale=(0.2, 0.2, 0.04)))
    if mg.at_least("mobile-high"):
        for x, y, s in ((1.35, -3.2, 1.0), (1.9, -2.95, 0.85)):   # flour sacks
            body.append(mg.part("sphere", "sack", loc=(x, y, 0.34 * s), scale=(0.55 * s, 0.45 * s, 0.68 * s)))
            body.append(mg.part("cyl", "sack", loc=(x, y, 0.66 * s), scale=(0.14 * s, 0.14 * s, 0.14 * s)))
        n = 14 if lvl == 2 else 24
        for i in range(n):   # stone course along the plinth
            th = 2 * pi * i / n + mg.rng.uniform(-0.05, 0.05)
            if abs(th - 1.5 * pi) < 0.3:
                continue
            size = (mg.rng.uniform(0.5, 0.8), 0.35, mg.rng.uniform(0.18, 0.3))
            body.append(mg.part("cube", mg.rng.choice(["stone", "stone_dark"]),
                                loc=(2.85 * math.cos(th), 2.85 * math.sin(th), mg.rng.uniform(0.15, 0.35)),
                                scale=size, rot=(0, 0, th + pi / 2), bevel=0.04))
    if mg.at_least("pc"):
        body.append(mg.part("cube", "wood_mid", loc=(-1.6, -3.25, 0.3), scale=(0.6, 0.6, 0.6), rot=(0, 0, 0.3), bevel=0.03))

    tower = mg.join("windmill_body", body)

    # ---- rotor: windshaft, hub and four sails (moving part) ----
    rotor = [mg.part("cyl", "wood_dark", loc=(0, -3.0, zh), scale=(0.34, 0.34, 1.0), rot=(pi / 2, 0, 0)),
             mg.part("cyl", "wood_dark", loc=(0, ys, zh), scale=(0.9, 0.9, 0.5), rot=(pi / 2, 0, 0), bevel=0.03),
             mg.part("cone", "iron", loc=(0, ys - 0.43, zh), scale=(0.6, 0.6, 0.4), rot=(pi / 2, 0, 0))]
    if mg.at_least("pc"):
        for i in range(8):
            th = 2 * pi * i / 8
            rotor.append(mg.part("cyl", "iron", loc=(0.36 * math.cos(th), ys - 0.26, zh + 0.36 * math.sin(th)),
                                 scale=(0.07, 0.07, 0.06), rot=(pi / 2, 0, 0), vertices=6))

    def sp(a, px, pz, dy, size, color, bevel=0.0):
        x = px * math.cos(a) + pz * math.sin(a)
        z = zh - px * math.sin(a) + pz * math.cos(a)
        return mg.part("cube", color, loc=(x, ys + dy, z), scale=size, rot=(0, a, 0), bevel=bevel)

    rs0, rs1 = 1.3, L - 0.15
    ln, mid = rs1 - rs0, (rs0 + rs1) / 2
    wd, off = 1.45, 0.14
    nbars = [4, 6, 9, 13][lvl]
    for k in range(4):
        a = pi / 4 + k * pi / 2
        rotor.append(sp(a, 0, (L + 0.2) / 2, 0, (0.24, 0.24, L - 0.2), "wood_dark", bevel=0.02))
        rotor.append(sp(a, off + wd, mid, -0.06, (0.09, 0.1, ln), "wood_light"))
        rotor.append(sp(a, off + wd / 2, mid, -0.03, (wd - 0.02, 0.03, ln - 0.05), "canvas"))
        for i in range(nbars):
            rotor.append(sp(a, off + wd / 2, rs0 + ln * i / (nbars - 1), -0.1, (wd + 0.1, 0.07, 0.08), "wood_light"))
        if mg.at_least("mobile-mid"):
            rotor.append(sp(a, -0.28, mid, -0.02, (0.36, 0.05, ln), "wood_light"))
        if mg.at_least("pc"):
            for pz in (0.7, 1.05):
                rotor.append(sp(a, 0, pz, 0, (0.28, 0.28, 0.08), "iron"))

    sails = mg.join("windmill_sails", rotor)
    mg.pivot(sails, (0, ys, zh))
    mg.attach(sails, tower)
    # counter-clockwise seen from the front, one turn every 4 s, constant speed
    mg.animate(sails, "spin", [(1, (0, 0, 0)), (61, (0, -pi, 0)), (121, (0, -2 * pi, 0))], smooth=False)
