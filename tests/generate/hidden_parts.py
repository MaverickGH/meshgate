"""build(mg) for the hidden-face check: a 1 m box with a ball wholly inside it (every face hidden) and an arm sunk
halfway in (only its inner cap is hidden; the side faces cross the box's surface and must stay)."""


def build(mg):
    grey = mg.color("grey", "#808080")
    box = mg.part("cube", grey, loc=(0, 0, 0.5))
    ball = mg.part("ico", grey, loc=(0, 0, 0.5), scale=(0.4, 0.4, 0.4))
    arm = mg.part("cyl", grey, loc=(0.55, 0, 0.5), scale=(0.2, 0.2, 0.7), rot=(0, 1.5707963, 0), vertices=12, exact=True)
    mg.join("body", [box, ball, arm])
