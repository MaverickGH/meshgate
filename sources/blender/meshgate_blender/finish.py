"""Surface finishes applied after a kit build (runner side, not for build code).

"weathered" (the realistic style): the kit paints every piece one flat palette colour, which reads as a toy. This bakes
the palette into real textures with what flat colours lack — dirt settled in crevices and near the ground (ambient
occlusion and height), colour variation across a surface, and fine relief as a normal map — within the tier's texture
budget. All meshes of the asset share one fresh UV atlas and one material, so the draw calls stay as they were.
"""

from __future__ import annotations

import json
import math
import os

import bpy
from mathutils import Vector

from . import compat

MAX_PX = 2048
MARGIN = 2   # bake margin in pixels
PAINT_ATTR = "mg_paint"   # Kit.paint's soft colour layer (removed after the bake, never exported)


DETAIL_M = 2.0   # the largest size the weathered finish scales its wear, grime and occlusion to


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


def _bake_proxy(ctx, objs, mat):
    """One temporary object holding every piece to bake, in world space, with their UVs and paint (layers are
    matched by name). The pieces are hidden from rendering meanwhile, so occlusion and edge wear do not find their
    twin surfaces."""
    import bmesh
    ctx.view_layer.update()
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        o.hide_render = True
    me = bpy.data.meshes.new("meshgate_bake")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    if me.uv_layers.get("bake"):
        me.uv_layers.active = me.uv_layers["bake"]
    for layer in me.uv_layers:
        layer.active_render = layer.name == "bake"
    proxy = bpy.data.objects.new("meshgate_bake", me)
    ctx.scene.collection.objects.link(proxy)
    return proxy


