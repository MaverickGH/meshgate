"""build(mg) for the cast / symmetrize check: a lumpy clay ball squared up toward a block, and a head made lopsided on
purpose (an ear on its left only) then mirrored — the result must be as wide on the right as on the left; a label patch on the block's front."""


def build(mg):
    clay = mg.color("clay", "#9a8a78")
    block = mg.blob([{"ball": (0, 1.0, 0.3), "r": 0.25}, {"ball": (0.1, 1.0, 0.4), "r": 0.15}], clay)
    mg.cast(block, "cube", 0.6)
    head = mg.blob([{"ball": (0, 0, 0.3), "r": 0.2}, {"ball": (0.2, 0, 0.45), "r": 0.07}], clay)   # the ear on +x only
    mg.symmetrize(head, "+x")
    label = mg.patch(block, mg.color("label", "#e0d8c0"), at=(0, 0.75, 0.3), size=(0.2, 0.15))
    mg.join("cast_sym", [block, head, label])
