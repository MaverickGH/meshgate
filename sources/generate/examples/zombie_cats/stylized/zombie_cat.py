"""Zombie cat character standing upright on two legs like a person, about 1 m tall, after the Zombie Cats concept art
(docs/img/zc-concept-target.jpg): built like a vinyl toy figure out of soft-edged blocks — a boxy body with a flat
front, a wide head sitting right on the shoulders, straight arms against the sides, short thick legs, big pink-lined
ears, green eyes under a frowning brow, a white muzzle, belly, paws and feet, a thin red collar with a brass bell,
grey-green fur, the tail curling up behind. Stylized: smooth rounded blocks, a clean coat (no coat noise, no fur cards)."""


def build(mg):
    # sliders the artist can tune in Studio without asking the AI again
    ears = mg.param("ear_size", 1.0, 0.7, 1.4, label="Ear size")
    eye_r = mg.param("eye_size", 0.038, 0.028, 0.05, label="Eye size")
    head_k = mg.param("head_size", 1.0, 0.85, 1.2, label="Head size")
    fur = mg.color("cat_fur", "#5f6c52", rough=0.85, material="fur")
    pale = mg.color("pale_fur", "#ece6d8", rough=0.85, material="fur")
    dark = mg.color("dark_fur", "#56614a", rough=0.9, material="fur")
    inner = mg.color("inner_ear", "#e8a0a8", rough=0.6)
    iris = mg.color("eye_green", "#6fb536", rough=0.3)
    nose = mg.color("nose_pink", "#d77f8a", rough=0.4)
    collar_c = mg.color("collar_red", "#a02a2a", rough=0.55)
    gold = mg.color("bell_brass", "#d9ae45", rough=0.3, metal=1.0)
    ball = {}   # sphere segments (the low-poly version asks for fewer)

    # ---- the body the way a toy designer blocks one: boxes with soft edges (a bevel, smoothed), not balls. The arms
    # join the body at round shoulders with a gap down the sides (so they swing free), the head sits right on the
    # shoulders (no neck). All the blocks melt into one skin below (mg.union), with a rounded blend at every seam, so
    # the cat bends as one body instead of coming apart
    hz = 0.79   # head centre height
    torso = mg.part("cube", fur, loc=(0, 0.0, 0.44), scale=(0.35, 0.25, 0.36), bevel=0.09, subdiv=1, smooth=True)
    mg.paint(torso, dark, at=(0, 0.13, 0.55), radius=0.2, facing=(0, 1, 0.2), rough=0.3, seed=4)   # a darker back
    blocks = [torso]
    socks = []   # white paws and feet: pieces of their own with a crisp colour edge (each holds its bone)
    for sx in (-1, 1):
        socks += [
            mg.part("cube", pale, loc=(sx * 0.088, -0.035, 0.05), scale=(0.16, 0.21, 0.1), bevel=0.045, subdiv=2, smooth=True),  # foot
            mg.part("sphere", pale, loc=(sx * 0.25, -0.01, 0.325), scale=(0.115, 0.115, 0.105), **ball),                       # paw
        ]
        blocks += [
            mg.part("cube", fur, loc=(sx * 0.082, 0.0, 0.16), scale=(0.145, 0.15, 0.24), bevel=0.05, subdiv=1, smooth=True),   # leg
            mg.part("cube", fur, loc=(sx * 0.245, 0.0, 0.46), scale=(0.1, 0.105, 0.28), bevel=0.04, subdiv=1, smooth=True),  # arm
            mg.part("sphere", fur, loc=(sx * 0.205, 0.0, 0.575), scale=(0.13, 0.12, 0.12), **ball),   # shoulder: the arm joins the body here
        ]

    # ---- the head: a wide box with soft edges, a little narrower at the top, cheek tufts at the jaw
    head = mg.part("cube", fur, loc=(0, -0.01, hz), scale=(0.41 * head_k, 0.31 * head_k, 0.37 * head_k), bevel=0.13,
                   subdiv=2, taper=0.9, smooth=True)
    mg.focus((0, -0.12, hz - 0.03), 0.14)   # the face is where players look: more polygons there
    blocks.append(head)
    for sx in (-1, 1):
        blocks.append(mg.part("cone", fur, loc=(sx * 0.2 * head_k, -0.04, hz - 0.1), scale=(0.07, 0.05, 0.1),
                             rot=(0.2, sx * 1.9, 0)))                                                    # cheek tuft
    face_y = -0.01 - 0.155 * head_k   # the front of the face
    parts = [
        mg.part("sphere", pale, loc=(-0.034, face_y, hz - 0.105), scale=(0.085, 0.06, 0.065), **ball),   # muzzle
        mg.part("sphere", pale, loc=(0.034, face_y, hz - 0.105), scale=(0.085, 0.06, 0.065), **ball),
        mg.part("sphere", pale, loc=(0, face_y + 0.01, hz - 0.135), scale=(0.06, 0.05, 0.045), **ball),   # chin
        mg.part("sphere", nose, loc=(0, face_y - 0.03, hz - 0.085), scale=(0.03, 0.018, 0.02), **ball),  # nose
    ]

    # ---- green eyes set into the face under a frowning brow (its inner end low), big ears with pink insides
    for sx in (-1, 1):
        parts.append(mg.eye((sx * 0.085, face_y + 0.025, hz - 0.025), eye_r, iris, look=(sx * 0.1, -1, 0.0),
                            pupil="round", pupil_size=0.42))
        parts.append(mg.part("cube", fur, loc=(sx * 0.087, face_y + 0.002, hz + 0.014), scale=(0.072, 0.016, 0.014),
                             rot=(0, -sx * 0.2, 0), bevel=0.006, smooth=True))                            # brow
        blocks.append(mg.part("cone", fur, loc=(sx * 0.135, -0.005, hz + 0.14 + 0.07 * ears),
                             scale=(0.17 * ears, 0.06 * ears, 0.2 * ears), rot=(0.05, sx * 0.3, 0)))    # ear
        parts.append(mg.part("cone", inner, loc=(sx * 0.133, -0.032, hz + 0.13 + 0.065 * ears),
                             scale=(0.11 * ears, 0.02 * ears, 0.14 * ears), rot=(0.05, sx * 0.3, 0)))   # its pink inside

    # ---- a thin collar where the head meets the body, with a brass bell
    parts.append(mg.part("torus", collar_c, loc=(0, -0.005, 0.615), scale=(0.18, 0.133, 0.08),
                         major_radius=1.0, minor_radius=0.11))
    bell = mg.part("sphere", gold, loc=(0, -0.145, 0.595), scale=(0.05, 0.05, 0.05), **ball)
    slot = mg.part("cube", gold, loc=(0, -0.172, 0.585), scale=(0.034, 0.03, 0.006))
    mg.cut(bell, slot)
    parts.append(bell)

    # ---- the tail curling up behind
    tail_pts = [(0, 0.11, 0.3), (0.03, 0.22, 0.28), (0.08, 0.3, 0.36), (0.12, 0.32, 0.5), (0.14, 0.28, 0.62)]
    tail = mg.skin(tail_pts, [0.042, 0.038, 0.034, 0.028, 0.02], fur)
    mg.paint(tail, dark, at=tail_pts[-1], radius=0.07)
    blocks.append(tail)

    body_skin = mg.union(blocks, fillet=0.025)   # one skin, rounded where the blocks meet
    parts.append(mg.patch(body_skin, pale, at=(0, -0.125, 0.44), size=(0.21, 0.27), thickness=0.007, dome=0.008))   # the belly, on the body
    parts += [body_skin, *socks]

    # ---- whiskers
    if mg.at_least("mobile-mid"):
        for sx in (-1, 1):
            for dz, dy in ((0.014, -0.01), (0.0, 0.0), (-0.014, 0.012)):
                parts.append(mg.tube([(sx * 0.06, face_y - 0.02, hz - 0.1 + dz), (sx * 0.29, face_y + dy, hz - 0.09 + dz * 3)],
                                     0.0018, pale, sides=4))

    body = mg.join("zc_zombie_cat", parts)

    # ---- a skeleton for the engines (Humanoid bone names) and zombie clips
    mg.rig(body, {"hips": (0, 0.0, 0.3), "spine": (0, 0.0, 0.42), "chest": (0, 0.0, 0.55), "neck": (0, 0.0, 0.61),
                  "head": (0, -0.01, 0.64), "head_top": (0, -0.01, 0.97),
                  "shoulder_l": (0.225, 0.0, 0.58), "elbow_l": (0.245, 0.0, 0.46), "hand_l": (0.25, -0.005, 0.35),
                  "fingers_l": (0.25, -0.01, 0.29), "hip_l": (0.082, 0.0, 0.27), "knee_l": (0.082, 0.0, 0.16),
                  "ankle_l": (0.082, 0.0, 0.065), "toe_l": (0.088, -0.12, 0.03)},
           tail=tail_pts)
    mg.clip("idle", "idle")
    mg.clip("shamble", "zombie_walk")
