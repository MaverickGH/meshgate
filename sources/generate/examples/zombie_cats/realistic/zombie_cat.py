"""Zombie cat character standing upright on two legs like a person, about 1 m tall: grey-green fur, a stitched scar
across its head, a torn ear, glowing green eyes, arms stretched forward like a zombie. Sculpted with the kit's clay
(one blob body), painted in regions, creased and stitched; after the Zombie Cats concept art (docs/img)."""
import math


def build(mg):
    # sliders the artist can tune in Studio without asking the AI again
    ears = mg.param("ear_size", 1.0, 0.6, 1.6, label="Ear size")
    eye_r = mg.param("eye_size", 0.039, 0.028, 0.05, label="Eye size")
    reach = mg.param("arm_reach", 1.0, 0.6, 1.3, label="Arm reach")
    fur_len = mg.param("fur_length", 1.0, 0.4, 2.0, label="Fur length")
    fur = mg.color("zombie_fur", "#627258", rough=0.85, material="fur")
    pale = mg.color("pale_fur", "#dcd6c0", rough=0.85, material="fur")
    dark = mg.color("dark_fur", "#434d3b", rough=0.9, material="fur")
    flesh = mg.color("raw_flesh", "#8c3a3c", rough=0.45)
    inner = mg.color("inner_ear", "#b98282", rough=0.6)
    glow = mg.color("eye_glow", "#a4ff3c", rough=0.3, glow=3.0)
    nose = mg.color("nose", "#6b3a44", rough=0.4)
    thread = mg.color("stitch_thread", "#2b2622", rough=0.8, material="fabric")
    collar_c = mg.color("collar_leather", "#6e1f1f", rough=0.55)
    gold = mg.color("bell_brass", "#d4a640", rough=0.3, metal=1.0)
    claw = mg.color("claw_bone", "#ddd4bb", rough=0.5, material="bone")

    # ---- the body: one piece of clay, arms reaching forward like a zombie
    shapes = [
        {"ellipsoid": (0, 0.02, 0.37), "size": (0.175, 0.14, 0.12)},          # hips
        {"ellipsoid": (0, 0.0, 0.5), "size": (0.155, 0.125, 0.16)},            # belly
        {"ball": (0, -0.005, 0.61), "r": 0.13},                                # chest
        {"ball": (0, 0.0, 0.69), "r": 0.085},                                  # neck
        {"ellipsoid": (0, -0.02, 0.8), "size": (0.19, 0.16, 0.155)},           # head
        {"ball": (-0.1, -0.09, 0.755), "r": 0.07}, {"ball": (0.1, -0.09, 0.755), "r": 0.07},   # cheek fluff
        {"ball": (-0.036, -0.165, 0.757), "r": 0.043}, {"ball": (0.036, -0.165, 0.757), "r": 0.043},  # muzzle
        {"ball": (0, -0.14, 0.715), "r": 0.038},                               # chin
        {"ball": (-0.068, -0.155, 0.825), "r": 0.048, "cut": True},            # eye sockets
        {"ball": (0.068, -0.155, 0.825), "r": 0.048, "cut": True},
    ]
    for sx in (-1, 1):
        shapes += [
            {"capsule": ((sx * 0.115, 0.02, 0.33), (sx * 0.12, 0.0, 0.09)), "r": 0.066},      # legs
            {"ellipsoid": (sx * 0.12, -0.04, 0.045), "size": (0.075, 0.12, 0.048)},           # feet
            {"capsule": ((sx * 0.14, -0.01, 0.63), (sx * 0.165, -0.19 * reach, 0.6)), "r": 0.05},     # upper arms
            {"capsule": ((sx * 0.165, -0.19 * reach, 0.6), (sx * 0.15, -0.35 * reach, 0.615)), "r": 0.042},  # forearms
            {"ellipsoid": (sx * 0.15, -0.39 * reach, 0.61), "size": (0.05, 0.06, 0.038)},             # paws
        ]
    body = mg.blob(shapes, fur, blend=0.9)
    mg.focus((0, -0.12, 0.8), 0.13)                  # the face is where players look: more polygons there
    for sx in (-1, 1):
        mg.focus((sx * 0.15, -0.39 * reach, 0.61), 0.06)   # and the reaching paws

    # ---- painted like a real coat: pale muzzle, chest and belly, darker back, a raw wound on the flank
    mg.paint(body, pale, at=(0, -0.17, 0.745), radius=0.075, rough=0.4, seed=1)
    mg.paint(body, pale, at=(0, -0.13, 0.52), radius=0.19, facing=(0, -1, 0), rough=0.6, seed=2)
    mg.paint(body, pale, at=(0, -0.04, 0.02), radius=0.2, below=0.06, rough=0.3, seed=3)   # socks
    mg.paint(body, dark, at=(0, 0.13, 0.62), radius=0.2, facing=(0, 1, 0.3), rough=0.5, seed=4)
    for i, z in enumerate((0.44, 0.52, 0.6)):   # tabby stripes over the back
        mg.paint(body, dark, at=(0, 0.16, z), radius=0.06, facing=(0, 1, 0), rough=0.3, seed=10 + i)
    mg.paint(body, dark, at=(0, 0.02, 0.94), radius=0.1, facing=(0, 0.3, 1), rough=0.25, seed=5)   # a dark cap
    mg.paint(body, flesh, at=(0.15, 0.03, 0.47), radius=0.045, rough=0.5, seed=6)

    # ---- sculpted detail: a mangy coat, the wound sunk in, a scar across the head, a mouth
    mg.sculpt(body, "noise", amount=0.0035, scale=38)
    mg.sculpt(body, "inflate", at=(0.155, 0.03, 0.47), radius=0.05, amount=-0.012)
    scar = [(-0.13, -0.1, 0.87), (-0.05, -0.12, 0.915), (0.04, -0.1, 0.93), (0.12, -0.06, 0.9)]
    mg.sculpt(body, "crease", path=scar, radius=0.012, amount=0.008)
    mg.sculpt(body, "crease", path=[(0, -0.205, 0.755), (0, -0.2, 0.73)], radius=0.008, amount=0.005)
    mouth = [[(0, -0.2, 0.73), (sx * 0.035, -0.19, 0.722), (sx * 0.06, -0.17, 0.73)] for sx in (-1, 1)]
    for m in mouth:
        mg.sculpt(body, "crease", path=m, radius=0.007, amount=0.004)
        mg.sculpt(body, "pinch", path=m, radius=0.008, strength=0.5)
    # sharp features the clay cannot make: eyelids, a frowning brow, the nose bridge, fingers and toes
    for sx in (-1, 1):
        cx, cz = sx * 0.068, 0.825
        upper = [(cx + 0.052 * math.cos(math.radians(a)), -0.163, cz + 0.047 * math.sin(math.radians(a))) for a in range(20, 170, 25)]
        lower = [(cx + 0.05 * math.cos(math.radians(a)), -0.163, cz + 0.044 * math.sin(math.radians(a))) for a in range(205, 340, 30)]
        mg.sculpt(body, "ridge", path=upper, radius=0.013, amount=0.011)
        mg.sculpt(body, "pinch", path=upper, radius=0.01, strength=0.35)
        mg.sculpt(body, "ridge", path=lower, radius=0.01, amount=0.006)
        brow = [(sx * 0.115, -0.125, 0.885), (sx * 0.07, -0.15, 0.89), (sx * 0.03, -0.165, 0.872)]
        mg.sculpt(body, "ridge", path=brow, radius=0.016, amount=0.01)
        for dx in (-0.025, 0.0, 0.025):   # toes
            toe = [(sx * 0.12 + dx, -0.168, 0.035), (sx * 0.12 + dx, -0.135, 0.07)]
            mg.sculpt(body, "crease", path=toe, radius=0.007, amount=0.006)
            mg.sculpt(body, "pinch", path=toe, radius=0.007, strength=0.5)
        for dx in (-0.017, 0.017):        # fingers
            finger = [(sx * 0.15 + dx, -0.447 * reach, 0.617), (sx * 0.15 + dx, -0.41 * reach, 0.643)]
            mg.sculpt(body, "crease", path=finger, radius=0.006, amount=0.005)
            mg.sculpt(body, "pinch", path=finger, radius=0.006, strength=0.5)
    mg.sculpt(body, "ridge", path=[(0, -0.175, 0.862), (0, -0.2, 0.79)], radius=0.012, amount=0.004)

    # ---- fur by zones, like a real coat: short on the body, a ruff on the chest, cheek fluff, shaggy thighs; the
    # cards take the painted colours under them (pale belly fur, dark back), with dark roots and light tips
    parts = [body,
             mg.fur(body, length=0.018 * fur_len, count=6000, droop=0.72, below=0.72, seed=1),                         # coat
             mg.fur(body, length=0.04 * fur_len, count=1200, droop=0.55, at=(0, -0.1, 0.62), radius=0.09,
                    facing=(0, -1, 0.2), seed=2),                                                             # chest ruff
             mg.fur(body, length=0.016 * fur_len, count=1800, droop=0.6, at=(0, 0.04, 0.86), radius=0.16,
                    facing=(0, 0.6, 0.8), seed=3)]                                                            # head
    for sx in (-1, 1):
        parts += [mg.fur(body, length=0.034 * fur_len, count=500, droop=0.35, at=(sx * 0.11, -0.08, 0.755), radius=0.055,
                         seed=4 + sx),                                                                         # cheeks
                  mg.fur(body, length=0.03 * fur_len, count=900, droop=0.7, at=(sx * 0.12, 0.03, 0.33), radius=0.1,
                         seed=6 + sx)]                                                                         # thighs

    # ---- stitches across the scar and the wound
    def stitches(path, n, length):
        for i in range(n):
            t = (i + 0.5) / n
            k = min(int(t * (len(path) - 1)), len(path) - 2)
            u = t * (len(path) - 1) - k
            a, b = path[k], path[k + 1]
            p = [a[j] + (b[j] - a[j]) * u for j in range(3)]
            d = [b[j] - a[j] for j in range(3)]
            n_ = math.hypot(d[0], d[2]) or 1.0
            across = (-d[2] / n_ * length, 0, d[0] / n_ * length)   # across the seam, in the XZ plane
            parts.append(mg.tube([(p[0] - across[0], p[1] - 0.004, p[2] - across[2]),
                                  (p[0] + across[0], p[1] - 0.004, p[2] + across[2])], 0.0035, thread, sides=5))

    if mg.at_least("mobile-mid"):
        stitches(scar, 7, 0.022)
        stitches([(0.17, -0.005, 0.44), (0.17, 0.06, 0.5)], 4, 0.02)

    # ---- ears: the left one whole, the right one torn
    for sx in (-1, 1):
        ear = mg.part("cone", fur, loc=(sx * 0.105, -0.02, 0.9 + 0.04 * ears), scale=(0.11 * ears, 0.055 * ears, 0.14 * ears),
                      rot=(0.1, sx * 0.22, 0))
        inside = mg.part("cone", inner, loc=(sx * 0.103, -0.042, 0.9 + 0.03 * ears), scale=(0.075 * ears, 0.02 * ears, 0.1 * ears),
                         rot=(0.1, sx * 0.22, 0))
        if sx > 0:
            bite = mg.part("sphere", fur, loc=(0.145, -0.03, 0.99), scale=(0.06, 0.12, 0.05))
            mg.cut(ear, bite)
            bite2 = mg.part("sphere", fur, loc=(0.145, -0.05, 0.99), scale=(0.06, 0.12, 0.05))
            mg.cut(inside, bite2)
        parts += [ear, inside]

    # ---- glowing eyes (iris rings, a slit pupil set in, a glossy ball), a nose
    for sx in (-1, 1):
        parts.append(mg.eye((sx * 0.068, -0.142, 0.825), eye_r, glow, look=(sx * 0.18, -1, 0.04), pupil="slit",
                            pupil_size=0.32))
    parts.append(mg.part("sphere", nose, loc=(0, -0.207, 0.772), scale=(0.036, 0.022, 0.024)))

    # ---- collar with a brass bell
    parts.append(mg.part("torus", collar_c, loc=(0, -0.01, 0.705), scale=(0.122, 0.118, 0.122), rot=(0.18, 0, 0),
                         major_radius=1.0, minor_radius=0.16))
    bell = mg.part("sphere", gold, loc=(0, -0.15, 0.665), scale=(0.055, 0.055, 0.055))
    slot = mg.part("cube", gold, loc=(0, -0.18, 0.655), scale=(0.038, 0.03, 0.007))
    mg.cut(bell, slot)
    parts.append(bell)

    # ---- tail, broken halfway
    tail = mg.skin([(0, 0.12, 0.36), (0, 0.24, 0.3), (0.03, 0.34, 0.36), (0.1, 0.36, 0.5), (0.16, 0.33, 0.56)],
                   [0.045, 0.04, 0.034, 0.028, 0.02], fur)
    mg.paint(tail, dark, at=(0.13, 0.35, 0.53), radius=0.06)
    parts += [tail, mg.fur(tail, length=0.03 * fur_len, count=1500, droop=0.45, seed=9)]   # a fluffy tail

    # ---- whiskers and claws on the richer tiers
    if mg.at_least("mobile-high"):
        for sx in (-1, 1):
            for dz, dy in ((0.012, -0.01), (0.0, 0.0), (-0.012, 0.012)):
                parts.append(mg.tube([(sx * 0.06, -0.19, 0.752 + dz), (sx * 0.2, -0.17 + dy, 0.765 + dz * 3)],
                                     0.0018, pale, sides=4))
            for cx in (-0.025, 0.0, 0.025):
                parts.append(mg.part("cone", claw, loc=(sx * 0.15 + cx, -0.445 * reach, 0.605), scale=(0.012, 0.012, 0.03),
                                     rot=(math.pi / 2, 0, 0)))

    body = mg.join("zc_zombie_cat", parts)

    # ---- a skeleton for the engines (Humanoid bone names) and zombie clips
    mg.rig(body, {"hips": (0, 0.02, 0.37), "spine": (0, 0.0, 0.47), "chest": (0, -0.005, 0.6), "neck": (0, 0.0, 0.69),
                  "head": (0, -0.02, 0.74), "head_top": (0, -0.02, 0.95),
                  "shoulder_l": (0.14, -0.01, 0.63), "elbow_l": (0.165, -0.19 * reach, 0.6), "hand_l": (0.15, -0.35 * reach, 0.615),
                  "fingers_l": (0.15, -0.44 * reach, 0.61), "hip_l": (0.115, 0.02, 0.33), "knee_l": (0.118, 0.005, 0.2),
                  "ankle_l": (0.12, 0.0, 0.075), "toe_l": (0.12, -0.12, 0.035)},
           tail=[(0, 0.12, 0.36), (0, 0.24, 0.3), (0.03, 0.34, 0.36), (0.1, 0.36, 0.5), (0.16, 0.33, 0.56)])
    mg.clip("idle", "idle")
    mg.clip("walk", "zombie_walk")
    mg.clip("attack", "attack")
