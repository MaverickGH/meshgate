"""Dead leafless tree ~2.5m: gnarled trunk, bare crooked branches, broken roots, red yarn ball on a string."""
import math


def build(mg):
    mg.color("bark", "#3a2a1f", rough=0.85)
    mg.color("bark_d", "#2a1c13", rough=0.9)
    mg.color("wood", "#5a4030", rough=0.8)
    mg.color("yarn", "#b02832", rough=0.8)
    mg.color("string", "#c04048", rough=0.9)

    parts = []
    # ---- gnarled trunk (surface of revolution, tapered, slight lean) ----
    prof = [(0.16, 0.0), (0.17, 0.15), (0.15, 0.4), (0.14, 0.8),
            (0.125, 1.3), (0.11, 1.8), (0.095, 2.15), (0.06, 2.4), (0.0, 2.5)]
    trunk = mg.lathe(prof, "bark", loc=(0, 0, 0), segments=mg.seg(14), smooth=True)
    parts.append(trunk)

    # ---- broken split spike at the top ----
    parts.append(mg.tube([(0.02, 0.02, 2.3), (-0.05, 0.05, 2.85)],
                         0, "bark_d", radii=[0.06, 0.0], sides=6, smooth=True))

    # ---- crooked branches ----
    # long branch to the right (viewer) that holds the yarn
    br_r = mg.tube([(0.08, 0.05, 1.75), (0.35, 0.02, 1.85),
                    (0.62, 0.0, 1.9)], 0, "bark",
                   radii=[0.07, 0.045, 0.02], sides=mg.seg(8), smooth=True)
    parts.append(br_r)
    # branch to the left, lower
    parts.append(mg.tube([(-0.09, 0.04, 1.25), (-0.35, 0.06, 1.28),
                          (-0.55, 0.05, 1.22)], 0, "bark",
                         radii=[0.065, 0.04, 0.018], sides=mg.seg(8), smooth=True))
    # short stub branch
    parts.append(mg.tube([(-0.08, 0.02, 1.35), (-0.22, -0.02, 1.55)],
                         0, "bark", radii=[0.05, 0.015], sides=mg.seg(8), smooth=True))

    if mg.at_least("mobile-mid"):
        # a couple of small twigs on the long branch
        parts.append(mg.tube([(0.45, 0.0, 1.87), (0.55, 0.02, 2.02)],
                             0, "bark_d", radii=[0.02, 0.008], sides=6, smooth=True))
        parts.append(mg.tube([(0.25, 0.03, 1.83), (0.33, 0.08, 1.98)],
                             0, "bark_d", radii=[0.022, 0.008], sides=6, smooth=True))

    # ---- broken roots at the base (angular splinters) ----
    roots = [(-0.22, 0.1, 0.35, -0.6), (0.24, -0.05, 0.32, 0.5),
             (0.05, 0.22, 0.3, 0.0), (-0.06, -0.2, 0.28, 0.2)]
    for x, y, h, tilt in roots:
        parts.append(mg.part("cone", "bark_d",
                             loc=(x, y, h / 2), scale=(0.12, 0.1, h),
                             rot=(y * 1.2, -x * 1.2 + tilt, 0),
                             taper=0.15, vertices=5, bevel=0.005))

    tree = mg.join("zc_dead_tree", parts)

    # ---- hanging string + red yarn ball (from tip of right branch) ----
    tip = (0.62, 0.0, 1.9)
    ball_z = 1.32
    hang = []
    hang.append(mg.tube([(tip[0], tip[1], tip[2]),
                         (tip[0], tip[1], ball_z + 0.11)],
                        0.008, "string", sides=6, smooth=True))
    hang.append(mg.part("sphere", "yarn", loc=(tip[0], tip[1], ball_z),
                        scale=(0.24, 0.24, 0.24), segments=mg.seg(16)))
    if mg.at_least("mobile-high"):
        # wound yarn strands wrapping the ball
        for i in range(6):
            a = i * math.pi / 6
            hang.append(mg.tube(
                [(tip[0] - 0.12 * math.cos(a), tip[1] - 0.12 * math.sin(a), ball_z),
                 (tip[0] + 0.12 * math.cos(a), tip[1] + 0.12 * math.sin(a), ball_z + 0.02)],
                0.012, "string", sides=6, smooth=True))
    yarn = mg.join("zc_dead_tree_yarn", hang)
    mg.attach(yarn, tree)
    # gentle sway of the yarn ball
    mg.pivot(yarn, tip)
    mg.animate(yarn, "sway",
               [(0, (0, 0, 0)), (45, (0.12, 0, 0)), (90, (0, 0, 0)),
                (135, (-0.12, 0, 0)), (180, (0, 0, 0))])
