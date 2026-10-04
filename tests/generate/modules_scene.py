"""build(mg) for the modular kit check: a 2 m grid set — plain wall, wall with a window, doorway, floor and a corner
post — brick and plank tiles that divide the grid, and one module deliberately 10 cm too wide."""


def build(mg):
    brick = mg.tile("brick", "bricks", "#9c4a32", rgb2="#b8b0a0", size=1.0)
    floor = mg.tile("floor", "planks", "#8a6440", size=1.0)
    wood = mg.color("frame_wood", "#5a3d26", material="wood")
    glass = mg.color("glass_dark", "#1d2630", rough=0.1)
    stone = mg.color("post_stone", "#8a877f", material="stone")
    mg.module("wall", [mg.part("cube", brick, loc=(1, 0, 1.5), scale=(2, 0.2, 3))])
    wall = mg.part("cube", brick, loc=(1, 0, 1.5), scale=(2, 0.2, 3))
    hole = mg.part("cube", brick, loc=(1, 0, 1.6), scale=(0.9, 0.4, 1.0))
    mg.cut(wall, hole)
    frame = mg.part("cube", wood, loc=(1, -0.1, 1.6), scale=(1.0, 0.06, 1.1))
    pane = mg.part("cube", glass, loc=(1, -0.12, 1.6), scale=(0.9, 0.03, 1.0))
    mg.module("wall_window", [wall, frame, pane])
    left = mg.part("cube", brick, loc=(0.3, 0, 1.5), scale=(0.6, 0.2, 3))
    right = mg.part("cube", brick, loc=(1.7, 0, 1.5), scale=(0.6, 0.2, 3))
    lintel = mg.part("cube", brick, loc=(1, 0, 2.6), scale=(0.8, 0.2, 0.8))
    mg.module("doorway", [left, right, lintel])
    mg.module("floor", [mg.part("cube", floor, loc=(1, 1, 0.05), scale=(2, 2, 0.1))], footprint=(1, 1))
    mg.module("post", [mg.part("cube", stone, loc=(0, 0, 1.5), scale=(0.3, 0.3, 3))], footprint=(0, 0))
    mg.module("wall_wide", [mg.part("cube", brick, loc=(1.05, 0, 1.5), scale=(2.1, 0.2, 3))])
