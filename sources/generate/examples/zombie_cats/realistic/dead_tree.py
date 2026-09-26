"""Dead leafless tree ~2.5 m: gnarled trunk, bare crooked branches, broken roots, red yarn ball on a string."""
import math


def build(mg):
    bark = mg.color("bark", "#2f231a", rough=0.9)
    bark2 = mg.color("bark2", "#3c2c20", rough=0.9)
    yarn = mg.color("yarn", "#9e2b2b", rough=0.85)
    string = mg.color("string", "#a83a3a", rough=0.9)

    parts = []

    # --- gnarled trunk (slightly crooked, tapering, broken top) ---
    trunk_pts = [(0.00, 0.00, 0.00), (0.02, 0.01, 0.45), (-0.02, 0.00, 0.95),
                 (0.02, -0.01, 1.45), (-0.01, 0.01, 1.95), (0.02, 0.00, 2.30)]
    trunk_r = [0.17, 0.155, 0.135, 0.115, 0.095, 0.05]
    parts.append(mg.tube(trunk_pts, 0, bark, radii=trunk_r, sides=12))

    # broken top spike
    parts.append(mg.tube([(-0.01, 0.01, 1.95), (0.00, -0.03, 2.25), (0.03, -0.06, 2.47)],
                         0, bark2, radii=[0.06, 0.03, 0.005], sides=8))

    # --- crooked branches ---
    # upper right branch (holds the yarn) - viewer's right = +X
    br_yarn = [(0.05, 0.00, 1.80), (0.35, 0.03, 1.92), (0.62, 0.05, 1.96), (0.88, 0.06, 1.99)]
    parts.append(mg.tube(br_yarn, 0, bark2, radii=[0.06, 0.04, 0.025, 0.012], sides=8))

    # lower left branch
    br_l = [(-0.05, 0.00, 1.25), (-0.30, 0.02, 1.30), (-0.55, 0.04, 1.33), (-0.70, 0.05, 1.35)]
    parts.append(mg.tube(br_l, 0, bark2, radii=[0.055, 0.035, 0.02, 0.01], sides=8))
    # small twig off the left branch
    parts.append(mg.tube([(-0.28, 0.02, 1.29), (-0.34, -0.02, 1.10), (-0.38, -0.05, 0.95)],
                         0, bark2, radii=[0.025, 0.014, 0.006], sides=6))

    if mg.at_least("mobile-mid"):
        # extra small twig near top
        parts.append(mg.tube([(0.35, 0.03, 1.92), (0.42, 0.06, 2.10), (0.46, 0.08, 2.25)],
                             0, bark2, radii=[0.02, 0.012, 0.005], sides=6))

    # --- broken roots at the base ---
    root_ang = [0.4, 2.3, 4.1, 5.4]
    for i, a in enumerate(root_ang):
        rr = 0.16
        x, y = math.cos(a) * rr, math.sin(a) * rr
        parts.append(mg.part("cube", bark, loc=(x, y, 0.06),
                             scale=(0.11, 0.09, 0.14), rot=(0.3 * math.cos(a), 0.3 * math.sin(a), a),
                             taper=0.4, bevel=0.01))

    tree = mg.join("dead_tree", parts)

    # --- red ball of yarn on a string (hanging, gentle sway) ---
    hang = (0.62, 0.05, 1.94)
    ball_c = (0.62, 0.05, 1.52)
    yparts = [mg.tube([hang, (ball_c[0], ball_c[1], ball_c[2] + 0.07)], 0.006, string, sides=6)]
    yparts.append(mg.part("sphere", yarn, loc=ball_c, scale=(0.14, 0.14, 0.14)))
    if mg.at_least("mobile-high"):
        # faint wound strands across the ball
        for k in range(5):
            ang = k * 1.05
            yparts.append(mg.part("torus", yarn, loc=ball_c, scale=(0.155, 0.155, 0.155),
                                  rot=(ang, ang * 0.7, 0), minor_radius=0.012))
    yarn_ball = mg.join("yarn_ball", yparts)
    mg.pivot(yarn_ball, hang)
    mg.attach(yarn_ball, tree)
    mg.animate(yarn_ball, "sway",
               [(0, (0, 0, 0)), (45, (0.08, 0, 0.05)), (90, (0, 0, 0)),
                (135, (-0.08, 0, -0.05)), (180, (0, 0, 0))])
