"""build(mg) for the rework check: a library model (a stand-in hydrant in a temporary library) taken as a piece,
only its lower half kept, repainted and sculpted, with a part of our own on top."""


def build(mg):
    red = mg.color("paint_red", "#b02a1e", rough=0.5)
    rust = mg.color("rust", "#7a3b1c", rough=0.9)
    cap = mg.color("cap_steel", "#8a8f96", rough=0.4, metal=1.0)
    body = mg.model("0" * 32, red, size=1.0, axis="height", keep=((-1, -1, 0), (1, 1, 0.6)))
    mg.paint(body, rust, below=0.15, rough=0.5)
    mg.sculpt(body, "noise", amount=0.004, scale=20)
    top = mg.part("cyl", cap, loc=(0, 0, 0.62), scale=(0.3, 0.3, 0.06))
    mg.join("reworked", [body, top])
