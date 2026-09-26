"""zc_dead_tree — a gnarled dead leafless tree with broken roots and a red yarn ball hanging on a string."""
import math


def build(mg):
    wood = mg.color("wood", "#8a5a2b", rough=0.85)
    wood_d = mg.color("wood_dark", "#5f3c1d", rough=0.9)
    yarn = mg.color("fabric_red", "#e21c1c", rough=0.85)
    rope = mg.color("rope_red", "#d81818", rough=0.9)

    parts = []
    sides = 6 if mg.at_least("mobile-mid") else 5

    # --- trunk: gnarled tapered column rising to a jagged point ---
    trunk_pts = [(0.0, 0.0, 0.0), (0.03, 0.02, 0.45), (-0.04, 0.0, 0.95),
                 (0.03, 0.03, 1.45), (-0.02, 0.0, 1.85), (0.03, 0.02, 2.2),
                 (0.0, 0.0, 2.46)]
    trunk_r = [0.29, 0.25, 0.21, 0.16, 0.11, 0.06, 0.0]
    parts.append(mg.tube(trunk_pts, 0.0, wood, radii=trunk_r, sides=sides,
                         smooth=False, cap=True))

    # --- main branch to viewer's right (+X), nearly horizontal, up-tilted ---
    parts.append(mg.tube([(0.1, 0.0, 1.5), (0.4, 0.0, 1.66), (0.72, 0.02, 1.74),
                          (0.98, 0.0, 1.82)], 0.0,
                         wood, radii=[0.1, 0.07, 0.045, 0.0], sides=sides, smooth=False))
    # two little crooked spikes off the main branch
    parts.append(mg.tube([(0.42, 0.0, 1.66), (0.47, 0.0, 1.85), (0.5, 0.0, 2.02)], 0.0,
                         wood, radii=[0.05, 0.03, 0.0], sides=sides, smooth=False))
    parts.append(mg.tube([(0.55, 0.0, 1.69), (0.6, 0.0, 1.85), (0.64, 0.0, 1.98)], 0.0,
                         wood, radii=[0.045, 0.028, 0.0], sides=sides, smooth=False))

    # --- lower-left branch (-X) with an upward spike ---
    parts.append(mg.tube([(-0.1, 0.0, 1.2), (-0.34, -0.01, 1.25), (-0.55, -0.03, 1.27)], 0.0,
                         wood, radii=[0.09, 0.05, 0.0], sides=sides, smooth=False))
    parts.append(mg.tube([(-0.28, 0.0, 1.24), (-0.31, 0.0, 1.4), (-0.33, 0.0, 1.56)], 0.0,
                         wood, radii=[0.045, 0.028, 0.0], sides=sides, smooth=False))

    # --- broken roots flaring out at the base ---
    nroots = 7 if mg.at_least("mobile-mid") else 5
    for i in range(nroots):
        a = (i / nroots) * math.tau + 0.3
        dx, dy = math.cos(a), math.sin(a)
        reach = 0.42 + 0.12 * mg.rng.random()
        parts.append(mg.tube([(dx * 0.12, dy * 0.12, 0.32),
                              (dx * 0.28, dy * 0.24, 0.14),
                              (dx * reach, dy * reach * 0.85, 0.02)], 0.0,
                             wood_d, radii=[0.11, 0.07, 0.0], sides=sides, smooth=False))

    tree = mg.join("zc_dead_tree", parts)

    # --- red yarn ball hanging on a string from the main branch ---
    hang_x = 0.78
    string = mg.tube([(hang_x, 0.0, 1.77), (hang_x, 0.0, 1.12)], 0.012, rope,
                     sides=6, smooth=True)
    ball = mg.part("ico", yarn, loc=(hang_x, 0.0, 0.98), scale=(0.24, 0.24, 0.24),
                   subdiv=1 if mg.at_least("mobile-high") else 0)
    mg.join("yarn", [string, ball])
