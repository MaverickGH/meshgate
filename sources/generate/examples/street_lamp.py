"""Old cast-iron Victorian street lamp with a warm glowing lantern (single rigid mesh, no moving parts).

Written by an AI model from the MeshGate prompt alone ("Old cast-iron street lamp with a warm glowing lantern,
Victorian style", realistic, 3.2 m), built cleanly on the first attempt: 1.4k tris on mobile-low, 31k on pc.
"""
import math


def build(mg):
    mg.color("iron", (0.045, 0.05, 0.045), rough=0.45, metal=1.0)
    mg.color("iron_worn", (0.30, 0.29, 0.27), rough=0.35, metal=1.0)
    mg.color("rust", (0.36, 0.16, 0.07), rough=0.9, metal=0.0)
    mg.color("brass", (0.80, 0.60, 0.30), rough=0.3, metal=1.0)
    mg.color("glass", (1.0, 0.72, 0.38), rough=0.15, glow=3.0)

    parts = []

    # ---------------- base plinth (stepped, bulbous cast-iron foot) ----------------
    base_prof = [(0.26, 0.0), (0.26, 0.05), (0.23, 0.07), (0.23, 0.10), (0.20, 0.13),
                 (0.19, 0.30), (0.17, 0.42), (0.20, 0.46), (0.20, 0.50), (0.15, 0.55),
                 (0.12, 0.62), (0.11, 0.72), (0.13, 0.76), (0.13, 0.80), (0.085, 0.84), (0.0, 0.84)]
    parts.append(mg.lathe(base_prof, "iron", segments=24))

    # ---------------- column: tapered shaft with a top collar and lantern spigot ----------------
    col_prof = [(0.085, 0.82), (0.075, 0.90), (0.068, 1.60), (0.058, 2.30), (0.075, 2.33),
                (0.075, 2.38), (0.05, 2.42), (0.045, 2.50), (0.06, 2.53)]
    parts.append(mg.lathe(col_prof, "iron", segments=20))

    def col_r(z):
        return 0.075 + (0.058 - 0.075) * (z - 0.90) / (2.30 - 0.90)

    # decorative collars on the shaft
    for zc in (1.30, 2.05):
        rc = col_r(zc) + 0.012
        parts.append(mg.part("torus", "iron", loc=(0, 0, zc), scale=(rc, rc, rc)))

    # ---------------- ladder bar with ball ends ----------------
    bar_z = 2.28
    parts.append(mg.part("cyl", "iron", loc=(0, 0, bar_z), scale=(0.032, 0.032, 0.72),
                         rot=(0, math.pi / 2, 0)))
    ball = mg.part("sphere", "iron", loc=(0.37, 0, bar_z), scale=(0.075, 0.075, 0.075))
    parts += [ball, mg.mirror_x(ball)]

    # ---------------- lantern ----------------
    # bowl under the lantern (overlaps the spigot)
    bowl_prof = [(0.045, 2.49), (0.07, 2.52), (0.11, 2.56), (0.135, 2.59), (0.0, 2.59)]
    parts.append(mg.lathe(bowl_prof, "iron", segments=20))
    # base plate
    parts.append(mg.part("cube", "iron", loc=(0, 0, 2.6025), scale=(0.27, 0.27, 0.035), bevel=0.006))
    # glowing glass body, widening towards the top
    g_bot, g_top, g_z0, g_z1 = 0.11, 0.1485, 2.62, 2.96
    parts.append(mg.part("cube", "glass", loc=(0, 0, (g_z0 + g_z1) / 2),
                         scale=(2 * g_bot, 2 * g_bot, g_z1 - g_z0), taper=g_top / g_bot))
    # corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(mg.tube([(sx * (g_bot + 0.002), sy * (g_bot + 0.002), g_z0),
                                  (sx * (g_top + 0.002), sy * (g_top + 0.002), g_z1)],
                                 0.013, "iron", sides=6))
    # top frame, eave, pyramid roof, chimney, finial
    parts.append(mg.part("cube", "iron", loc=(0, 0, 2.975), scale=(0.33, 0.33, 0.035), bevel=0.005))
    parts.append(mg.part("cube", "iron", loc=(0, 0, 3.0), scale=(0.40, 0.40, 0.02), bevel=0.004))
    parts.append(mg.part("cube", "iron", loc=(0, 0, 3.07), scale=(0.38, 0.38, 0.13), taper=0.18))
    parts.append(mg.part("cyl", "iron", loc=(0, 0, 3.145), scale=(0.07, 0.07, 0.04), vertices=12))
    fin_prof = [(0.03, 3.16), (0.022, 3.17), (0.026, 3.18), (0.014, 3.19), (0.018, 3.198), (0.0, 3.215)]
    parts.append(mg.lathe(fin_prof, "iron", segments=12))

    # ---------------- mobile-mid: scroll brackets, lantern supports, fluting, base door ----------------
    if mg.at_least("mobile-mid"):
        n = mg.seg(10)
        pts = []
        for i in range(n + 1):
            t = i / n * math.pi / 2
            pts.append((0.062 + 0.24 * (1 - math.cos(t)), 0.0, 1.95 + 0.315 * math.sin(t)))
        br = mg.tube(pts, 0.013, "iron", sides=8)
        parts += [br, mg.mirror_x(br)]
        # curl at the foot of each bracket
        curl = mg.part("sphere", "iron", loc=(0.075, 0, 1.95), scale=(0.035, 0.035, 0.035))
        parts += [curl, mg.mirror_x(curl)]

        # four small supports from spigot to lantern plate
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts.append(mg.tube([(sx * 0.03, sy * 0.03, 2.46), (sx * 0.08, sy * 0.08, 2.50),
                                      (sx * 0.11, sy * 0.11, 2.59)], 0.01, "iron", sides=6))

        # reeded (fluted) shaft: raised ribs following the taper
        n_rib = 8
        for i in range(n_rib):
            a = i * 2 * math.pi / n_rib
            z0, z1 = 0.95, 2.20
            r0, r1 = col_r(z0), col_r(z1)
            parts.append(mg.tube([(r0 * math.cos(a), r0 * math.sin(a), z0),
                                  (r1 * math.cos(a), r1 * math.sin(a), z1)],
                                 0.0, "iron", sides=6, radii=[0.010, 0.008]))

        # arched inspection door on the front of the base (-Y)
        door = [(-0.055, 0.17), (0.055, 0.17)]
        steps = mg.seg(8)
        for i in range(steps + 1):
            a = math.pi * i / steps
            door.append((0.055 * math.cos(a), 0.33 + 0.055 * math.sin(a)))
        parts.append(mg.extrude(door, 0.04, "iron", loc=(0, -0.185, 0), bevel=0.004))

    # ---------------- mobile-high: glazing bars, bolts, brass fittings ----------------
    if mg.at_least("mobile-high"):
        for k in range(4):
            a = k * math.pi / 2
            dx, dy = math.cos(a), math.sin(a)
            parts.append(mg.tube([(dx * (g_bot + 0.003), dy * (g_bot + 0.003), g_z0),
                                  (dx * (g_top + 0.003), dy * (g_top + 0.003), g_z1)],
                                 0.006, "iron", sides=6))
            zm = (g_z0 + g_z1) / 2
            wm = (g_bot + g_top) / 2 + 0.003
            px, py = -dy, dx
            parts.append(mg.tube([(dx * wm - px * wm, dy * wm - py * wm, zm),
                                  (dx * wm + px * wm, dy * wm + py * wm, zm)],
                                 0.006, "iron", sides=6))
        # brass lantern door knob and base door keyhole boss
        parts.append(mg.part("sphere", "brass", loc=(0.07, -(wm + 0.01), 2.74), scale=(0.022, 0.022, 0.022)))
        parts.append(mg.part("sphere", "brass", loc=(0.0, -0.207, 0.25), scale=(0.018, 0.018, 0.018)))
        # hold-down bolts on the foot
        for i in range(8):
            a = (i + 0.5) * 2 * math.pi / 8
            parts.append(mg.part("cyl", "iron", loc=(0.245 * math.cos(a), 0.245 * math.sin(a), 0.062),
                                 scale=(0.026, 0.026, 0.022), vertices=6, bevel=0.002))
        # corner rivets on the lantern top frame
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts.append(mg.part("sphere", "iron", loc=(sx * 0.15, sy * 0.15, 2.995),
                                     scale=(0.018, 0.018, 0.018)))

    # ---------------- pc: wear (rust streaks, chipped paint) ----------------
    if mg.at_least("pc"):
        def stain(color, r, z, a, w, h):
            return mg.part("sphere", color, loc=(r * math.cos(a), r * math.sin(a), z),
                           scale=(w, 0.012, h), rot=(0, 0, a - math.pi / 2), segments=10, ring_count=6)

        for i in range(10):
            z = mg.rng.uniform(0.15, 0.29)
            a = mg.rng.uniform(0, 2 * math.pi)
            if abs(math.sin(a) + 1) < 0.15:     # keep clear of the front door
                a += 0.8
            parts.append(stain("rust", 0.195 - (z - 0.13) * 0.06 - 0.004, z, a,
                               mg.rng.uniform(0.015, 0.03), mg.rng.uniform(0.03, 0.07)))
        for i in range(8):
            z = mg.rng.uniform(0.95, 2.2)
            a = mg.rng.uniform(0, 2 * math.pi)
            parts.append(stain("iron_worn", col_r(z) - 0.003, z, a,
                               mg.rng.uniform(0.01, 0.02), mg.rng.uniform(0.015, 0.04)))
        for i in range(6):
            a = mg.rng.uniform(0, 2 * math.pi)
            parts.append(stain("iron_worn", 0.255, 0.03, a, mg.rng.uniform(0.02, 0.04), 0.02))
        # a rust run below each bolt-free side of the ladder bar ends
        for sx in (-1, 1):
            parts.append(mg.part("sphere", "rust", loc=(sx * 0.37, 0, bar_z - 0.045),
                                 scale=(0.045, 0.045, 0.03)))

    mg.join("street_lamp", parts)
