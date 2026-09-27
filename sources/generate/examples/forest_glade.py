"""A forest glade (example for the scene recipe): a patch of forest — trees scattered as instances over a hill, a fence of
instanced posts, a boulder with a rock set on it. The file should store each repeated mesh once."""


def build(mg):
    grass = mg.color("grass", "#4f7a3a", material="ground")
    bark = mg.color("bark", "#5a3d26", material="wood")
    leaf = mg.color("leaves", "#2f6b2a", rough=0.8)
    wood = mg.color("fence_wood", "#8a6a44", material="wood")
    stone = mg.color("stone", "#8a8a84", material="stone")
    hill = mg.part("plane", grass, loc=(0, 0, 0), scale=(12, 12, 1))
    trunk = mg.part("cyl", bark, loc=(0, 0, 0.6), scale=(0.25, 0.25, 1.2))
    crown = mg.part("cone", leaf, loc=(0, 0, 2.0), scale=(1.4, 1.4, 2.2))
    tree = mg.join("tree", [trunk, crown])
    mg.scatter(hill, tree, 40, seed=3, scale=(0.8, 1.3), align=False, sink=0.05, instances=True)
    post = mg.part("cube", wood, loc=(0, 0, 0.5), scale=(0.12, 0.12, 1.0), bevel=0.01)
    posts = [mg.instance(post, at=(-5.5 + i * 1.0, -5.5, 0.5), turn=i * 7) for i in range(1, 11)]
    mg.place(posts[3])
    boulder = mg.part("ico", stone, loc=(3, -3, 0.4), scale=(1.2, 1.0, 0.8))
    rock = mg.part("ico", stone, loc=(0, 0, 0), scale=(0.3, 0.3, 0.25))
    small = mg.instance(rock, at=(3, -3, 3), turn=30)
    mg.place(small, on=boulder)
    mg.place(rock, at=(-3, 3))