def _mean_brightness(img) -> float:
    """Mean brightness of a baked image (on a small copy): a colour bake near 0 means something went wrong."""
    small = img.copy()
    try:
        small.scale(32, 32)
        px = small.pixels[:]
        return round(sum(sum(px[i:i + 3]) / 3 for i in range(0, len(px), 4)) / (len(px) // 4), 4)
    finally:
        bpy.data.images.remove(small)


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
    seen = set()
    for o in ctx.scene.objects:
        if o.type != "MESH" or o.get("meshgate_collision_for") or o.data.shape_keys or o.data in seen:
            continue
        seen.add(o.data)   # instances share a mesh: pair its triangles once
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

    # soft paint (Kit.paint): a colour per vertex whose alpha fades out past each painted region, so patch edges
    # blend instead of following the faces
    painted = nodes.new("ShaderNodeAttribute")
    painted.attribute_name = PAINT_ATTR
    base_colour = mix(painted.outputs["Alpha"], base.outputs["Color"], painted.outputs["Color"])
    soft_emission = None
    if "emissive" in pal:   # glow follows the soft paint too: the palette glow scaled by painted / palette colour
        ratio = mix(1.0, painted.outputs["Color"], base.outputs["Color"], "DIVIDE")
        soft_emission = mix(1.0, emi.outputs["Color"], mix(painted.outputs["Alpha"], (1.0, 1.0, 1.0, 1.0), ratio), "MULTIPLY")

    if clean:   # exact colours; ambient occlusion goes to the ORM red, the glTF occlusion channel
        ao = nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 16
        ao.inputs["Distance"].default_value = max(size * 0.08, 0.02)
        orm_out = nodes.new("ShaderNodeCombineColor")
        links.new(ao.outputs["AO"], orm_out.inputs[0])
        links.new(rough, orm_out.inputs[1])
        links.new(metal, orm_out.inputs[2])
        emit, bsdf, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeBsdfPrincipled"), nodes.new("ShaderNodeOutputMaterial")
        outs = {"colour": base_colour, "orm": orm_out.outputs[0]}
        if "emissive" in pal:
            outs["emissive"] = soft_emission
        return m, emit, bsdf, out, outs

    # colour variation: broad blotches and finer mottling, about ±20 %, less on bare metal
    var = math_("MULTIPLY", maprange(noise(1.2 / max(size, 0.1) * 2.0).outputs["Fac"], 0.3, 0.7, 0.78, 1.14),
                maprange(noise(9.0 / max(size, 0.1) * 0.6, 8.0).outputs["Fac"], 0.35, 0.65, 0.88, 1.08))
    var = mix(math_("MULTIPLY", metal, 0.7), var, 1.0)
    col = mix(1.0, base_colour, var, "MULTIPLY")
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
    strands, tufts = noise_at(mapped((1, 1, .07)), 260, 3), noise_at(obj, 18.0, 5)   # hair: fine streaks down the body
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
        9: (shade(shade(col, maprange(strands, .3, .7, .78, 1.12)), maprange(tufts, .3, .7, .85, 1.1)),
            math_("ADD", math_("MULTIPLY", strands, .9), math_("MULTIPLY", tufts, .5)), .08),                     # fur
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
    # curvature, the way texturing tools use it: convex edges wear lighter and smoother, hollows collect dark grime.
    # Bevel normals find edges at any mesh density; occlusion tells ridges from hollows.
    bev = nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = max(size * 0.012, 0.003)   # real edges, not every bump of a coat
    bend = nodes.new("ShaderNodeVectorMath")
    bend.operation = "DOT_PRODUCT"
    links.new(bev.outputs["Normal"], bend.inputs[0])
    links.new(geo.outputs["Normal"], bend.inputs[1])
    edge = maprange(bend.outputs["Value"], 0.985, 0.8, 0.0, 1.0)
    # ridge or hollow: an edge out in the open is convex, an edge in shadow is concave (occlusion, unlike pointiness,
    # does not flicker with the mesh's facets)
    ridge = maprange(ao.outputs["AO"], 0.82, 0.97, 0.0, 1.0)
    hollow = maprange(ao.outputs["AO"], 0.75, 0.45, 0.0, 1.0)
    wear_amt = {1: .5, 2: .35, 3: .6, 4: .75, 5: .25, 6: .1, 7: .15, 8: .7, 9: .04}   # material index → edge wear (fur: none)
    dirt_amt = {1: .35, 2: .3, 3: .45, 4: .25, 5: .35, 6: .3, 7: .2, 8: .3, 9: .1}  # → grime in concave edges
    wear_k, dirt_k = 0.3, 0.25
    for k in wear_amt:
        mk = nodes.new("ShaderNodeMath")
        mk.operation = "COMPARE"
        links.new(kind, mk.inputs[0])
        mk.inputs[1].default_value, mk.inputs[2].default_value = float(k), .5
        wear_k = math_("ADD", wear_k if not isinstance(wear_k, float) else wear_k,
                       math_("MULTIPLY", mk.outputs[0], wear_amt[k] - 0.3))
        dirt_k = math_("ADD", dirt_k if not isinstance(dirt_k, float) else dirt_k,
                       math_("MULTIPLY", mk.outputs[0], dirt_amt[k] - 0.25))
    if glow is not None:   # glowing parts stay clean
        clean_glow = maprange(glow.outputs[0], 0.0, 0.05, 1.0, 0.0)
        wear_k, dirt_k = math_("MULTIPLY", wear_k, clean_glow), math_("MULTIPLY", dirt_k, clean_glow)
    wear = math_("MULTIPLY", math_("MULTIPLY", edge, ridge), wear_k)
    grime_c = math_("MULTIPLY", math_("MULTIPLY", edge, hollow), dirt_k)   # the broad crevice dirt comes further down
    col = mix(wear, col, mix(1.0, col, (1.3, 1.28, 1.22, 1.0), "MULTIPLY"))                  # worn edges lighter
    col = mix(grime_c, col, mix(1.0, col, (0.42, 0.36, 0.28, 1.0), "MULTIPLY"))              # warm dark grime
    rough = math_("MAXIMUM", math_("SUBTRACT", rough, math_("MULTIPLY", wear, 0.25)), 0.05)   # rubbed smooth

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
        outs["emissive"] = soft_emission
    return m, emit, bsdf, out, outs


def _relief(kind: int, p) -> float:
    """Surface relief in meters for a material at world point p — sculpted-in detail on the hero model. Amplitudes are
    kept to a gentle slope (amplitude × frequency ≈ 0.1–0.35): fine detail reads as texture, not as dents."""
    from mathutils import Vector, noise as nz
    if kind == 9:    # fur: fine strands running down the body, gathered in soft clumps
        return 0.00018 * nz.noise(Vector((p.x * 320, p.y * 320, p.z * 36))) + 0.0009 * nz.noise(p * 24.0)
    if kind == 8:    # bone: a gentle undulation, fine pores and a few tiny pits
        return (0.0003 * nz.noise(p * 30.0) + 0.00003 * nz.noise(p * 700.0)
                - 0.00008 * max(0.0, nz.noise(p * 420.0) - 0.45))
    if kind == 3:    # stone: lumps and thin cracks
        return 0.0018 * nz.noise(p * 7.0) + 0.0005 * nz.noise(p * 40.0) - 0.002 * max(0.0, 0.08 - abs(nz.noise(p * 5.0)))
    if kind == 1:    # wood: grain along the length
        return 0.0006 * nz.noise(Vector((p.x * 30, p.y * 30, p.z * 3))) + 0.0001 * nz.noise(p * 200.0)
    if kind == 7:    # ground: clumps and grit
        return 0.003 * nz.noise(p * 11.0) + 0.0005 * nz.noise(p * 60.0)
    if kind == 6:    # fabric: a weave
        return 0.00022 * math.sin(p.x * 900) * math.sin(p.z * 900) + 0.0001 * nz.noise(p * 150.0)
    if kind == 2:    # cardboard: corrugation showing through
        return 0.0002 * math.sin((p.x + p.y) * 700) + 0.00015 * nz.noise(p * 90.0)
    if kind == 5:    # rust: flaky crust
        return 0.0003 * nz.noise(p * 110.0)
    if kind == 4:    # metal: faint hammer marks
        return 0.0001 * nz.noise(p * 60.0)
    return 0.0


def _hero(me, cells: dict, target_tris: int) -> None:
    """Densify a mesh in place (simple subdivision: the shape stays) and press each material's relief into it."""
    import bmesh
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    cuts = 0
    while tris * 4 ** (cuts + 1) <= target_tris and cuts < 3:
        cuts += 1
    if cuts:
        bm = bmesh.new()
        bm.from_mesh(me)
        for _ in range(cuts):
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        bm.to_mesh(me)
        bm.free()
    uv = me.uv_layers.get("UVMap")
    kinds = [0] * len(me.vertices)
    if uv is not None:
        data = uv.data
        for poly in me.polygons:
            u, v = data[poly.loop_start].uv
            k = cells.get((round(u, 4), round(v, 4)), 0)
            if k:
                for vi in poly.vertices:
                    kinds[vi] = k
    me.update()
    # normals read once: moving a vertex marks them stale, and the next vx.normal would recompute the whole mesh
    n = len(me.vertices)
    co, nor = [0.0] * (3 * n), [0.0] * (3 * n)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nor)
    for i, k in enumerate(kinds):
        if k:
            p = Vector(co[3 * i:3 * i + 3])
            d = _relief(k, p)
            co[3 * i:3 * i + 3] = p + Vector(nor[3 * i:3 * i + 3]) * d
    me.vertices.foreach_set("co", co)
    me.update()


def _tidy_uvs(margin: float) -> None:
    """What a UV artist does after an automatic unwrap: relax the stretch, give every island the same texel density,
    then pack tightly with rotation (exact shapes on Blender 3.6+). Each step is skipped where a version lacks it."""
    bpy.ops.uv.select_all(action="SELECT")
    for op, kw in ((bpy.ops.uv.minimize_stretch, {"iterations": 30}), (bpy.ops.uv.average_islands_scale, {})):
        try:
            op(**kw)
        except (RuntimeError, TypeError, AttributeError):
            pass
    for kw in ({"shape_method": "CONCAVE", "rotate": True, "margin": margin}, {"rotate": True, "margin": margin}):
        try:
            bpy.ops.uv.pack_islands(**kw)
            break
        except (RuntimeError, TypeError):
            continue


def uv_metrics(meshes, layer: str) -> dict:
    """How well the texture is used: the share of the UV square covered, and how even the texel density is (the
    spread of UV-to-surface scale across faces, weighted by area; 0 % = perfectly even)."""
    used, samples, total_area = 0.0, [], 0.0
    for o in meshes:
        me = o.data
        uv = me.uv_layers.get(layer)
        if uv is None:
            continue
        data = uv.data
        mw = o.matrix_world
        for poly in me.polygons:
            pts = [data[li].uv for li in poly.loop_indices]
            a2 = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                a2 += x1 * y2 - x2 * y1
            uv_area = abs(a2) / 2
            area = poly.area * abs(mw.determinant()) ** (2 / 3)
            used += uv_area
            if area > 1e-10 and uv_area > 0:
                samples.append(((uv_area / area) ** 0.5, area))
                total_area += area
    if not samples or total_area <= 0:
        return {}
    mean = sum(d * a for d, a in samples) / total_area
    var = sum(a * (d - mean) ** 2 for d, a in samples) / total_area
    return {"used": round(min(1.0, used), 3), "density_spread": round((var ** 0.5) / mean, 3) if mean else 0.0}


def save_high(ctx, path: str, *, hero: bool = False, cells: dict | None = None, target_tris: int = 1_200_000) -> None:
    """Write the built model's meshes, in world space, to a .blend: the high model the tiers bake from. hero = densify
    it and press each material's relief in (fur strands, bone pores, stone cracks…): sculpted detail that every tier,
    PC included, gets in its normal, colour and occlusion maps."""
    ctx.view_layer.update()
    objs = []
    meshes = [o for o in ctx.scene.objects if o.type == "MESH" and not o.get("meshgate_collision_for")
              and not o.get("meshgate_cards") and not o.get("meshgate_tiles")]
    unique = list({o.data: o for o in meshes}.values())
    total = sum(len(p.vertices) - 2 for o in unique for p in o.data.polygons) or 1
    made: dict = {}   # instances (objects sharing a mesh): one high mesh, placed by each copy's own transform
    for o in meshes:
        shared = o.data.users > 1
        if o.data not in made or not shared:
            me = o.data.copy()
            if not shared:
                me.transform(o.matrix_world)
            if hero:
                share = sum(len(p.vertices) - 2 for p in me.polygons) / total
                _hero(me, cells or {}, int(target_tris * share))
            made[o.data] = me
        h = bpy.data.objects.new(f"mg_high_{o.name}", made[o.data])
        if shared:
            h.matrix_world = o.matrix_world
        objs.append(h)
    bpy.data.libraries.write(path, set(objs), fake_user=True)
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o)
        if me.users == 0:
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
              high: list | None = None, hero: bool = False) -> list[str]:
    """Bake the weathered look (or, clean, the exact colours) into one full PBR texture set for every mesh of the asset:
    base colour, occlusion-roughness-metallic, emission and a normal map. want = texture size asked for. high = meshes
    of the detailed (PC) build: the normal map is baked from them onto this lighter model. Returns notes."""
    from .modeling import rest_pose
    scene = ctx.scene
    high = list(high or [])
    try:
        with rest_pose():   # a rigged character bakes in its rest pose, not mid-clip
            return _weathered(ctx, scene, budget, tier, tmp, name, want, clean, high, hero)
    finally:
        for o in high:
            me = o.data
            bpy.data.objects.remove(o)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)


