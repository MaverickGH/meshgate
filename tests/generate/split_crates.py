"""build(mg) for the split check: three crates in a pile, one with a nail in its side, joined into one mesh. Built with
--split, the file must hold one object per crate under a root — the nail stays with its crate."""


def build(mg):
    wood, dark, red, iron = mg.color("wood", "#9a6b3f"), mg.color("dark_wood", "#5e3f25"), mg.color("red", "#8a3030"), \
        mg.color("iron", "#606060")
    crates = [mg.part("cube", wood, loc=(-0.26, 0, 0.25), scale=(0.5, 0.5, 0.5), bevel=0.02),
              mg.part("cube", dark, loc=(0.26, 0, 0.25), scale=(0.5, 0.5, 0.5), bevel=0.02),
              mg.part("cube", red, loc=(0, 0, 0.76), scale=(0.5, 0.5, 0.5), bevel=0.02),
              mg.part("cyl", iron, loc=(-0.26, -0.26, 0.3), scale=(0.02, 0.02, 0.05), rot=(1.5708, 0, 0))]   # the nail
    mg.join("crate_pile", crates)
