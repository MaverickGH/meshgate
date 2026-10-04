"""zc_dead_tree, low-poly — the same dead tree with few, flat facets: a straight trunk to one sharp point, thorny
branches, buttress roots and a red yarn ball on a string."""
import math


def build(mg):
    wood = mg.color("bark", "#5a3423", rough=0.9, material="wood")
    wood_d = mg.color("bark_dark", "#3e2418", rough=0.9, material="wood")
    yarn = mg.color("yarn", "#e21c1c", rough=0.6)
    rope = mg.color("string", "#c41616", rough=0.9)
    sides = 5 if mg.at_least("mobile-mid") else 4
    twig_sides, smooth, nroots = 4, False, 4

    parts = []

    # --- trunk: a straight tapering column rising to one sharp point ---
    trunk_pts = [(0.0, 0.0, 0.0), (0.01, 0.0, 0.5), (-0.01, 0.0, 1.0), (0.01, 0.0, 1.5),
                 (0.0, 0.0, 1.95), (0.0, 0.0, 2.3), (0.0, 0.0, 2.6)]
    trunk_r = [0.3, 0.24, 0.2, 0.16, 0.11, 0.05, 0.0]
    parts.append(mg.tube(trunk_pts, 0.0, wood, radii=trunk_r, sides=sides, smooth=smooth, cap=True))

    def branch(points, radii, color=None):
        parts.append(mg.tube(points, 0.0, color or wood, radii=radii, sides=twig_sides, smooth=smooth))

    # --- the long branch to the viewer's right (+X), rising a little: the yarn ball hangs from it ---
    branch([(0.08, 0.0, 1.55), (0.38, 0.0, 1.7), (0.68, 0.0, 1.8), (1.0, 0.0, 1.9)], [0.09, 0.06, 0.035, 0.0])
    branch([(0.4, 0.0, 1.7), (0.46, 0.0, 1.9), (0.5, 0.0, 2.06)], [0.045, 0.028, 0.0])   # two thorns up
    branch([(0.62, 0.0, 1.78), (0.68, 0.0, 1.93), (0.71, 0.0, 2.02)], [0.035, 0.02, 0.0])
    # --- the shorter branch to the left, with a thorn up, and a thorn off the trunk higher up ---
    branch([(-0.08, 0.0, 1.25), (-0.32, 0.0, 1.32), (-0.58, 0.0, 1.4)], [0.08, 0.045, 0.0])
    branch([(-0.3, 0.0, 1.31), (-0.34, 0.0, 1.47), (-0.36, 0.0, 1.6)], [0.035, 0.02, 0.0])
    branch([(-0.04, 0.0, 1.95), (-0.2, 0.0, 2.06), (-0.34, 0.0, 2.14)], [0.04, 0.022, 0.0])
    if mg.at_least("mobile-mid"):
        branch([(0.05, 0.0, 0.95), (0.18, 0.02, 1.02), (0.28, 0.03, 1.06)], [0.035, 0.02, 0.0])   # a stub
        branch([(0.0, 0.05, 1.7), (0.02, 0.2, 1.8), (0.03, 0.32, 1.86)], [0.035, 0.02, 0.0])       # one to the back

    # --- roots: short thick buttresses flaring into the ground ---
    for i in range(nroots):
        a = (i / nroots) * math.tau + 0.35
        dx, dy = math.cos(a), math.sin(a)
        reach = 0.44 + 0.08 * mg.rng.random()
        parts.append(mg.tube([(dx * 0.1, dy * 0.1, 0.42), (dx * 0.26, dy * 0.26, 0.14), (dx * reach, dy * reach, 0.0)],
                             0.0, wood_d, radii=[0.13, 0.085, 0.0], sides=twig_sides, smooth=smooth))
    tree = mg.join("zc_dead_tree", parts)

    hang_x = 0.8
    string = mg.tube([(hang_x, 0.0, 1.83), (hang_x, 0.0, 1.2)], 0.01, rope, sides=4, smooth=False)
    ball = mg.part("ico", yarn, loc=(hang_x, 0.0, 1.07), scale=(0.26, 0.26, 0.26), subdiv=0, smooth=False)
    yarn_ball = mg.join("yarn", [string, ball])
    mg.pivot(yarn_ball, (hang_x, 0.0, 1.83))
    mg.attach(yarn_ball, tree)
    mg.animate(yarn_ball, "yarn_swing", [(0, (0, 0, 0)), (45, (0.1, 0, 0.06)), (90, (0, 0, 0)), (135, (-0.1, 0, -0.06)),
                                         (180, (0, 0, 0))])
