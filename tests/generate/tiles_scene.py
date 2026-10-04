"""build(mg) for the tiling check: a small yard — grass ground, a brick cottage with a shingle roof and wooden window
frames joined to its walls, a cobble path, a plank deck and an instanced fence. Big surfaces take tiling materials."""


def build(mg):
    ground = mg.tile("ground", "ground", "#4d7336", rgb2="#6b5436", size=4.0)
    brick = mg.tile("brick", "bricks", "#9c4a32", rgb2="#b8b0a0", size=1.0)
    roof = mg.tile("roof", "shingles", "#6b3a2e", size=1.5)
    path = mg.tile("path", "cobble", "#8a877f", size=1.2)
    deck = mg.tile("deck", "planks", "#8a6440", size=1.0)
    wood = mg.color("frame_wood", "#5a3d26", material="wood")
    glass = mg.color("glass_dark", "#1d2630", rough=0.1)
    yard = mg.part("plane", ground, scale=(14, 14, 1))
    walls = mg.part("cube", brick, loc=(0, 1.5, 1.4), scale=(5, 4, 2.8))
    frames = [mg.part("cube", wood, loc=(x, -0.52, 1.5), scale=(0.9, 0.1, 1.1)) for x in (-1.4, 1.4)]
    panes = [mg.part("cube", glass, loc=(x, -0.56, 1.5), scale=(0.7, 0.05, 0.9)) for x in (-1.4, 1.4)]
    door = mg.part("cube", wood, loc=(0, -0.52, 1.0), scale=(1.0, 0.1, 2.0))
    house = mg.join("house", [walls, *frames, *panes, door])
    mg.extrude([(-2.8, 0), (2.8, 0), (0, 1.8)], 4.6, roof, loc=(0, 1.5, 2.8))
    mg.part("cube", path, loc=(0, -3.8, 0.02), scale=(1.4, 6, 0.04))
    mg.part("cube", deck, loc=(4.2, 0.5, 0.1), scale=(2.4, 3.0, 0.2))
    post = mg.part("cube", wood, loc=(0, 0, 0.5), scale=(0.12, 0.12, 1.0))
    for i in range(12):
        mg.instance(post, at=(-6.5 + i * 1.2, -6.5, 0.5))
