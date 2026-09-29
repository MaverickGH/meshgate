"""build(mg) for the cast / symmetrize check: a lumpy clay ball squared up toward a block, and a head made lopsided on
purpose (an ear on its left only) then mirrored — the result must be as wide on the right as on the left; a label patch on the block's front; a post with
a torn fringe, a slanted band and stitches; a body with an open shirt, a strap, a buckle and a pouch."""


def build(mg):
    clay = mg.color("clay", "#9a8a78")
    block = mg.blob([{"ball": (0, 1.0, 0.3), "r": 0.25}, {"ball": (0.1, 1.0, 0.4), "r": 0.15}], clay)
    mg.cast(block, "cube", 0.6)
    head = mg.blob([{"ball": (0, 0, 0.3), "r": 0.2}, {"ball": (0.2, 0, 0.45), "r": 0.07}], clay)   # the ear on +x only
    mg.symmetrize(head, "+x")
    label = mg.patch(block, mg.color("label", "#e0d8c0"), at=(0, 0.75, 0.3), size=(0.2, 0.15))
    cloth = mg.color("cloth", "#6d774f")
    post = mg.part("cube", clay, loc=(0.8, 0, 0.4), scale=(0.2, 0.2, 0.8), bevel=0.03)
    detail = [mg.fringe(post, cloth, 0.3, depth=0.05), mg.wrap(post, cloth, (0.8, 0, 0), (0.8, 0, 0.8), 0.7, slant=0.3),
              mg.stitch(post, cloth, [(0.75, -0.1, 0.6), (0.85, -0.1, 0.5)], ticks=3)]
    body = mg.part("cube", clay, loc=(-0.8, 0, 0.4), scale=(0.3, 0.2, 0.5), bevel=0.05, subdiv=1, smooth=True)
    shirt = mg.garment(body, cloth, above=0.3, below=0.6, open_front=0.08)
    dress = [body, shirt, mg.strap(shirt, clay, [(-0.75, -0.12, 0.3), (-0.75, -0.12, 0.6), (-0.75, 0.12, 0.6)], width=0.03),
             mg.buckle("label", (-0.75, -0.12, 0.5)), mg.pouch(body, clay, (-0.9, -0.1, 0.3), flap=cloth, buckle="label")]
    mg.join("cast_sym", [block, head, label, post, *detail, *dress])
