"""zc_dead_tree — dead leafless tree with a red ball of yarn hanging from a branch."""
import math


def build(mg):
    bark = mg.color("bark", "#3a2a20", rough=0.9)
    bark_d = mg.color("bark_dark", "#2a1c14", rough=0.9)
    yarn = mg.color("yarn", "#b02535", rough=0.85)
    string = mg.color("string", "#7a1520", rough=0.9)

    parts = []

    # --- gnarled trunk, base to top, slightly crooked and tapering ---
    trunk_pts = [
        (0.00, 0.00, 0.00),
        (0.03, -0.02, 0.55),
        (-0.02, 0.02, 1.10),
        (0.04, -0.01, 1.65),
        (0.00, 0.03, 2.10),
    ]
    trunk_r = [0.15, 0.135, 0.115, 0.09, 0.06]
    parts.append(mg.tube(trunk_pts, 0, bark, radii=trunk_r, sides=8, smooth=False))

    # jagged broken top splinter
    parts.append(mg.tube([(0.00, 0.03, 2.05), (-0.06, 0.05, 2.45)], 0,
                         bark_d, radii=[0.055, 0.006], sides=6, smooth=False))

    # --- broken roots at the base (chunky wedges) ---
    for ang in (0.4, 2.2, 3.6, 5.1):
        rx, ry = math.cos(ang), math.sin(ang)
        parts.append(mg.part("cube", bark_d,
                             loc=(rx * 0.20, ry * 0.20, 0.06),
                             scale=(0.10, 0.10, 0.13),
                             rot=(mg.rng.uniform(-0.4, 0.4), mg.rng.uniform(-0.4, 0.4), ang),
                             taper=0.3))

    # --- bare crooked branches ---
    # left-pointing branch (viewer's right, +X) around mid trunk
    parts.append(mg.tube([(0.02, 0.0, 1.05), (0.45, 0.05, 1.15), (0.72, 0.02, 1.05)], 0,
                         bark, radii=[0.05, 0.03, 0.012], sides=6, smooth=False))
    # short opposite stub
    parts.append(mg.tube([(-0.02, 0.0, 1.02), (-0.35, -0.03, 0.92)], 0,
                         bark, radii=[0.045, 0.012], sides=6, smooth=False))
    # upper branch that carries the yarn (goes to +X, viewer's right)
    branch_end = (0.85, 0.04, 1.58)
    parts.append(mg.tube([(0.03, 0.0, 1.55), (0.5, 0.06, 1.62), branch_end], 0,
                         bark, radii=[0.05, 0.03, 0.012], sides=6, smooth=False))
    # small upper-left twig
    parts.append(mg.tube([(-0.02, 0.0, 1.60), (-0.28, -0.04, 1.78)], 0,
                         bark, radii=[0.035, 0.008], sides=6, smooth=False))

    # --- string hanging from the branch end ---
    ball_z = 1.05
    hang_x = branch_end[0] - 0.02
    parts.append(mg.tube([(hang_x, branch_end[1], branch_end[2]),
                          (hang_x, branch_end[1], ball_z + 0.09)], 0.006,
                         string, sides=6, smooth=False))

    # --- red ball of yarn ---
    parts.append(mg.part("sphere", yarn, loc=(hang_x, branch_end[1], ball_z),
                         scale=(0.19, 0.19, 0.19)))
    if mg.at_least("mobile-mid"):
        # faint wound-thread ridges hinting at yarn
        for i in range(3):
            parts.append(mg.part("torus", string,
                                 loc=(hang_x, branch_end[1], ball_z),
                                 rot=(mg.rng.uniform(0, 3), mg.rng.uniform(0, 3), 0),
                                 major_radius=0.095, minor_radius=0.006))

    mg.join("zc_dead_tree", parts)
