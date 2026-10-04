"""build(mg) for the facts check: a table with a floating cup (a mistake the facts must report) and a focus region."""


def build(mg):
    wood = mg.color("wood", "#8a5a2b", rough=0.7)
    white = mg.color("cup_white", "#eeeeee", rough=0.3)
    top = mg.part("cube", wood, loc=(0, 0, 0.72), scale=(1.0, 0.6, 0.04), bevel=0.01)
    legs = [mg.part("cube", wood, loc=(sx * 0.45, sy * 0.25, 0.35), scale=(0.05, 0.05, 0.7)) for sx in (-1, 1) for sy in (-1, 1)]
    cup = mg.part("cyl", white, loc=(0.2, 0.0, 0.85), scale=(0.08, 0.08, 0.1))    # floats 5 cm above the table top
    ball = mg.blob([{"ball": (-0.25, 0, 0.82), "r": 0.08}], white)                 # rests on the top
    mg.focus((-0.25, 0, 0.82), 0.1)
    mg.join("table", [top, *legs, cup, ball])
