"""Zombie cat character standing upright on two legs like a person, about 1 m tall, after the Zombie Cats concept art
(docs/img/zc-concept-target.jpg): a big round head with big pink-lined ears, green eyes, a white muzzle and belly,
white paws, a red collar with a brass bell, grey-green fur, the tail curling up behind. Sculpted with the kit's clay
(one blob body) and painted in regions. Realistic: a short, soft plush coat of fur cards by zone, taking the painted colours."""
import math


def build(mg):
    # sliders the artist can tune in Studio without asking the AI again
    ears = mg.param("ear_size", 1.25, 0.7, 1.7, label="Ear size")
    eye_r = mg.param("eye_size", 0.042, 0.03, 0.055, label="Eye size")
    head_k = mg.param("head_size", 1.0, 0.8, 1.25, label="Head size")
    fur_len = mg.param("fur_length", 1.0, 0.4, 2.0, label="Fur length")
    fur = mg.color("cat_fur", "#6f7c61", rough=0.85, material="fur")
    pale = mg.color("pale_fur", "#ece6d8", rough=0.85, material="fur")
    dark = mg.color("dark_fur", "#5f6a52", rough=0.9, material="fur")
    inner = mg.color("inner_ear", "#e8a0a8", rough=0.6)
    iris = mg.color("eye_green", "#6fb536", rough=0.3)
    nose = mg.color("nose_pink", "#d77f8a", rough=0.4)
    thread = mg.color("stitch_thread", "#3a332c", rough=0.8, material="fabric")
    collar_c = mg.color("collar_red", "#a02a2a", rough=0.55)
    gold = mg.color("bell_brass", "#d9ae45", rough=0.3, metal=1.0)

    hz = 0.8   # head centre height
    # ---- the body: one piece of clay — a big round head, a pear body, short legs, arms hanging at the sides
    shapes = [
        {"ellipsoid": (0, 0.02, 0.33), "size": (0.17, 0.14, 0.12)},                     # hips
        {"ellipsoid": (0, 0.0, 0.46), "size": (0.155, 0.13, 0.15)},                      # belly
        {"ball": (0, 0.0, 0.58), "r": 0.12},                                             # chest
        {"ball": (0, 0.0, 0.66), "r": 0.09},                                             # neck
        {"ellipsoid": (0, -0.01, hz), "size": (0.2 * head_k, 0.175 * head_k, 0.17 * head_k)},   # head
        {"ball": (-0.1, -0.1, hz - 0.05), "r": 0.075}, {"ball": (0.1, -0.1, hz - 0.05), "r": 0.075},   # cheeks
        {"ball": (-0.038, -0.172, hz - 0.045), "r": 0.045}, {"ball": (0.038, -0.172, hz - 0.045), "r": 0.045},  # muzzle
        {"ball": (0, -0.15, hz - 0.085), "r": 0.036},                                    # chin
    ]
    for sx in (-1, 1):
        shapes += [
            {"capsule": ((sx * 0.1, 0.02, 0.3), (sx * 0.105, 0.0, 0.08)), "r": 0.07},     # legs
            {"ellipsoid": (sx * 0.105, -0.04, 0.042), "size": (0.078, 0.11, 0.045)},      # feet
            {"capsule": ((sx * 0.135, 0.0, 0.6), (sx * 0.175, -0.02, 0.45)), "r": 0.05},  # upper arms
            {"capsule": ((sx * 0.175, -0.02, 0.45), (sx * 0.18, -0.03, 0.37)), "r": 0.044},   # forearms
            {"ball": (sx * 0.18, -0.035, 0.34), "r": 0.052},                                # paws
        ]
    body = mg.blob(shapes, fur, blend=0.9)
    mg.focus((0, -0.12, hz), 0.14)   # the face is where players look: more polygons there
    mg.focus((0, -0.14, 0.47), 0.13)  # and a clean edge round the white belly

    # ---- painted like the concept: white muzzle, an oval belly, white paws and feet, a darker back
    mg.paint(body, pale, at=(0, -0.18, hz - 0.06), radius=0.075, rough=0.1, seed=1)
    mg.paint(body, pale, at=(0, -0.14, 0.47), radius=0.12, facing=(0, -1, 0), rough=0.0, seed=2)   # a clean oval
    mg.paint(body, pale, at=(0, -0.04, 0.02), radius=0.2, below=0.075, rough=0.2, seed=3)   # feet
    for sx in (-1, 1):
        mg.paint(body, pale, at=(sx * 0.18, -0.035, 0.34), radius=0.06, rough=0.0, seed=7 + sx)   # paws
    mg.paint(body, dark, at=(0, 0.13, 0.6), radius=0.2, facing=(0, 1, 0.3), rough=0.4, seed=4)

    # ---- a few sculpted features: a mouth, the nose bridge, eyelids, toes
    mouth = [[(0, -0.215, hz - 0.07), (sx * 0.035, -0.205, hz - 0.078), (sx * 0.06, -0.185, hz - 0.07)] for sx in (-1, 1)]
    for m in mouth:
        mg.sculpt(body, "crease", path=m, radius=0.007, amount=0.004)
    for sx in (-1, 1):
        cx, cz = sx * 0.07, hz + 0.03
        upper = [(cx + 0.05 * math.cos(math.radians(a)), -0.17, cz + 0.045 * math.sin(math.radians(a))) for a in range(20, 170, 25)]
        mg.sculpt(body, "ridge", path=upper, radius=0.012, amount=0.008)
        for dx in (-0.025, 0.0, 0.025):   # toes
            toe = [(sx * 0.105 + dx, -0.15, 0.03), (sx * 0.105 + dx, -0.12, 0.065)]
            mg.sculpt(body, "crease", path=toe, radius=0.007, amount=0.005)

    mg.sculpt(body, "noise", amount=0.002, scale=38)   # a soft coat surface under the fur
    # ---- fur by zones: a short plush coat, a slightly longer chest ruff and cheek tufts; the cards take the painted
    # colours under them (white belly and paws, darker back)
    parts = [body,
             mg.fur(body, length=0.012 * fur_len, count=5000, droop=0.75, below=hz + 0.1, seed=1),                    # coat
             mg.fur(body, length=0.022 * fur_len, count=900, droop=0.6, at=(0, -0.1, 0.6), radius=0.09,
                    facing=(0, -1, 0.2), seed=2),                                                             # chest ruff
             mg.fur(body, length=0.01 * fur_len, count=1500, droop=0.6, at=(0, 0.02, hz + 0.06), radius=0.17,
                    facing=(0, 0.4, 0.9), seed=3)]                                                            # head
    for sx in (-1, 1):
        parts.append(mg.fur(body, length=0.022 * fur_len, count=350, droop=0.35, at=(sx * 0.12, -0.08, hz - 0.05),
                            radius=0.05, seed=4 + sx))                                                         # cheeks

    # ---- big ears with pink insides
    for sx in (-1, 1):
        ear = mg.part("cone", fur, loc=(sx * 0.12, -0.01, hz + 0.13 + 0.04 * ears), scale=(0.13 * ears, 0.06 * ears, 0.17 * ears),
                      rot=(0.08, sx * 0.3, 0))
        inside = mg.part("cone", inner, loc=(sx * 0.118, -0.036, hz + 0.12 + 0.035 * ears), scale=(0.09 * ears, 0.02 * ears, 0.12 * ears),
                         rot=(0.08, sx * 0.3, 0))
        parts += [ear, inside]

    # ---- green eyes with a slit pupil (a soft glow, not a lamp), a pink nose
    for sx in (-1, 1):
        parts.append(mg.eye((sx * 0.07, -0.15, hz + 0.03), eye_r, iris, look=(sx * 0.1, -1, 0.0), pupil="round",
                            pupil_size=0.42))
    parts.append(mg.part("sphere", nose, loc=(0, -0.222, hz - 0.03), scale=(0.034, 0.02, 0.022)))

    # ---- collar with a brass bell
    parts.append(mg.part("torus", collar_c, loc=(0, -0.01, 0.668), scale=(0.132, 0.128, 0.132), rot=(0.18, 0, 0),
                         major_radius=1.0, minor_radius=0.2))
    bell = mg.part("sphere", gold, loc=(0, -0.138, 0.638), scale=(0.05, 0.05, 0.05))
    slot = mg.part("cube", gold, loc=(0, -0.165, 0.628), scale=(0.034, 0.03, 0.006))
    mg.cut(bell, slot)
    parts.append(bell)

    # ---- tail curling up behind
    tail = mg.skin([(0, 0.12, 0.32), (0.02, 0.24, 0.3), (0.06, 0.33, 0.38), (0.1, 0.36, 0.52), (0.12, 0.33, 0.62)],
                   [0.045, 0.04, 0.036, 0.03, 0.022], fur)
    mg.paint(tail, dark, at=(0.11, 0.35, 0.58), radius=0.07)
    parts += [tail, mg.fur(tail, length=0.02 * fur_len, count=900, droop=0.45, seed=9)]

    # ---- whiskers
    if mg.at_least("mobile-mid"):
        for sx in (-1, 1):
            for dz, dy in ((0.014, -0.01), (0.0, 0.0), (-0.014, 0.012)):
                parts.append(mg.tube([(sx * 0.06, -0.2, hz - 0.05 + dz), (sx * 0.24, -0.18 + dy, hz - 0.035 + dz * 3)],
                                     0.0018, pale, sides=4))

    body = mg.join("zc_zombie_cat", parts)

    # ---- a skeleton for the engines (Humanoid bone names) and zombie clips
    mg.rig(body, {"hips": (0, 0.02, 0.33), "spine": (0, 0.0, 0.44), "chest": (0, 0.0, 0.57), "neck": (0, 0.0, 0.66),
                  "head": (0, -0.01, 0.7), "head_top": (0, -0.01, 0.98),
                  "shoulder_l": (0.135, 0.0, 0.6), "elbow_l": (0.175, -0.02, 0.45), "hand_l": (0.18, -0.03, 0.37),
                  "fingers_l": (0.18, -0.035, 0.3), "hip_l": (0.1, 0.02, 0.3), "knee_l": (0.103, 0.01, 0.18),
                  "ankle_l": (0.105, 0.0, 0.07), "toe_l": (0.105, -0.12, 0.03)},
           tail=[(0, 0.12, 0.32), (0.02, 0.24, 0.3), (0.06, 0.33, 0.38), (0.1, 0.36, 0.52), (0.12, 0.33, 0.62)])
    mg.clip("idle", "idle")
    mg.clip("shamble", "zombie_walk")
