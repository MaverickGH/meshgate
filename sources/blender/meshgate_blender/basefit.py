"""A saved character base (mg.load_base) made to fit a quality tier, the way an artist makes a phone LOD of a hero model:
its textures scaled down to the tier's size and memory, and — where it has more materials than the tier allows — the
whole model baked into one atlas (colour and normal) on a fresh unwrap, so a phone draws it in one call.
Pure bpy; used by modeling.Kit.load_base.
"""
from __future__ import annotations

import math
import os

import bpy

MARGIN = 4   # bake margin in pixels: colour spills this far past each UV island, so mip levels show no seams


def _images(obj) -> list:
    return list({n.image for m in obj.data.materials if m and m.use_nodes for n in m.node_tree.nodes
                 if n.type == "TEX_IMAGE" and n.image and n.image.size[0]})


def _mb(images) -> float:
    """Texture memory as the validator counts it: RGBA with mipmaps."""
    return sum(i.size[0] * i.size[1] * 4 * 4 / 3 for i in images) / 2 ** 20


def _pack(img, tmp: str) -> None:
    path = os.path.join(tmp, f"{img.name}.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.source = "FILE"
    img.reload()
    img.pack()
    img.filepath_raw = f"//textures/{img.name}.png"


def scale_textures(obj, max_px: int | None, max_mb: float | None, tmp: str) -> list[str]:
    """Every texture at most max_px on a side, then the largest ones halved until all of them fit max_mb (90 % of it,
    so the file has room). Square powers of two stay powers of two."""
    images = _images(obj)
    if not images:
        return []
    before = _mb(images)
    target = {i: list(i.size) for i in images}
    if max_px:
        for i in images:
            w, h = target[i]
            k = min(1.0, max_px / max(w, h))
            target[i] = [max(4, int(w * k)), max(4, int(h * k))]
    if max_mb:
        def mem():
            return sum(w * h * 4 * 4 / 3 for w, h in target.values()) / 2 ** 20
        while mem() > 0.9 * max_mb:
            big = max(target, key=lambda i: target[i][0] * target[i][1])
            w, h = target[big]
            if max(w, h) <= 64:
                break
            target[big] = [max(4, w // 2), max(4, h // 2)]
    changed = [i for i in images if target[i] != list(i.size)]
    for i in changed:
        i.scale(*target[i])
        _pack(i, tmp)
    if not changed:
        return []
    return [f"base textures scaled for the tier: {len(changed)} of {len(images)}, {before:.0f} → {_mb(images):.0f} MB"]


def _pin_uv(mat, uv_name: str) -> None:
    """Make every texture of a material read the given UV map by name, not 'the active one' — so a new active map
    (the atlas being baked into) does not move them."""
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type == "TEX_IMAGE" and not n.inputs["Vector"].is_linked:
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.uv_map = uv_name
            nt.links.new(uvn.outputs["UV"], n.inputs["Vector"])
        elif n.type == "TEX_COORD":
            for link in list(n.outputs["UV"].links):
                uvn = nt.nodes.new("ShaderNodeUVMap")
                uvn.uv_map = uv_name
                nt.links.new(uvn.outputs["UV"], link.to_socket)
                nt.links.remove(link)
        elif n.type == "NORMAL_MAP" and not n.uv_map:
            n.uv_map = uv_name
        elif n.type == "UVMAP" and not n.uv_map:
            n.uv_map = uv_name


def bake_atlas(obj, px: int, tmp: str, name: str) -> list[str]:
    """The whole model into one material, exactly: the model gets a second, fresh unwrap and bakes into it from its
    own materials (their textures pinned to the old UVs) — colour, and a normal map that keeps the tiled fabric's
    relief. No rays between copies, so nothing under the clothes or behind an eye can be caught instead."""
    scene = bpy.context.scene
    old_mats = [m for m in obj.data.materials]
    uvs = obj.data.uv_layers
    orig = next((layer.name for layer in uvs if layer.active_render), uvs.active.name if uvs.active else None)
    for m in old_mats:
        if m and m.use_nodes and orig:
            _pin_uv(m, orig)
    atlas_uv = uvs.new(name="atlas")
    uvs.active = atlas_uv
    for x in bpy.context.view_layer.objects:
        x.select_set(x is obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=min(0.02, 2.5 * MARGIN / px))
    bpy.ops.object.mode_set(mode="OBJECT")
    uvs.active = uvs["atlas"]
    for layer in uvs:   # the bake writes through the atlas map
        layer.active_render = layer.name == "atlas"
    colour = bpy.data.images.new(f"{name}_atlas_colour", px, px, alpha=False)
    normal = bpy.data.images.new(f"{name}_atlas_normal", px, px, alpha=False)
    normal.colorspace_settings.name = "Non-Color"
    targets = {}   # every old material writes into the same two images
    for m in old_mats:
        if m and m.use_nodes:
            node = m.node_tree.nodes.new("ShaderNodeTexImage")
            targets[m] = node
    engine, samples = scene.render.engine, getattr(scene.cycles, "samples", 16)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    try:
        for img, kind in ((colour, "DIFFUSE"), (normal, "NORMAL")):
            for m, node in targets.items():
                node.image = img
                for n in m.node_tree.nodes:
                    n.select = False
                node.select = True
                m.node_tree.nodes.active = node
            extra = {"pass_filter": {"COLOR"}} if kind == "DIFFUSE" else {"normal_space": "TANGENT"}
            bpy.ops.object.bake(type=kind, margin=MARGIN, use_clear=True, target="IMAGE_TEXTURES", **extra)
            _pack(img, tmp)
    finally:
        scene.render.engine = engine
        if hasattr(scene, "cycles"):
            scene.cycles.samples = samples
    # one material with the two baked maps, on the atlas map alone
    mat = bpy.data.materials.new(f"{name}_atlas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    c_node = nt.nodes.new("ShaderNodeTexImage")
    c_node.image = colour
    n_node = nt.nodes.new("ShaderNodeTexImage")
    n_node.image = normal
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(c_node.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(n_node.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    for nm in [layer.name for layer in obj.data.uv_layers if layer.name != "atlas"]:
        layer = obj.data.uv_layers.get(nm)   # the old maps pointed into textures that are gone
        if layer is not None:
            obj.data.uv_layers.remove(layer)
    obj.data.uv_layers.active = obj.data.uv_layers["atlas"]
    obj.data.uv_layers["atlas"].active_render = True
    for m in old_mats:   # the base's own materials and their textures are not used any more
        if m and m.users == 0:
            bpy.data.materials.remove(m)
    return [f"base baked into one atlas for the tier ({len(old_mats)} materials → 1, colour and normal {px} px)"]


def fit(obj, *, max_materials: int | None, max_texture: int | None, max_texture_mb: float | None, tmp: str,
        name: str) -> list[str]:
    """Make a loaded base fit the tier: an atlas where it has too many materials, its textures scaled where they are
    too big. Returns notes for the report."""
    mats = [m for m in obj.data.materials if m]
    if max_materials and len(mats) > max_materials:
        px = max_texture or 1024
        while max_texture_mb and px > 64 and 2 * px * px * 4 * 4 / 3 / 2 ** 20 > 0.9 * max_texture_mb:
            px //= 2   # colour and normal together within the tier's texture memory
        return bake_atlas(obj, px, tmp, name)
    return scale_textures(obj, max_texture, max_texture_mb, tmp)
