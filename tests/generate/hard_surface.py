"""build(mg) for the hard-surface check: a sci-fi crate — bevelled box with inset panels, a swept frame and a swept
handle rail; weighted normals and packed UVs come from MeshGate."""


def build(mg):
    steel = mg.color("steel", "#7d848c", rough=0.4, metal=1.0)
    panel = mg.color("panel_paint", "#3f5a6e", rough=0.6)
    rubber = mg.color("rubber_grip", "#1c1c1e", rough=0.8)
    box = mg.part("cube", steel, loc=(0, 0, 0.3), scale=(0.8, 0.6, 0.6), bevel=0.02)
    mg.inset(box, facing=(0, -1, 0), amount=0.05, depth=-0.012, color=panel)
    mg.inset(box, facing=(1, 0, 0), amount=0.05, depth=-0.012, color=panel)
    mg.inset(box, facing=(-1, 0, 0), amount=0.05, depth=-0.012, color=panel)
    frame_profile = [(-0.015, -0.01), (0.015, -0.01), (0.015, 0.01), (-0.015, 0.01)]
    frame = mg.sweep(frame_profile, [(-0.41, -0.31, 0.02), (0.41, -0.31, 0.02), (0.41, -0.31, 0.58), (-0.41, -0.31, 0.58)],
                     steel, closed_path=True, smooth=False, corners="sharp")
    grip_profile = [(0.0, -0.012), (0.012, 0.0), (0.0, 0.012), (-0.012, 0.0)]
    handle = mg.sweep(grip_profile, [(-0.2, 0.0, 0.6), (-0.15, 0.0, 0.7), (0.15, 0.0, 0.7), (0.2, 0.0, 0.6)], rubber)
    mg.join("crate", [box, frame, handle])
