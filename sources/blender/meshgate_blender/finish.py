"""Surface finishes applied after a kit build (runner side, not for build code).

"weathered" (the realistic style): the kit paints every piece one flat palette colour, which reads as a toy. This bakes
the palette into real textures with what flat colours lack — dirt settled in crevices and near the ground (ambient
occlusion and height), colour variation across a surface, and fine relief as a normal map — within the tier's texture
budget. All meshes of the asset share one fresh UV atlas and one material, so the draw calls stay as they were.
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from . import compat

MAX_PX = 2048
MARGIN = 2   # bake margin in pixels


def texture_plan(budget: dict, tier: str, glow: bool, want: int | None = None,
                 normal_map: bool = True) -> tuple[int, int, int, int]:
    """(colour, orm, emissive, normal) sizes in px within the tier's texture size and memory (RGBA, +1/3 for mips).
    want: the texture size asked for (--texture 1k…8k); the tier's own limit still caps it."""
    mb = lambda px: px * px * 4 * 4 / 3 / 2 ** 20 if px else 0.0   # noqa: E731
    colour = min(budget.get("max_texture", 1024), want or MAX_PX)
    while True:
        # roughness-metallic and glow need less detail than colour; the memory saved goes to the normal map
        orm, emissive = min(colour // 2, 1024), (min(colour // 2, 1024) if glow else 0)
        base = mb(colour) + mb(orm) + mb(emissive)
        if base <= budget.get("max_texture_mb", 64) or colour <= 256:
            break
        colour //= 2
    normal = 0
    if tier != "mobile-low" and normal_map:
        for n in (colour, colour // 2, colour // 4):
            if base + mb(n) <= budget.get("max_texture_mb", 64):
                normal = n
                break
    return colour, orm, emissive, normal


def _image(name: str, px: int, non_color: bool):
    img = bpy.data.images.new(name, px, px, alpha=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def _pack(img, tmp: str):
    path = os.path.join(tmp, f"{img.name}.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.source = "FILE"
    img.reload()
    img.pack()
    img.filepath_raw = f"//textures/{img.name}.png"


def _palette_images(mat) -> dict:
    """The kit palette's images by role: basecolor, orm, emissive."""
    out = {}
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            for role in ("basecolor", "orm", "emissive"):
                if n.image.name.endswith(role):
                    out[role] = n.image
    return out


def quads(ctx) -> list[str]:
    """Quad topology for editors and further modelling: n-gons are split, then triangles are paired into quads wherever
    the shape allows. (GLB stays triangles — glTF stores nothing else; FBX and .blend keep the quads.)"""
    import bmesh
    total = quad = 0
    for o in ctx.scene.objects:
        if o.type != "MESH" or o.get("meshgate_collision_for") or o.data.shape_keys:
            continue
        if o.data.users > 1:
            o.data = o.data.copy()
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bmesh.ops.join_triangles(bm, faces=bm.faces, angle_face_threshold=math.radians(40),
                                 angle_shape_threshold=math.radians(40), cmp_seam=False, cmp_sharp=False,
                                 cmp_uvs=False, cmp_vcols=False, cmp_materials=True)
        total += len(bm.faces)
        quad += sum(1 for f in bm.faces if len(f.verts) == 4)
        bm.to_mesh(o.data)
        o.data.update()
        bm.free()
    return [f"quad topology: {quad * 100 // max(total, 1)} % quads"]


def _occlusion(nt, socket):
    """Wire an ambient-occlusion value into the glTF exporter's 'glTF Material Output' group (the occlusion slot)."""
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        if hasattr(g, "interface"):      # Blender 4.0+
            g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        else:
            g.inputs.new("NodeSocketFloat", "Occlusion")
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = g
    nt.links.new(socket, node.inputs["Occlusion"])


def _bake_material(pal: dict, size: float, clean: bool = False):
    """A temporary material that computes the weathered maps from the palette (sampled through the old UVMap).
    clean: the exact palette colours plus ambient occlusion, no weathering (full PBR for stylized looks)."""
    m = bpy.data.materials.new("meshgate_weather_bake")
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"

    def palette(role):
        t = nodes.new("ShaderNodeTexImage")
        t.image = pal[role]
        t.interpolation = "Closest"
        links.new(uv.outputs["UV"], t.inputs["Vector"])
        return t

    base = palette("basecolor")
    orm = palette("orm")
    sep_orm = nodes.new("ShaderNodeSeparateColor")
    links.new(orm.outputs["Color"], sep_orm.inputs[0])
    rough, metal = sep_orm.outputs[1], sep_orm.outputs[2]
    glow = None
    if "emissive" in pal:
        emi = palette("emissive")
        glow = nodes.new("ShaderNodeRGBToBW")   # glowing parts stay clean
        links.new(emi.outputs["Color"], glow.inputs[0])

    coord = nodes.new("ShaderNodeTexCoord")
    geo = nodes.new("ShaderNodeNewGeometry")

    def noise(scale, detail=6.0, rough_=0.55):
        n = nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough_
        links.new(coord.outputs["Object"], n.inputs["Vector"])
        return n

    def maprange(src, a, b, c, d, clamp=True):
        r = nodes.new("ShaderNodeMapRange")
        r.clamp = clamp
        links.new(src, r.inputs["Value"])
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = c, d
        return r.outputs["Result"]

    def math_(op, a, b=None):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                links.new(v, n.inputs[i])
        return n.outputs[0]

    def mix(fac, a, b, blend="MIX"):
        n = nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v if sock.type == "VALUE" else (v, v, v, 1.0)
            elif isinstance(v, tuple):
                sock.default_value = v
            else:
                links.new(v, sock)
        return n.outputs[2]

    def mapped(scale_xyz):
        m = nodes.new("ShaderNodeMapping")
        links.new(coord.outputs["Object"], m.inputs["Vector"])
        m.inputs["Scale"].default_value = scale_xyz
        return m.outputs["Vector"]

    def noise_at(vec, scale, detail=4.0, rough_=.55):
        n = nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value, n.inputs["Detail"].default_value, n.inputs["Roughness"].default_value = \
            scale, detail, rough_
        links.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def wave(vec, scale, direction, distortion, detail=2.0):
        n = nodes.new("ShaderNodeTexWave")
        n.wave_type, n.bands_direction = "BANDS", direction
        n.inputs["Scale"].default_value, n.inputs["Distortion"].default_value = scale, distortion
        n.inputs["Detail"].default_value = detail
        links.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def voronoi(scale, feature):
        n = nodes.new("ShaderNodeTexVoronoi")
        n.feature = feature
        n.inputs["Scale"].default_value = scale
        links.new(coord.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Distance"]

    def shade(c, fac):
        return mix(1.0, c, fac, "MULTIPLY")

    if clean:   # exact colours; ambient occlusion goes to the ORM red, the glTF occlusion channel
        ao = nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 16
        ao.inputs["Distance"].default_value = max(size * 0.08, 0.02)
        orm_out = nodes.new("ShaderNodeCombineColor")
        links.new(ao.outputs["AO"], orm_out.inputs[0])
        links.new(rough, orm_out.inputs[1])
        links.new(metal, orm_out.inputs[2])
        emit, bsdf, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeBsdfPrincipled"), nodes.new("ShaderNodeOutputMaterial")
        outs = {"colour": base.outputs["Color"], "orm": orm_out.outputs[0]}
        if "emissive" in pal:
            outs["emissive"] = emi.outputs["Color"]
        return m, emit, bsdf, out, outs

    # colour variation: broad blotches and finer mottling, about ±20 %, less on bare metal
    var = math_("MULTIPLY", maprange(noise(1.2 / max(size, 0.1) * 2.0).outputs["Fac"], 0.3, 0.7, 0.78, 1.14),
                maprange(noise(9.0 / max(size, 0.1) * 0.6, 8.0).outputs["Fac"], 0.35, 0.65, 0.88, 1.08))
    var = mix(math_("MULTIPLY", metal, 0.7), var, 1.0)
    col = mix(1.0, base.outputs["Color"], var, "MULTIPLY")
    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = max(size * 0.08, 0.02)
    crevice = maprange(ao.outputs["AO"], 0.45, 1.0, 1.0, 0.0)
    nz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Normal"], nz.inputs[0])
    obj = coord.outputs["Object"]

    # what each colour is made of (the kit writes it into the ORM red: material index / 16), drawn in real metres
    kind = math_("FLOOR", math_("MULTIPLY", sep_orm.outputs[0], 16.0))
    grain = math_("MULTIPLY", math_("ADD", wave(mapped((1, 1, .12)), 9.0, "X", 7.0, 4), wave(mapped((1, 1, .12)), 9.0, "Y", 7.0, 4)), .5)
    fibre, corr = noise_at(obj, 140, 3), wave(obj, 55.0, "Z", 0.0, 0)
    crack = math_("MULTIPLY", maprange(voronoi(3.0, "DISTANCE_TO_EDGE"), 0.0, 0.018, 1.0, 0.0),   # thin, and only here and there
                  maprange(noise_at(obj, 1.6, 3), .52, .64, 0.0, 1.0))
    mottle = noise_at(obj, 3.5, 6)
    moss = math_("MULTIPLY", math_("MAXIMUM", maprange(nz.outputs["Z"], .25, .85, 0, 1), math_("MULTIPLY", crevice, .6)),
                 maprange(noise_at(obj, 2.5, 6), .45, .62, 0, 1))
    brushed = noise_at(mapped((.06, 1, 1)), 40, 2)
    rust_spots = maprange(noise_at(obj, 2.2, 8, .6), .56, .7, 0, 1)
    rust_all = maprange(noise_at(obj, 2.2, 8, .6), .38, .6, 0, 1)
    weave = math_("MULTIPLY", wave(obj, 80.0, "X", 0.0, 0), wave(obj, 80.0, "Z", 0.0, 0))
    clumps, small = noise_at(obj, 3.0, 6), noise_at(obj, 28.0, 4)
    pores = maprange(voronoi(70.0, "F1"), 0.0, 0.12, 1.0, 0.0)
    looks = {   # material index: (colour, relief, extra roughness)
        1: (shade(col, maprange(grain, 0, 1, .7, 1.12)), math_("MULTIPLY", grain, .7), 0.0),                      # wood
        2: (shade(col, maprange(fibre, .3, .7, .9, 1.05)),
            math_("ADD", math_("MULTIPLY", corr, .25), math_("MULTIPLY", fibre, .12)), 0.0),                       # cardboard
        3: (mix(moss, mix(math_("MULTIPLY", crack, .6), shade(col, maprange(mottle, .35, .65, .82, 1.1)),
                          (.08, .075, .07, 1.0)), (.16, .24, .07, 1.0)),
            math_("SUBTRACT", math_("MULTIPLY", mottle, .4), math_("MULTIPLY", crack, .9)), .1),                   # stone
        4: (mix(math_("MULTIPLY", rust_spots, .85), shade(col, maprange(brushed, .3, .7, .92, 1.06)), (.32, .12, .045, 1.0)),
            math_("MULTIPLY", rust_spots, .35), math_("MULTIPLY", rust_spots, .45)),                               # metal
        5: (mix(maprange(rust_all, 0, 1, .5, .95), col, (.30, .11, .04, 1.0)),
            math_("ADD", math_("MULTIPLY", noise_at(obj, 30, 4), .5), math_("MULTIPLY", rust_all, .3)), .5),      # rust
        6: (shade(col, maprange(weave, 0, 1, .86, 1.05)),
            math_("ADD", math_("MULTIPLY", weave, .6), math_("MULTIPLY", noise_at(obj, 200, 2), .2)), .05),       # fabric
        7: (shade(shade(col, maprange(clumps, .3, .7, .7, 1.2)), maprange(small, .3, .7, .9, 1.1)),
            math_("ADD", math_("MULTIPLY", clumps, .8), math_("MULTIPLY", small, .4)), .1),                        # ground
        8: (mix(math_("MULTIPLY", crevice, .5), mix(math_("MULTIPLY", pores, .35), col, (.35, .3, .22, 1.0)), (.55, .45, .28, 1.0)),
            math_("MULTIPLY", pores, -.5), 0.0),                                                                     # bone
    }
    relief, rough_extra = None, None
    for k, (c, h, r) in looks.items():
        mask = nodes.new("ShaderNodeMath")
        mask.operation = "COMPARE"
        links.new(kind, mask.inputs[0])
        mask.inputs[1].default_value, mask.inputs[2].default_value = float(k), .5
        col = mix(mask.outputs[0], col, c)
        hk = math_("MULTIPLY", mask.outputs[0], h)
        relief = hk if relief is None else math_("ADD", relief, hk)
        if r:
            rk = math_("MULTIPLY", mask.outputs[0], r)
            rough_extra = rk if rough_extra is None else math_("ADD", rough_extra, rk)
    # dirt: occluded corners and the lowest band near the ground, broken up by noise
    world_z = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], world_z.inputs[0])
    ground = maprange(world_z.outputs["Z"], 0.0, max(size * 0.25, 0.06), 0.75, 0.0)
    breakup = maprange(noise(4.0 / max(size, 0.1) * 1.5, 4.0).outputs["Fac"], 0.4, 0.62, 0.35, 1.0)
    dirt = math_("MULTIPLY", math_("MAXIMUM", crevice, ground), breakup)
    if glow is not None:
        dirt = math_("MULTIPLY", dirt, maprange(glow.outputs[0], 0.0, 0.05, 1.0, 0.0))
    grime = mix(1.0, col, (0.1, 0.085, 0.065, 1.0), "MULTIPLY")
    col = mix(dirt, col, grime)
    # roughness: dirt is duller; relief: fine noise, stronger on rough surfaces, none on polished metal
    rough_out = math_("MINIMUM", math_("ADD", math_("ADD", rough, math_("MULTIPLY", dirt, 0.25)), rough_extra), 1.0)
    orm_out = nodes.new("ShaderNodeCombineColor")
    links.new(ao.outputs["AO"], orm_out.inputs[0])   # ambient occlusion: the glTF occlusion channel
    links.new(rough_out, orm_out.inputs[1])
    links.new(metal, orm_out.inputs[2])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = max(size * 0.006, 0.0015)
    links.new(math_("MULTIPLY", rough, 0.8), bump.inputs["Strength"])
    fine = noise(60.0 / max(size, 0.1) * 0.5, 10.0, 0.6)
    links.new(math_("ADD", math_("ADD", fine.outputs["Fac"], math_("MULTIPLY", noise(14.0 / max(size, 0.1) * 0.5, 4.0).outputs["Fac"], 0.6)),
                    math_("MULTIPLY", relief, 1.6)), bump.inputs["Height"])

    emit = nodes.new("ShaderNodeEmission")   # colour maps bake through Emission: exact values, no lighting
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    out = nodes.new("ShaderNodeOutputMaterial")
    outs = {"colour": col, "orm": orm_out.outputs[0]}
    if "emissive" in pal:
        outs["emissive"] = emi.outputs["Color"]
    return m, emit, bsdf, out, outs


def save_high(ctx, path: str) -> None:
    """Write the built model's meshes, in world space, to a .blend: the high model lighter tiers bake normals from."""
    ctx.view_layer.update()
    objs = []
    for o in ctx.scene.objects:
        if o.type == "MESH" and not o.get("meshgate_collision_for"):
            me = o.data.copy()
            me.transform(o.matrix_world)
            objs.append(bpy.data.objects.new(f"mg_high_{o.name}", me))
    bpy.data.libraries.write(path, set(objs), fake_user=True)
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)


def load_high(ctx, path: str) -> list:
    """Append the high model written by save_high into the scene (marked; removed again after the bake)."""
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("mg_high_")]
    objs = [o for o in dst.objects if o is not None]
    for o in objs:
        ctx.scene.collection.objects.link(o)
        o["meshgate_high"] = True
        o.use_fake_user = False
    return objs


def weathered(ctx, budget: dict, tier: str, tmp: str, name: str, want: int | None = None, clean: bool = False,
              high: list | None = None) -> list[str]:
    """Bake the weathered look (or, clean, the exact colours) into one full PBR texture set for every mesh of the asset:
    base colour, occlusion-roughness-metallic, emission and a normal map. want = texture size asked for. high = meshes
    of the detailed (PC) build: the normal map is baked from them onto this lighter model. Returns notes."""
    scene = ctx.scene
    high = list(high or [])
    try:
        return _weathered(ctx, scene, budget, tier, tmp, name, want, clean, high)
    finally:
        for o in high:
            me = o.data
            bpy.data.objects.remove(o)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)