def _weathered(ctx, scene, budget, tier, tmp, name, want, clean, high, hero=False) -> list[str]:
    meshes = [o for o in scene.objects if o.type == "MESH" and not o.get("meshgate_collision_for")
              and not o.get("meshgate_high") and not o.get("meshgate_cards")   # fur cards keep their own material
              and not o.get("meshgate_tiles")]   # so do tiling surfaces (mg.tile): they repeat, not bake
    if not meshes:
        return []
    # tiling surfaces (mg.tile) already hold part of the tier's texture memory: the atlas gets the rest
    tiled = {n.image for o in scene.objects if o.type == "MESH" and o.get("meshgate_tiles")
             for sl in o.material_slots if sl.material and sl.material.use_nodes
             for n in sl.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
    if tiled:
        taken = sum(i.size[0] * i.size[1] * 16 / 3 / 2 ** 20 for i in tiled)
        budget = {**budget, "max_texture_mb": max(budget.get("max_texture_mb", 64) - taken, 1.0)}
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
    # one shared atlas: every mesh gets a "bake" UV map, unwrapped together so the islands never overlap (instances
    # share a mesh, so they share its islands and its pixels too)
    for o in meshes:
        uvs = o.data.uv_layers
        (uvs.get("bake") or uvs.new(name="bake"))
        uvs.active = uvs["bake"]
    for o in ctx.view_layer.objects:
        o.select_set(o in meshes)
    ctx.view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=island_margin)
    _tidy_uvs(island_margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    ctx.scene["mg_uv"] = json.dumps(uv_metrics(list({o.data: o for o in meshes}.values()), "bake"))
    for o in meshes:   # bakes and the viewport read the render UV map; the palette is sampled through "UVMap"
        for layer in o.data.uv_layers:
            layer.active_render = layer.name == "bake"

    for o in meshes:   # pieces without soft paint get a clear layer: a missing one reads as opaque black paint
        if hasattr(o.data, "color_attributes") and not o.data.color_attributes.get(PAINT_ATTR):
            layer = o.data.color_attributes.new(PAINT_ATTR, "FLOAT_COLOR", "POINT")
            layer.data.foreach_set("color", [0.0] * (4 * len(layer.data)))
    # wear, grime, occlusion and bake rays work at the scale of a thing you hold or walk around: a scene of many
    # metres keeps them at that scale instead of growing them with the whole scene
    detail = min(size, DETAIL_M)
    bake_mat, emit, bsdf, out, outs = _bake_material(pal, detail, clean)
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
        # relief comes from the detailed model; colours stay on the model itself, where painted edges are soft and thin
        # parts (eyes in their sockets, whiskers) cannot pick up a neighbour's colour
        from_high = btype == "NORMAL" and bool(high)
        for i, o in enumerate(bakers):   # into the shared image; clear only before the first
            for x in ctx.view_layer.objects:
                x.select_set(x is o or (from_high and x in high))
            ctx.view_layer.objects.active = o
            extra = {"use_selected_to_active": True, "cage_extrusion": detail * 0.01, "max_ray_distance": detail * 0.04} \
                if from_high else {}
            bpy.ops.object.bake(type=btype, normal_space="TANGENT", margin=MARGIN, use_clear=(i == 0),
                                target="IMAGE_TEXTURES", **extra)
        _pack(img, tmp)
        images[kind] = img

    # instances share a mesh and so its place in the atlas: one copy of each is enough. Several pieces bake as one
    # temporary object — Cycles goes over the whole image for every object it bakes
    reps = list({o.data: o for o in reversed(meshes)}.values())
    proxy = _bake_proxy(ctx, reps, bake_mat) if len(reps) > 1 else None
    bakers = [proxy] if proxy else reps
    try:
        bake("basecolor", colour_px, False, outs["colour"])
        scene["mg_bake_colour"] = _mean_brightness(images["basecolor"])
        bake("orm", orm_px, True, outs["orm"])
        if emi_px:
            bake("emissive", emi_px, False, outs["emissive"])
        if normal_px:
            bake("normal", normal_px, True)
    finally:
        if proxy:
            me = proxy.data
            bpy.data.objects.remove(proxy)
            bpy.data.meshes.remove(me)
            for o in reps:
                o.hide_render = False

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
    for o in list({o.data: o for o in meshes}.values()):   # once per mesh (instances share one)
        uvs = o.data.uv_layers
        uvs.remove(uvs["UVMap"])
        uvs["bake"].name = "UVMap"
        uvs.active = uvs["UVMap"]
        uvs["UVMap"].active_render = True
        layer = o.data.color_attributes.get(PAINT_ATTR) if hasattr(o.data, "color_attributes") else None
        if layer is not None:
            o.data.color_attributes.remove(layer)
    bpy.data.materials.remove(bake_mat)
    parts = [f"colour {colour_px} px"] + ([f"normal {normal_px} px"] if normal_px else []) + ["occlusion"] \
        + ([f"relief from the {'hero' if hero else 'PC'} model ({sum(len(p.vertices) - 2 for o in high for p in o.data.polygons):,} triangles)"]
           if high else [])
    notes = [f"{'clean PBR' if clean else 'weathered finish'} baked ({', '.join(parts)})"]
    if scene.get("mg_bake_colour", 1.0) < 0.02:
        notes.append("the baked colour came out almost black — the colour bake failed; report this as a MeshGate bug")
    return notes
