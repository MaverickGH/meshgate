"""build(mg) for the z-fighting check: a post with a cap flush with its top, and a plate lying exactly on a crate's
front face. MeshGate should move the smaller piece's faces a hair off, so engines do not draw them flickering."""


def build(mg):
    wood = mg.color("wood", "#8a5a2b", material="wood")
    dark = mg.color("wood_dark", "#4a2c1e", material="wood")
    post = mg.part("cube", wood, loc=(0, 0, 0.5), scale=(0.1, 0.1, 1.0))
    cap = mg.part("cube", dark, loc=(0, 0, 0.97), scale=(0.1, 0.1, 0.06))           # flush with the post's top and sides
    crate = mg.part("cube", wood, loc=(0.5, 0, 0.2), scale=(0.4, 0.4, 0.4))
    plate = mg.part("cube", dark, loc=(0.5, -0.2 + 0.005, 0.2), scale=(0.2, 0.01, 0.1))   # its front face on the crate's
    mg.join("flush_set", [post, cap, crate, plate])