def _weathered(ctx, scene, budget, tier, tmp, name, want, clean, high) -> list[str]:
    meshes = [o for o in scene.objects if o.type == "MESH" and not o.get("meshgate_collision_for")
              and not o.get("meshgate_high")]
    mats = {s.material for o in meshes for s in o.material_slots if s.material}
    if len(mats) != 1:
        return [f"weathered finish skipped: needs the one palette material (found {len(mats)})"]
    palette_mat = next(iter(mats))
    pal = _palette_images(palette_mat)
    if not {"basecolor", "orm"} <= set(pal):
        return ["weathered finish skipped: no palette textures (vertex colours)"]
    b = compat.principled(palette_mat)
    peak = b.inputs["Emission Strength"].default_value if "emissive" in pal else 0.0
    ctx.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    size = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    colour_px, orm_px, emi_px, normal_px = texture_plan(budget, tier, peak > 0, want, normal_map=not clean or bool(high))
    smallest = min(px for px in (colour_px, orm_px, emi_px, normal_px) if px)
    # gaps between UV islands wider than the bake margin on the smallest map, so no colour or glow bleeds across
    island_margin = min(0.02, 2.5 * MARGIN / smallest)
    # one shared atlas: every mesh gets a "bake" UV map, unwrapped together so the islands never overlap
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()
        uvs = o.data.uv_layers
        (uvs.get("bake") or uvs.new(name="bake"))
        uvs.active = uvs["bake"]
    for o in ctx.view_layer.objects:
        o.select_set(o in meshes)
    ctx.view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=island_margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in meshes:   # bakes and the viewport read the render UV map; the palette is sampled through "UVMap"
        for layer in o.data.uv_layers:
            layer.active_render = layer.name == "bake"

    bake_mat, emit, bsdf, out, outs = _bake_material(pal, size, clean)
    for o in meshes + high:
        for slot in o.material_slots:
            slot.material = bake_mat
    nt = bake_mat.node_tree
    target = nt.nodes.new("ShaderNodeTexImage")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16 if colour_px <= 2048 else 6    # at 4K and 8K a pixel is tiny: noise does not show
    images = {}

    def bake(kind, px, non_color, source=None):
        img = _image(f"{name}_{tier}_{kind}", px, non_color)
        target.image = img
        for n in nt.nodes:
            n.select = False
        target.select = True
        nt.nodes.active = target
        if source is not None:
            for link in list(out.inputs["Surface"].links):
                nt.links.remove(link)
            nt.links.new(source, emit.inputs["Color"])
            nt.links.new(emit.outputs[0], out.inputs["Surface"])
            btype = "EMIT"
        else:
            for link in list(out.inputs["Surface"].links):
                nt.links.remove(link)
            nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
            btype = "NORMAL"
        from_high = btype == "NORMAL" and bool(high)
        for i, o in enumerate(meshes):   # one object at a time into the shared image; clear only before the first
            for x in ctx.view_layer.objects:
                x.select_set(x is o or (from_high and x in high))
            ctx.view_layer.objects.active = o
            extra = {"use_selected_to_active": True, "cage_extrusion": size * 0.01, "max_ray_distance": size * 0.04} \
                if from_high else {}
            bpy.ops.object.bake(type=btype, normal_space="TANGENT", margin=MARGIN, use_clear=(i == 0),
                                target="IMAGE_TEXTURES", **extra)
        _pack(img, tmp)
        images[kind] = img

    bake("basecolor", colour_px, False, outs["colour"])
    bake("orm", orm_px, True, outs["orm"])
    if emi_px:
        bake("emissive", emi_px, False, outs["emissive"])
    if normal_px:
        bake("normal", normal_px, True)

    # the final material: glTF-ready PBR on the new atlas
    mat = bpy.data.materials.new(f"{name}_weathered")
    mat.use_nodes = True
    mat.use_backface_culling = palette_mat.use_backface_culling
    mnt = mat.node_tree
    pb = compat.principled(mat)

    def tex(img):
        t = mnt.nodes.new("ShaderNodeTexImage")
        t.image = img
        return t

    c = tex(images["basecolor"])
    mnt.links.new(c.outputs["Color"], pb.inputs["Base Color"])
    r = tex(images["orm"])
    sep = mnt.nodes.new("ShaderNodeSeparateColor")
    mnt.links.new(r.outputs["Color"], sep.inputs[0])
    mnt.links.new(sep.outputs[1], pb.inputs["Roughness"])
    mnt.links.new(sep.outputs[2], pb.inputs["Metallic"])
    _occlusion(mnt, sep.outputs[0])
    if "emissive" in images:
        e = tex(images["emissive"])
        mnt.links.new(e.outputs["Color"], compat.socket(pb, "Emission Color"))
        pb.inputs["Emission Strength"].default_value = peak
    if "normal" in images:
        n = tex(images["normal"])
        nm = mnt.nodes.new("ShaderNodeNormalMap")
        mnt.links.new(n.outputs["Color"], nm.inputs["Color"])
        mnt.links.new(nm.outputs["Normal"], pb.inputs["Normal"])
    mnt.nodes.active = c   # previews show the colour
    for o in meshes:
        for slot in o.material_slots:
            slot.material = mat
        uvs = o.data.uv_layers
        uvs.remove(uvs["UVMap"])
        uvs["bake"].name = "UVMap"
        uvs.active = uvs["UVMap"]
        uvs["UVMap"].active_render = True
    bpy.data.materials.remove(bake_mat)
    parts = [f"colour {colour_px} px"] + ([f"normal {normal_px} px" + (" from the PC model" if high else "")]
                                          if normal_px else []) + ["occlusion"]
    return [f"{'clean PBR' if clean else 'weathered finish'} baked ({', '.join(parts)})"]
