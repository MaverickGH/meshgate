"""The cat scout as a finished character base (v15): the procedural build of zombie_cat_scout_smooth.py, shaped by
hand in MeshGate live and saved with blender_save_base — broad stepped ears, a thin folded scarf with an off-centre
knot, fabric and leather tiles, six two-sided Appearance sliders (head width and depth, body width, leg length, paw and
hand size). load_base keeps its geometry, UVs, packed textures and morphs exactly; the path is relative to the
MeshGate folder."""


def build(mg):
    mg.load_base("samples/bases/cat_scout_v15_editable.blend", morphs=True)
