"""build(mg) for the relations check: pieces placed by other pieces instead of guessed coordinates — a cup and a book
set down on a table, a crate snapped against its side, three plates lined up, and a socket for a lamp."""


def build(mg):
    wood = mg.color("wood", "#8a5a2b", rough=0.7)
    white = mg.color("cup_white", "#eeeeee", rough=0.3)
    red = mg.color("book_red", "#9c2b2b", rough=0.6)
    top = mg.part("cube", wood, loc=(0, 0, 0.72), scale=(1.0, 0.6, 0.04), bevel=0.01)
    legs = [mg.part("cube", wood, loc=(sx * 0.45, sy * 0.25, 0.35), scale=(0.05, 0.05, 0.7)) for sx in (-1, 1) for sy in (-1, 1)]
    cup = mg.part("cyl", white, loc=(0.2, 0.0, 1.5), scale=(0.08, 0.08, 0.1))      # dropped from high up
    mg.place(cup, on=top)
    book = mg.part("cube", red, loc=(0, 0, 2.0), scale=(0.2, 0.28, 0.04))
    mg.place(book, on=top, at=(-0.25, 0.05))
    crate = mg.part("cube", wood, loc=(3, 3, 0.2), scale=(0.4, 0.4, 0.4), bevel=0.01)
    mg.snap(crate, top, side="right", gap=0.05)
    mg.place(crate)                                                                  # on the ground
    plates = [mg.part("cyl", white, loc=(x, 0.0, 1.0 + x), scale=(0.12, 0.12, 0.015)) for x in (-0.3, 0.0, 0.3)]
    mg.align(plates, axis="z", to="min")
    for p in plates:
        mg.place(p, on=top)
    mg.socket("lamp_hook", (0, 0, 1.6))
    mg.join("table_set", [top, *legs, cup, book, crate, *plates])
