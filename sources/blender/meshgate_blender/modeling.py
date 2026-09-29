"""MeshGate modeling kit — the small, stable API that generated models are written against.

An AI (or a person) writes one function, `def build(mg): ...`, using only this kit. MeshGate runs that function
once per quality tier with `mg.tier` set, so the same code builds a light model for phones and a detailed one
for PC ("detail by necessity"), then checks every result against the asset contract and the tier budget.

Why a kit instead of raw bpy: the contract comes for free. Every part is in meters, lands in one palette material
(one draw call on every tier), gets UVs, and the asset is grounded and named on `finish`. The API is also the whole
surface a generated script may touch (see sources/generate/safety.py).

Conventions: Blender axes, +Z up, the model's FRONT faces -Y (glTF turns that into +Z forward), X is the model's
left→right. Units are meters. Build the object standing on z = 0 around the origin.

Only methods without a leading underscore are part of the API; their docstrings are shown to the AI verbatim.
"""

from __future__ import annotations

import json
import math
import os
import random
import re

import bpy
from mathutils import Matrix, Vector

from . import compat

TIERS = ("mobile-low", "mobile-mid", "mobile-high", "pc")
# Level of detail per quality tier: the budget is a target, not only a ceiling. seg = factor for round segment
# counts, subdiv = added subdivision levels, bevel = bevel segments. Same table as the Zombie Cats pack.
DETAILS = {
    "mobile-low":  {"seg": 0.5, "subdiv": -1, "bevel": 1},
    "mobile-mid":  {"seg": 1.0, "subdiv": 0,  "bevel": 2},
    "mobile-high": {"seg": 1.5, "subdiv": 0,  "bevel": 2},
    "pc":          {"seg": 2.0, "subdiv": 1,  "bevel": 3},
}
# finish="faceted" (low-poly style): fewer segments, no subdivision, one-step bevels, flat shading everywhere
FACETED_SEG = {"mobile-low": 0.4, "mobile-mid": 0.5, "mobile-high": 0.6, "pc": 0.75}
# What a colour is made of. The realistic finish (finish.py) draws each one: wood grain, corrugated cardboard, cracked
# and mossy stone, brushed and rusting metal, woven fabric, clumpy ground, porous bone, streaky fur. Stored in the palette's ORM red.
MATERIALS = ["plain", "wood", "cardboard", "stone", "metal", "rust", "fabric", "ground", "bone", "fur"]
_GUESS = [("rust", r"rust"), ("cardboard", r"card|carton|paper"), ("wood", r"wood|plank|bark|trunk|branch|_wd|board"),
          ("stone", r"stone|rock|concrete|tomb|brick|marble|asphalt|cement"),
          ("metal", r"steel|iron|metal|tin|brass|gold|copper|chrome|nail|bolt|rivet|silver"),
          ("fur", r"fur|pelt|coat|mane|hair|wool|fleece"),
          ("fabric", r"rope|string|yarn|carpet|canvas|sack|cloth|fabric|sisal|felt"),
          ("ground", r"grass|dirt|soil|mud|ground|sand"), ("bone", r"bone|skull|tooth|teeth")]
CELLS = 8          # palette grid: 8×8 = 64 colours
PALETTE_PX = 256   # palette texture size (fits every tier, 32 px per colour)


def _linear(c: float) -> float:
    """sRGB → linear (vertex colours and emission sockets are linear; the palette is written in sRGB)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


UNFIGHT = 0.0008   # how far a face lying flat on another piece's face is moved out (meters)
SRC_ATTR = "mg_src"   # which line of build code made each vertex (geometry facts; never exported)
_PUBLIC = {"part", "lathe", "tube", "curve", "extrude", "blob", "skin", "model", "eye", "copy", "mirror_x", "scatter"}


def _seg_distance(p, a, b) -> float:
    """Distance from point p to the segment a–b (sculpt crease)."""
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def _srgb(c: float) -> float:
    """linear → sRGB."""
    c = max(0.0, c)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _paint_layer(me):
    """An empty soft-paint layer (Blender fills new colour layers with opaque white; this one starts clear)."""
    from .finish import PAINT_ATTR
    layer = me.color_attributes.new(PAINT_ATTR, "FLOAT_COLOR", "POINT")
    layer.data.foreach_set("color", [0.0] * (4 * len(layer.data)))
    return layer


class rest_pose:
    """Measure and bake a rigged character in its rest pose: with clips on NLA tracks Blender would otherwise show
    every clip at once on the current frame."""

    def __enter__(self):
        self.arms = [(a, a.data.pose_position) for a in bpy.data.objects if a.type == "ARMATURE"]
        for a, _ in self.arms:
            a.data.pose_position = "REST"
        bpy.context.view_layer.update()

    def __exit__(self, *exc):
        for a, pos in self.arms:
            a.data.pose_position = pos
        bpy.context.view_layer.update()
        return False


def _tidy_bm(bm, size: float = 1.0) -> None:
    """Remove what trips Blender's own mesh tools (subdivide can crash on it in 3.5 / 4.2): duplicate vertices, zero-area
    faces and zero-length edges, loose bits; and make the normals consistent."""
    import bmesh
    eps = max(size * 1e-6, 1e-7)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=eps)
    bmesh.ops.dissolve_degenerate(bm, dist=eps, edges=bm.edges)
    _drop_duplicate_faces(bm)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _drop_duplicate_faces(bm) -> int:
    """Delete faces lying on exactly the same vertices as another face. Re-triangulating around split edges can make
    such twins; Blender's glTF exporter (3.5) fails on a mesh that has them."""
    import bmesh
    seen, twins = set(), []
    for f in bm.faces:
        key = frozenset(f.verts)
        if key in seen:
            twins.append(f)
        else:
            seen.add(key)
    if twins:
        bmesh.ops.delete(bm, geom=twins, context="FACES_ONLY")
    return len(twins)


def _split_edges(bm, edges, smooth: float = 0.0) -> None:
    """Refine: split each edge in two and re-triangulate the faces around them — a plain path through Blender's mesh
    tools (bmesh subdivide's triangle patterns crash on some meshes in 3.5 / 4.2). smooth relaxes the new vertices."""
    import bmesh
    edges = [e for e in edges if e.is_valid and e.is_manifold]
    if not edges:
        return
    res = bmesh.ops.bisect_edges(bm, edges=edges, cuts=1)
    new = [v for v in res.get("geom_split", []) if isinstance(v, bmesh.types.BMVert)]
    faces = list({f for v in new for f in v.link_faces})
    if faces:
        bmesh.ops.triangulate(bm, faces=faces, quad_method="BEAUTY", ngon_method="BEAUTY")
        _drop_duplicate_faces(bm)
    if smooth and new:
        for _ in range(2):
            moved = {}
            for v in new:
                if v.link_edges:
                    avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
                    moved[v] = v.co.lerp(avg, 0.5 * smooth)
            for v, co in moved.items():
                v.co = co


def _seg_closest(p, a, b):
    """The point on segment a–b nearest to p (sculpt pinch)."""
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return a + ab * t


def material_code(material: str) -> float:
    """The palette's ORM red for a material: the middle of its 1/16 band (finish.py reads it back)."""
    return (MATERIALS.index(material) + .5) / 16


class ModelError(ValueError):
    """A mistake in the generated build code that the AI can fix (shown back to it verbatim)."""


def _rgb(value) -> tuple[float, float, float]:
    if isinstance(value, str):
        h = value.strip().lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            raise ModelError(f"colour '{value}' is not #rrggbb")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        rgb = tuple(float(c) for c in value[:3])
        if max(rgb) > 1.0:   # 0–255 given
            rgb = tuple(c / 255 for c in rgb)
        return tuple(min(1.0, max(0.0, c)) for c in rgb)
    raise ModelError(f"colour {value!r}: use (r, g, b) in 0..1 or '#rrggbb'")


# the rest pose a rigged character is exported in: "none" = as modelled, "a" = arms 45° down (A-pose), "t" = arms
# straight out to the sides (T-pose) — the bind poses retargeting and Humanoid setups expect
POSES = ("none", "a", "t")
ARM_DROP = {"a": 45.0, "t": 0.0}   # degrees below horizontal


class Kit:
    """The `mg` object passed to build(mg)."""

    def __init__(self, tier: str = "pc", seed: int = 1, name: str = "asset", tmp: str | None = None,
                 colors: str = "texture", max_materials: int | None = None, finish: str = "none",
                 max_influences: int = 4, params: dict | None = None, max_tris: int | None = None,
                 max_texture: int | None = None, max_texture_mb: float | None = None, pose: str = "none",
                 outline: bool = False, fit: list | None = None):
        if tier not in DETAILS:
            raise ModelError(f"unknown tier {tier}")
        if pose not in POSES:
            raise ModelError(f"unknown pose {pose!r} — use {', '.join(POSES)}")
        self._pose = pose                           # the rest pose of rigged characters (mg.rig): none, a or t
        self._outline = bool(outline) and finish in ("none", "faceted")   # toon ink line (baked finishes: one material)
        self._fit = [tuple(float(x) for x in b) for b in (fit or []) if len(b) == 3]   # (from, to, width ratio) bands
        self._pose_c: dict = {}                     # bone → the rotation that posed it (clips play as modelled)
        # "texture": one palette material with base colour / roughness-metallic / emission textures (default).
        # "vertex": no textures at all — each part's colour goes into the COLOR_0 vertex attribute, and parts share a
        # few materials grouped by metal and glow (glTF has no per-vertex roughness, so it is averaged per group).
        self._vertex = colors == "vertex"
        self._groups: dict = {}
        self._max_materials = max_materials
        self._max_influences = max(1, int(max_influences))   # bones per vertex the tier allows (mg.rig)
        self._param_values = dict(params or {})   # values set in MeshGate Studio (sliders)
        self._params: list = []                     # what the build code declared, in order
        self._max_tris = max_tris                   # the tier's triangle budget (focus regions stay within it)
        self._max_texture = max_texture             # the tier's texture size and memory (tiling materials fit in)
        self._max_texture_mb = max_texture_mb
        self._sources: dict = {}                    # code line → what it made (geometry facts for the AI)
        self._focus: list = []                      # (point, radius, strength) where the model needs more polygons
        self.tier = tier
        self.level = TIERS.index(tier)
        self.rng = random.Random(seed)
        self._name = name
        self._tmp = tmp or bpy.app.tempdir
        self._detail = DETAILS[tier]
        # "faceted" is the low-poly look, enforced here rather than hoped for from the code: flat shading, few
        # segments, no subdivision. ("weathered" is a bake after the build; see finish.py.)
        self._faceted = finish == "faceted"
        self._soft_paint = finish in ("weathered", "clean")   # baked finishes blend paint edges (finish.py)
        if self._faceted:
            self._detail = {"seg": FACETED_SEG[tier], "subdiv": -9, "bevel": 1}
        self._colors: dict[str, dict] = {}
        self._tiles: dict[str, dict] = {}   # tiling materials (mg.tile), by colour name
        self._modules: list = []              # modular kit pieces (mg.module), laid out in a row
        self._module_x = 0.0
        self._frame_end = 1
        self._mat = bpy.data.materials.new(f"{name}_palette")
        self._mat.use_nodes = True
        self._mat.use_backface_culling = True   # closed meshes: single-sided in glTF (cheaper on every engine)
        self._reset_scene()

    # ------------------------------------------------------------------ public API

    def param(self, name: str, default: float, lo: float, hi: float, *, label: str | None = None,
              step: float | None = None) -> float:
        """A number the artist can tune in MeshGate Studio with a slider, without asking the AI again: ear size, fur
        length, how far the arms reach, how big the eyes are, how many planks, how bent the tail. Use it wherever one
        number decides the look: `ear = mg.param("ear_size", 0.11, 0.06, 0.18, label="Ear size")`. Returns the
        value to build with (the default until Studio sets another, always within lo…hi). step = 1 makes a whole-number
        slider (a count, an on/off switch with 0…1). Give each name once; 3–8 well-chosen parameters are plenty."""
        name = self._ascii(str(name))
        lo, hi = float(min(lo, hi)), float(max(lo, hi))
        value = float(self._param_values.get(name, default))
        value = max(lo, min(hi, value))
        if step:
            value = round(value / float(step)) * float(step)
        if all(p["name"] != name for p in self._params):
            self._params.append({"name": name, "label": label or name.replace("_", " "), "default": float(default),
                                 "min": lo, "max": hi, "step": float(step) if step else None, "value": value})
        return int(value) if step and float(step).is_integer() else value

    def focus(self, at, radius: float, strength: float = 1.0) -> None:
        """Spend more polygons where they show: a face, hands, a silhouette edge a player looks at. Faces within `radius`
        of `at` get denser (up to `strength` levels of smooth subdivision) when the model is finished, as far as the
        tier's triangle budget allows; the rest keeps its density. Call it anywhere in build; world meters."""
        self._focus.append((Vector(at), float(radius), max(0.0, min(2.0, float(strength)))))

    def at_least(self, tier: str) -> bool:
        """True when building for `tier` or a richer one — gate optional details: `if mg.at_least("mobile-high"): add bolts`.
        Tiers from light to rich: "mobile-low", "mobile-mid", "mobile-high", "pc"."""
        return self.level >= TIERS.index(tier)

    def seg(self, n: int) -> int:
        """Segment count for round shapes scaled to the tier (pc = 2×, mobile-low = ½, never below 6). Counts below 8 are
        kept exactly, so vertices=4 is always a square and vertices=6 a hexagon. The shape functions already do this for
        their own `segments`/`vertices`/`sides` arguments — use seg() for your own loops."""
        return max(5 if self._faceted else 6, round(n * self._detail["seg"])) if n >= 8 else max(3, n)

    def color(self, name: str, rgb, rough: float = 0.6, metal: float = 0.0, glow: float = 0.0, material: str | None = None) -> str:
        """Define a named colour of the model's single palette material and return the name. rgb = (r, g, b) in 0..1 or
        '#rrggbb'. rough = roughness 0..1, metal = metallic 0..1, glow = emission strength (0 = none, 1–4 = lamp, eyes).
        material = what it is made of, for the realistic finish's surface detail: "wood", "cardboard", "stone", "metal",
        "rust", "fabric", "ground", "bone", "fur" or "plain"; by default it is read from the name (wood_dark → wood,
        cardboard_b → cardboard, iron → metal), so name colours by their material.
        At most 64 colours. Parts may also pass an (r, g, b) tuple or hex string directly as their colour."""
        if name in self._colors:
            return name
        if len(self._colors) >= CELLS * CELLS:
            raise ModelError(f"more than {CELLS * CELLS} colours — reuse colours, the palette has one cell per colour")
        if material is not None and material not in MATERIALS:
            raise ModelError(f"material '{material}' — use one of {', '.join(MATERIALS)}")
        guess = next((m for m, rx in _GUESS if re.search(rx, str(name).lower())), "plain")
        self._colors[name] = {"index": len(self._colors), "rgb": _rgb(rgb), "rough": float(rough),
                              "metal": float(metal), "glow": float(glow), "material": material or guess}
        return name

    def tile(self, name: str, pattern: str, rgb, *, size: float = 1.0, rgb2=None, rough: float = 0.7,
             metal: float = 0.0, material: str | None = None) -> str:
        """A tiling material for big surfaces — walls, floors, roads, roofs, yards, ground — that one colour cannot
        cover at a readable scale. pattern: "bricks" (4 × 12 per repeat, running bond), "planks" (5 boards),
        "tiles" (4 × 4), "cobble" (irregular stones), "shingles" (roof rows), "plates" (2 × 2 riveted metal),
        "plaster" or "ground" (soft variation; rgb2 = patches of moss, dirt or dry grass). size = meters one repeat
        covers (bricks at size=1 are 25 × 8 cm); rgb2 = joint colour (mortar, grout, gaps). Use the name like a colour:
        mg.part("cube", wall, ...). It is laid by world position, so neighbouring pieces continue the pattern. Tiers
        with too few materials and the low-poly look show its plain colour instead. Returns the name."""
        from . import tiles
        if pattern not in tiles.PATTERNS:
            raise ModelError(f"tile pattern '{pattern}' — use one of {', '.join(tiles.PATTERNS)}")
        guess = {"bricks": "stone", "cobble": "stone", "tiles": "stone", "shingles": "stone", "planks": "wood",
                 "plates": "metal", "ground": "ground", "plaster": "plain"}[pattern]
        self.color(name, rgb, rough=rough, metal=metal, material=material or guess)
        self._tiles[name] = {"pattern": pattern, "rgb": _rgb(rgb), "rgb2": _rgb(rgb2) if rgb2 is not None else None,
                             "size": max(float(size), 0.05), "rough": float(rough), "metal": float(metal),
                             "seed": len(self._tiles) + 1}
        return name

    def part(self, kind: str, color, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), *, smooth: bool | None = None,
             subdiv: int = 0, bevel: float = 0.0, taper: float | None = None, exact: bool = False,
             bevel_segments: int | None = None, **size):
        """One primitive piece. kind: "cube" (1 m edge), "sphere" and "ico" (radius 0.5), "cyl" and "cone" (radius 0.5,
        depth 1, along Z), "torus" (major 1, minor 0.25, lies in XY), "plane" (1 m), all centred on `loc` before scaling.
        scale = size along the primitive's OWN axes before rotation: scale=(0.2, 0.2, 1.5) + rot=(0, math.pi/2, 0) is a
        cylinder 0.2 m thick and 1.5 m long lying along X. rot = Euler radians (x, y, z). For a rod between two points use
        tube([a, b], radius). smooth = smooth shading (default: round kinds).
        subdiv = subdivision levels (tier-adjusted), bevel = bevel width in meters for crisp but soft edges;
        bevel_segments = its steps (default: the tier's; the low-poly look uses one flat chamfer — 2 rounds a big
        low-poly block, a head or a body, into a few clean facets).
        taper = scale of every vertex above the piece's centre, i.e. the top face (0.5 = top half as wide, 0 = a point):
        tapered posts, pyramids (cube + taper=0), truncated cones. Extra size keywords pass to Blender:
        segments/ring_count (sphere), vertices/radius/depth (cyl), radius1/radius2 (cone), major_radius/minor_radius (torus).
        Counts of 8 and more scale with the tier; exact=True keeps them as given (an octagonal tower stays 8-sided).
        The first vertex of a cyl/cone sits on +X."""
        for key in ("segments", "ring_count", "vertices", "major_segments", "minor_segments"):
            if key in size and isinstance(size[key], int) and not exact:
                size[key] = self.seg(size[key])
        ops = {"cube": bpy.ops.mesh.primitive_cube_add, "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
               "ico": bpy.ops.mesh.primitive_ico_sphere_add, "cyl": bpy.ops.mesh.primitive_cylinder_add,
               "cone": bpy.ops.mesh.primitive_cone_add, "torus": bpy.ops.mesh.primitive_torus_add,
               "plane": bpy.ops.mesh.primitive_plane_add}
        if kind not in ops:
            raise ModelError(f"part kind '{kind}' — use one of {', '.join(ops)} (or lathe/tube/extrude for other shapes)")
        defaults = {"cube": {"size": 1.0}, "plane": {"size": 1.0},
                    "sphere": {"segments": self.seg(16), "ring_count": self.seg(10), "radius": 0.5},
                    "ico": {"subdivisions": 1 + (self.level >= 2 and not self._faceted), "radius": 0.5},
                    "cyl": {"vertices": self.seg(12), "radius": 0.5, "depth": 1.0},
                    "cone": {"vertices": self.seg(12), "radius1": 0.5, "radius2": 0.0, "depth": 1.0},
                    "torus": {"major_segments": self.seg(24), "minor_segments": self.seg(10)}}[kind]
        try:
            ops[kind](location=(0, 0, 0), rotation=(0, 0, 0), **{**defaults, **size})
        except TypeError as exc:
            raise ModelError(f"part('{kind}'): {exc}") from None
        obj = bpy.context.active_object
        if taper is not None:
            for v in obj.data.vertices:
                if v.co.z > 1e-6:
                    v.co.x *= taper
                    v.co.y *= taper
        self._place(obj, loc, scale, rot)
        if bevel:
            m = obj.modifiers.new("bevel", "BEVEL")
            m.width = float(bevel)
            if bevel_segments:
                m.segments = max(1, int(bevel_segments))
            else:   # a wide rounding in one step is a chamfer that turns a soft block into an octagon: two at least
                m.segments = max(self._detail["bevel"], 2 if float(bevel) >= 0.04 and not self._faceted else 1)
            m.limit_method = "ANGLE"
        # round kinds already get more segments on richer tiers; an extra subdivision level on top would multiply
        # them again (a pc sphere with subdiv=1 went from 29k to 200k triangles), so they only lose levels on light tiers
        bonus = min(0, self._detail["subdiv"]) if kind in {"sphere", "cyl", "cone", "torus"} else self._detail["subdiv"]
        levels = max(0, subdiv + bonus) if subdiv else 0
        if levels:
            m = obj.modifiers.new("subsurf", "SUBSURF")
            m.levels = m.render_levels = levels
        self._apply_modifiers(obj)
        self._finish_piece(obj, color, kind in {"sphere", "ico", "cyl", "cone", "torus"} if smooth is None else smooth)
        return obj

    def lathe(self, profile, color, loc=(0, 0, 0), *, segments: int = 24, smooth: bool = True, cap: bool = True,
              exact: bool = False):
        """Surface of revolution around the Z axis — bottles, vases, lamp posts, wheels, bowls. profile = [(radius, z), ...]
        from bottom to top in meters; a radius of 0 closes the end to a point. cap closes open ends with flat discs.
        segments scale with the tier unless exact=True."""
        pts = [(max(0.0, float(r)), float(z)) for r, z in profile]
        if len(pts) < 2:
            raise ModelError("lathe profile needs at least two (radius, z) points")
        n = segments if exact else self.seg(segments)
        verts, faces, rings = [], [], []
        for r, z in pts:
            if r < 1e-6:
                rings.append([len(verts)])
                verts.append((0.0, 0.0, z))
            else:
                rings.append(list(range(len(verts), len(verts) + n)))
                verts += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(n):
                j = (i + 1) % n
                if len(a) == 1:
                    faces.append((a[0], b[j], b[i]))
                elif len(b) == 1:
                    faces.append((a[i], a[j], b[0]))
                else:
                    faces.append((a[i], a[j], b[j], b[i]))
        flat = []
        if cap and len(rings[0]) > 1:
            faces.append(tuple(reversed(rings[0])))
            flat.append(len(faces) - 1)
        if cap and len(rings[-1]) > 1:
            faces.append(tuple(rings[-1]))
            flat.append(len(faces) - 1)
        obj = self._mesh("lathe", verts, faces)
        self._place(obj, loc, (1, 1, 1), (0, 0, 0))
        self._finish_piece(obj, color, smooth, flat)
        return obj

    def tube(self, points, radius, color, *, sides: int = 8, radii=None, cap: bool = True, smooth: bool = True,
             exact: bool = False):
        """A round tube along a polyline — branches, pipes, cables, handles, legs, tails. points = [(x, y, z), ...] in
        meters (at least 2), radius in meters, or radii = one radius per point for tapering (e.g. [0.05, 0.03, 0.01]);
        when radii is given, radius is ignored (pass 0). sides of 8 and more scale with the tier unless exact=True;
        fewer are kept (4 = square beam)."""
        pts = [Vector(p) for p in points]
        if len(pts) < 2:
            raise ModelError("tube needs at least two points")
        rs = [float(r) for r in radii] if radii is not None else [float(radius)] * len(pts)
        if len(rs) != len(pts):
            raise ModelError("tube radii must have one value per point")
        n = sides if exact else (self.seg(sides) if sides >= 8 else max(3, sides))
        tangents = []
        for i in range(len(pts)):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
            if t.length < 1e-9:
                raise ModelError("tube has two identical points in a row")
            tangents.append(t.normalized())
        ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
        normal = tangents[0].cross(ref).normalized()
        verts, faces = [], []
        for i, (p, t, r) in enumerate(zip(pts, tangents, rs)):
            if i:   # parallel transport: rotate the previous normal onto the new tangent, no twisting
                normal = (normal - t * normal.dot(t)).normalized()
            binormal = t.cross(normal)
            for k in range(n):
                a = 2 * math.pi * k / n
                verts.append(tuple(p + (normal * math.cos(a) + binormal * math.sin(a)) * r))
        for i in range(len(pts) - 1):
            for k in range(n):
                a, b = i * n + k, i * n + (k + 1) % n
                faces.append((a, b, b + n, a + n))
        flat = []
        if cap:
            faces.append(tuple(reversed(range(n)))); flat.append(len(faces) - 1)
            last = (len(pts) - 1) * n
            faces.append(tuple(range(last, last + n))); flat.append(len(faces) - 1)
        obj = self._mesh("tube", verts, faces)
        self._finish_piece(obj, color, smooth, flat)
        return obj

    def curve(self, points, radius, color, *, radii=None, sides: int = 8, cap: bool = True, smooth: bool = True,
              closed: bool = False):
        """A smooth round tube through control points (a spline, not a polyline) — cables, hoses, vines, branches,
        ribs, spines, tentacles, springs (points on a helix), handles, horns. points = [(x, y, z), …] (2 or more);
        radius in meters, or radii = one per point for tapering (then pass radius 0); closed = a loop (a ring, a
        hoop, a coiled rope). Smoothness follows the tier. Returns the piece."""
        pts = [Vector(p) for p in points]
        if len(pts) < 2:
            raise ModelError("curve needs at least two points")
        rs = [float(r) for r in radii] if radii is not None else [float(radius)] * len(pts)
        if len(rs) != len(pts):
            raise ModelError("curve radii must have one value per point")
        if closed:
            pts, rs = pts + pts[:1], rs + rs[:1]
        steps = max(2, round({0: 2, 1: 4, 2: 6, 3: 8}[self.level] * (0.6 if self._faceted else 1.0)))
        out_p, out_r = [], []
        n = len(pts)
        for i in range(n - 1):   # Catmull-Rom through every point, radii eased along with it
            p0 = pts[i - 1] if i > 0 else (pts[-2] if closed else pts[0] * 2 - pts[1])
            p3 = pts[i + 2] if i + 2 < n else (pts[1] if closed else pts[-1] * 2 - pts[-2])
            p1, p2 = pts[i], pts[i + 1]
            for k in range(steps):
                t = k / steps
                t2, t3 = t * t, t * t * t
                out_p.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
                out_r.append(rs[i] + (rs[i + 1] - rs[i]) * (3 * t2 - 2 * t3))
        out_p.append(pts[-1])
        out_r.append(rs[-1])
        if closed:   # the tube meets itself: drop the duplicate end, no caps
            out_p, out_r = out_p[:-1] + [out_p[0] + (out_p[1] - out_p[0]) * 1e-3], out_r[:-1] + [out_r[0]]
        keep = [0] + [i for i in range(1, len(out_p)) if (out_p[i] - out_p[i - 1]).length > 1e-6]
        # thin curves come in dozens (ribs, rays, wires): fewer sides on the phone tiers too
        n_sides = self.seg(sides) if sides >= 8 else max(3, round(sides * {0: 0.6, 1: 0.8, 2: 1.0, 3: 1.0}[self.level]))
        return self.tube([tuple(out_p[i]) for i in keep], 0, color, radii=[out_r[i] for i in keep], sides=n_sides,
                         cap=cap and not closed, smooth=smooth, exact=True)

    def scatter(self, surface, piece, count: int, *, seed: int = 0, scale=(0.8, 1.2), align: bool = True,
                spin: bool = True, sink: float = 0.0, at=None, radius: float = 0.1, facing=None,
                below: float | None = None, above: float | None = None, instances: bool = False):
        """Copies of `piece` scattered over the surface of another piece — pebbles on ground, grass tufts, moss,
        mushrooms on a log, spikes on a shell, rivets, warts, fur tufts, leaves on a branch. count = copies on the pc
        tier (fewer on phones: ½, ¼, ⅛). The piece is modelled standing at the origin, its up along +Z; each copy is
        stood on the surface (align = up along the surface normal, else straight up), turned randomly about it (spin),
        scaled by a random factor in scale = (min, max) and sunk `sink` meters in. Limit where copies land with at +
        radius, facing (a direction the surface must face), below / above (heights). `piece` is used up (do not also
        join it); returns one piece holding every copy.
        instances=True (trees on a hill, rocks across a field, lamps along a street — big, repeated things): the
        copies share their mesh (see instance()); sizes come from three variants within `scale`. Returns a group
        holding the copies, to attach() or place like one piece."""
        import bmesh
        self._bake(surface)
        self._bake(piece)
        n = max(1, round(count * {3: 1.0, 2: 0.5, 1: 0.25, 0: 0.125}[self.level]))
        rng = random.Random(seed * 7919 + 13)
        sm = surface.data
        off = surface.location
        tris = []
        sm.calc_loop_triangles()
        for lt in sm.loop_triangles:
            a, b, c = (sm.vertices[i].co + off for i in lt.vertices)
            nrm = (b - a).cross(c - a)
            area = nrm.length / 2
            if area <= 0:
                continue
            nrm.normalize()
            cen = (a + b + c) / 3
            if at is not None and (cen - Vector(at)).length > radius:
                continue
            if facing is not None and nrm.dot(Vector(facing).normalized()) < 0.35:
                continue
            if (below is not None and cen.z > below) or (above is not None and cen.z < above):
                continue
            tris.append((a, b, c, nrm, area))
        if not tris:
            raise ModelError("scatter found no surface where the copies may land — check at / radius / facing / heights")
        total = sum(t[4] for t in tris)
        cum, acc = [], 0.0
        for t in tris:
            acc += t[4]
            cum.append(acc)
        if instances:
            return self._scatter_instances(piece, tris, cum, total, n, rng, scale, align, spin, sink)
        src = bmesh.new()
        src.from_mesh(piece.data)
        bmesh.ops.translate(src, verts=src.verts, vec=piece.location)   # piece space → its placed position
        base = piece.location.copy()
        out = bmesh.new()
        import bisect
        for _ in range(n):
            a, b, c, nrm, _area = tris[min(bisect.bisect_left(cum, rng.random() * total), len(tris) - 1)]
            u, v = rng.random(), rng.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + (b - a) * u + (c - a) * v
            up = nrm if align else Vector((0, 0, 1))
            m = up.to_track_quat("Z", "Y").to_matrix().to_4x4()
            if spin:
                m = m @ Matrix.Rotation(rng.uniform(0, 2 * math.pi), 4, "Z")
            k = rng.uniform(*scale) if isinstance(scale, (tuple, list)) else float(scale)
            xf = Matrix.Translation(p - up * sink) @ m @ Matrix.Scale(k, 4) @ Matrix.Translation(-base)
            tmp = src.copy()
            bmesh.ops.transform(tmp, matrix=xf, verts=tmp.verts)
            me_tmp = bpy.data.meshes.new("scatter_tmp")
            tmp.to_mesh(me_tmp)
            tmp.free()
            out.from_mesh(me_tmp)
            bpy.data.meshes.remove(me_tmp)
        src.free()
        me = bpy.data.meshes.new("scatter")
        out.to_mesh(me)
        out.free()
        for mat in piece.data.materials:
            me.materials.append(mat)
        obj = bpy.data.objects.new("scatter", me)
        bpy.context.collection.objects.link(obj)
        self._forget(piece)
        return obj

    def _scatter_instances(self, piece, tris, cum, total, n, rng, scale, align, spin, sink):
        """scatter(instances=True): up to three pre-scaled variants of the piece, each copy a shared-mesh placement."""
        import bisect
        lo, hi = (scale if isinstance(scale, (tuple, list)) else (scale, scale))
        sizes = [lo] if abs(hi - lo) < 1e-6 else [lo + (hi - lo) * t for t in (0.0, 0.5, 1.0)]
        variants = []
        for k in sizes:
            me = piece.data.copy()
            me.transform(Matrix.Scale(float(k), 4))
            variants.append(me)
        group = self.group(f"{piece.name}_set")
        for i in range(n):
            a, b, c, nrm, _area = tris[min(bisect.bisect_left(cum, rng.random() * total), len(tris) - 1)]
            u, v = rng.random(), rng.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + (b - a) * u + (c - a) * v
            up = nrm if align else Vector((0, 0, 1))
            m = up.to_track_quat("Z", "Y").to_matrix().to_4x4()
            if spin:
                m = m @ Matrix.Rotation(rng.uniform(0, 2 * math.pi), 4, "Z")
            obj = bpy.data.objects.new(f"{piece.name}_{i:03d}", variants[rng.randrange(len(variants))])
            bpy.context.collection.objects.link(obj)
            obj.location = p - up * sink
            obj.rotation_euler = m.to_euler()
            obj.parent = group   # the group sits at the origin unrotated: no parent inverse needed
        self._forget(piece)
        for me in variants:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        return group

    def modify(self, obj, kind: str, **opts):
        """Apply one Blender modifier to a piece, the way an artist stacks them:
          "solidify"  thickness= — give an open shell or a plane thickness (leaves, fins, cloth, paper, ears)
          "array"     count=, offset=(x, y, z) meters — repeat in a row (vertebrae, chain links, planks, stairs)
          "displace"  strength= meters, scale= size of the bumps in meters — noisy relief (terrain, rock, bark)
          "smooth"    factor=, repeat= — relax lumps and hard edges
          "remesh"    size= voxel meters — rebuild as an even, closed mesh (after many cuts; melted shapes)
          "bevel"     width=, segments= — round every sharp edge
          "wireframe" thickness= — keep only the edges as struts (cages, grilles, lattices)
          "subdivide" levels= — smooth subdivision (tier-adjusted)
          "decimate"  ratio= 0…1 — fewer faces, same shape
          "shrinkwrap" target=another piece, offset= — hug its surface (straps, bandages, clothes)
        Returns the piece."""
        kind = str(kind).lower()
        self._bake(obj)
        if kind == "displace":
            size = float(opts.get("scale", 0.1))
            self._refine(obj, size / 3)
        mods = {"solidify": "SOLIDIFY", "array": "ARRAY", "displace": "DISPLACE", "smooth": "SMOOTH", "remesh": "REMESH",
                "bevel": "BEVEL", "wireframe": "WIREFRAME", "subdivide": "SUBSURF", "decimate": "DECIMATE",
                "shrinkwrap": "SHRINKWRAP"}
        if kind not in mods:
            raise ModelError(f"modify: unknown '{kind}' — use {', '.join(mods)}")
        m = obj.modifiers.new(kind, mods[kind])
        if kind == "solidify":
            m.thickness, m.offset = float(opts.get("thickness", 0.01)), 0.0
            m.use_even_offset = True
        elif kind == "array":
            m.count = max(1, int(opts.get("count", 2)))
            m.use_relative_offset, m.use_constant_offset = False, True
            m.constant_offset_displace = tuple(opts.get("offset", (0.1, 0, 0)))
        elif kind == "displace":
            tex = bpy.data.textures.new(f"mg_displace_{len(bpy.data.textures)}", "CLOUDS")
            tex.noise_scale = float(opts.get("scale", 0.1))
            m.texture, m.texture_coords = tex, "GLOBAL"
            m.strength, m.mid_level = float(opts.get("strength", 0.01)), 0.5
        elif kind == "smooth":
            m.factor, m.iterations = float(opts.get("factor", 0.5)), int(opts.get("repeat", 5))
        elif kind == "remesh":
            m.mode, m.voxel_size = "VOXEL", max(float(opts.get("size", 0.02)), 0.002)
        elif kind == "bevel":
            m.width, m.segments = float(opts.get("width", 0.005)), int(opts.get("segments", self._detail["bevel"]))
            m.limit_method = "ANGLE"
        elif kind == "wireframe":
            m.thickness, m.use_even_offset = float(opts.get("thickness", 0.01)), False
        elif kind == "subdivide":
            m.levels = m.render_levels = max(0, int(opts.get("levels", 1)) + min(0, self._detail["subdiv"]))
        elif kind == "decimate":
            m.ratio = min(1.0, max(0.01, float(opts.get("ratio", 0.5))))
        elif kind == "shrinkwrap":
            target = opts.get("target")
            if target is None:
                raise ModelError("modify('shrinkwrap') needs target=another piece")
            self._bake(target)
            m.target, m.offset = target, float(opts.get("offset", 0.002))
        bpy.context.view_layer.update()
        self._apply_modifiers(obj)
        self._fix_normals(obj)
        return obj

    def sweep(self, profile, path, color, *, closed_path: bool = False, cap: bool = True, smooth: bool = True,
              scale=None, corners: str = "smooth"):
        """Sweep a 2D profile along a smooth path — frames, mouldings, rails, rims, pipes with a shaped cross-section,
        a sword's fuller, a tyre. profile = [(x, y), …] in meters around the path (x across, y up), a closed outline;
        path = [(x, y, z), …] (2 or more points, smoothed like mg.curve); closed_path = a loop (a picture frame, a
        wheel rim); scale = one factor per path point to taper the profile; corners = "sharp" keeps the path's corners
        with mitred joints like a picture frame (else the path is a smooth spline). Returns the piece."""
        prof = [tuple(float(c) for c in p_) for p_ in profile]
        if len(prof) < 3:
            raise ModelError("sweep profile needs at least three points")
        pts = [Vector(p_) for p_ in path]
        if len(pts) < 2:
            raise ModelError("sweep path needs at least two points")
        sc = [float(x) for x in scale] if scale is not None else [1.0] * len(pts)
        if closed_path:
            pts, sc = pts + pts[:1], sc + sc[:1]
        steps = max(2, round({0: 2, 1: 4, 2: 6, 3: 8}[self.level] * (0.6 if self._faceted else 1.0)))
        out_p, out_s = [], []
        n = len(pts)
        sharp = corners == "sharp"
        for i in range(n - 1):
            if sharp:   # straight runs between the given corners
                out_p.append(pts[i])
                out_s.append(sc[i])
                continue
            p0 = pts[i - 1] if i > 0 else (pts[-2] if closed_path else pts[0] * 2 - pts[1])
            p3 = pts[i + 2] if i + 2 < n else (pts[1] if closed_path else pts[-1] * 2 - pts[-2])
            p1, p2 = pts[i], pts[i + 1]
            for k in range(steps):
                t = k / steps
                t2, t3 = t * t, t * t * t
                out_p.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
                out_s.append(sc[i] + (sc[i + 1] - sc[i]) * t)
        if not closed_path:
            out_p.append(pts[-1])
            out_s.append(sc[-1])
        m = len(out_p)
        tangents = []
        for i in range(m):
            a = out_p[(i - 1) % m] if closed_path or i > 0 else out_p[i]
            b = out_p[(i + 1) % m] if closed_path or i < m - 1 else out_p[i]
            t = (b - a)
            tangents.append(t.normalized() if t.length > 1e-9 else Vector((1, 0, 0)))
        up = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
        side = tangents[0].cross(up).normalized()
        verts, faces = [], []
        k = len(prof)
        for i, (p_, t) in enumerate(zip(out_p, tangents)):
            side = (side - t * side.dot(t)).normalized()   # parallel transport: no twist along the path
            upv = side.cross(t)
            stretch, bend = 1.0, None
            if sharp:   # a mitre: across the corner (along its bisector in the path's plane) the ring widens
                a = out_p[(i - 1) % m] if closed_path or i > 0 else None
                b = out_p[(i + 1) % m] if closed_path or i < m - 1 else None
                if a is not None and b is not None:
                    d1, d2 = (p_ - a).normalized(), (b - p_).normalized()
                    if (d2 - d1).length > 1e-6:
                        bend = (d2 - d1).normalized()
                        stretch = 1.0 / max(0.3, (1 + d1.dot(d2)) / 2) ** 0.5
            for x, y in prof:
                o = side * x + upv * y
                if bend is not None:
                    o = o + bend * o.dot(bend) * (stretch - 1.0)
                verts.append(tuple(p_ + o * out_s[i]))
        rings = m if closed_path else m
        for i in range(rings - (0 if closed_path else 1)):
            j = (i + 1) % m
            for q in range(k):
                faces.append((i * k + q, i * k + (q + 1) % k, j * k + (q + 1) % k, j * k + q))
        flat = []
        if cap and not closed_path:
            faces.append(tuple(reversed(range(k)))); flat.append(len(faces) - 1)
            last = (m - 1) * k
            faces.append(tuple(range(last, last + k))); flat.append(len(faces) - 1)
        obj = self._mesh("sweep", verts, faces)
        self._fix_normals(obj)
        self._finish_piece(obj, color, smooth, flat)
        return obj

    def inset(self, obj, *, facing=(0, -1, 0), amount: float = 0.01, depth: float = -0.005, each: bool = True,
              color=None):
        """Panels, buttons and recesses on the faces of a piece that face a direction — the hard-surface artist's
        inset: each face (or the whole region, each=False) gets a border `amount` wide and its middle pushed `depth`
        (negative = sunk in, positive = raised). facing = the direction those faces look (default the front, -Y);
        color = paint the inner panels another palette colour. Best on bevelled cubes, extrusions and sweeps.
        Returns the piece."""
        import bmesh
        self._bake(obj)
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        tag = bm.faces.layers.int.get("mg_inner") or bm.faces.layers.int.new("mg_inner")   # before taking faces: a new layer
        bm.normal_update()                                                                  # would invalidate them
        d = Vector(facing).normalized()
        # only faces wide enough to hold the border: a bevel's thin strips would fold into spikes
        faces = [f for f in bm.faces if f.normal.dot(d) > 0.85 and min(e.calc_length() for e in f.edges) > 2.2 * abs(amount)]
        if not faces:
            bm.free()
            raise ModelError("inset found no faces facing that way wide enough for that border")
        for f in faces:
            f[tag] = 1   # the original faces become the inner panels
        if each:
            bmesh.ops.inset_individual(bm, faces=faces, thickness=float(amount), depth=float(depth))
        else:
            bmesh.ops.inset_region(bm, faces=faces, thickness=float(amount), depth=float(depth))
        bm.to_mesh(me)
        bm.free()
        me.update()
        attr = me.attributes.get("mg_inner")
        if color is not None and attr is not None:
            u, v = self._cell_uv(self._color_name(color))
            uv = me.uv_layers.active.data
            flags = [0] * len(me.polygons)
            attr.data.foreach_get("value", flags)
            for poly, on in zip(me.polygons, flags):
                if on:
                    for li in poly.loop_indices:
                        uv[li].uv = (u, v)
        if attr is not None:
            me.attributes.remove(attr)
        return obj

    def extrude(self, outline, depth, color, loc=(0, 0, 0), rot=(0, 0, 0), *, bevel: float = 0.0, smooth: bool = False):
        """A flat shape with thickness — signs, blades, planks, leaves, logos, gears. outline = [(x, z), ...] polygon in
        the XZ plane (front view, may be concave, no self-crossing), extruded `depth` meters along Y, centred on y = 0."""
        pts = [(float(x), float(z)) for x, z in outline]
        if len(pts) < 3:
            raise ModelError("extrude outline needs at least three points")
        area = sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]))
        if area < 0:   # counter-clockwise seen from the front (-Y) so the normals face outward
            pts.reverse()
        n, h = len(pts), float(depth) / 2
        verts = [(x, -h, z) for x, z in pts] + [(x, h, z) for x, z in pts]
        faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        obj = self._mesh("extrude", verts, faces)
        self._fix_normals(obj)
        self._place(obj, loc, (1, 1, 1), rot)
        if bevel:
            m = obj.modifiers.new("bevel", "BEVEL")
            m.width = float(bevel); m.segments = self._detail["bevel"]; m.limit_method = "ANGLE"
            self._apply_modifiers(obj)
        self._finish_piece(obj, color, smooth)
        return obj

    def mirror_x(self, obj, name: str | None = None):
        """A mirrored copy across the X = 0 plane (left/right pairs: ears, arms, wheels). Returns the new object."""
        c = obj.copy()
        c.data = obj.data.copy()
        bpy.context.collection.objects.link(c)
        c.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
        self._flip(c.data)
        c.location.x = -obj.location.x
        c.rotation_euler = (obj.rotation_euler.x, -obj.rotation_euler.y, -obj.rotation_euler.z)
        if name:
            c.name = name
        return c

    def copy(self, obj, loc=None, rot=None, scale=None):
        """A copy of a piece (shares nothing) — repeat planks, bolts, blades. loc sets the copy's origin (absolute, meters);
        rot and scale are applied around that origin. A part()'s origin is its loc, a join()'ed mesh's origin is the world
        origin — so build a repeated piece at the origin, then copy(piece, loc=..., rot=...) to place each instance."""
        c = obj.copy()
        c.data = obj.data.copy()
        bpy.context.collection.objects.link(c)
        if loc is not None:
            c.location = loc
        if rot is not None:
            c.rotation_euler = rot
        if scale is not None:
            c.scale = scale
        self._bake(c)
        return c

    def module(self, name: str, parts, *, grid: float = 2.0, footprint=(1, 0)):
        """One piece of a modular kit — a wall, a wall with a window, a doorway, a corner, a floor tile, stairs — made
        to a grid so level designers snap the pieces together in the engine. Build it with its footprint's corner at
        the origin: x from 0 to footprint[0] × grid, y from 0 to footprint[1] × grid (0 for a wall: its thickness sits
        around y = 0), z up from 0. parts are joined into the module. The asset shows every module in a row; each is
        also written as its own file (<asset>_<name>.glb, origin at that corner). Choose tile sizes (mg.tile) that
        divide the grid, so bricks and planks carry on across the joints. Returns the module."""
        name = self._ascii(name)
        if any(m["meshgate_module"] == name for m in self._modules):
            raise ModelError(f"module '{name}' twice — give every module its own name")
        grid = float(grid)
        if grid <= 0:
            raise ModelError("module grid must be positive (meters)")
        obj = self.join(f"MOD_{name}", list(parts) if isinstance(parts, (list, tuple)) else [parts])
        obj["meshgate_module"] = name
        obj["meshgate_grid"] = grid
        obj["meshgate_footprint"] = [float(footprint[0]), float(footprint[1])]
        obj.location.x += self._module_x   # laid out in a row, a grid cell apart
        self._module_x += (max(float(footprint[0]), 1.0) + 1.0) * grid
        self._modules.append(obj)
        return obj

    def instance(self, piece, at=None, *, turn: float = 0.0, rot=None):
        """A copy that shares the piece's mesh — trees in a forest, fence posts, chairs round a table, lamps down a
        street, crates in a warehouse. The file stores the mesh once and engines can draw every copy in one go, so a
        hundred copies cost about the memory of one (triangles still count per copy). at = where the copy's origin
        goes (default: the piece's own place); turn = degrees about the vertical; rot = (x, y, z) radians instead.
        Same size as the piece: for another size make another piece. Build the piece completely first — shaping or
        painting it afterwards changes every copy, and joining a copy makes it an ordinary piece again."""
        self._bake(piece)
        if piece.type != "MESH":
            raise ModelError("instance() takes a mesh piece")
        c = piece.copy()   # shares piece.data
        bpy.context.collection.objects.link(c)
        if at is not None:
            c.location = Vector(at)
        c.rotation_euler = tuple(rot) if rot is not None else (0.0, 0.0, math.radians(float(turn)))
        return c

    def join(self, name: str, parts):
        """Merge pieces into one mesh object named `name`, origin at the world origin. One mesh per rigid part:
        join everything that never moves separately (a whole prop is usually one join)."""
        from .finish import PAINT_ATTR
        meshes_ = [p for p in parts if getattr(p, "type", None) == "MESH" and not p.get("meshgate_cards")]
        if any(p.data.color_attributes.get(PAINT_ATTR) for p in meshes_):
            for p in meshes_:
                if not p.data.color_attributes.get(PAINT_ATTR):
                    if p.data.users > 1:
                        p.data = p.data.copy()
                    _paint_layer(p.data)
        parts = [p for p in parts if p is not None]
        if self._faceted or self.level == 0:
            # big faces bend by their corners: a patch lying on them as a piece of its own slides into them when a
            # rigged body moves; as part of the same skin it bends with it exactly
            for patch in [p for p in parts if p.get("meshgate_patch_on")]:
                host = next((p for p in parts if p is not patch and p.name == patch["meshgate_patch_on"]), None)
                if host is not None:
                    del patch["meshgate_patch_on"]
                    self.union([host, patch])
                    parts = [p for p in parts if p is not patch]
        cards = [p for p in parts if p.get("meshgate_cards")]   # fur keeps its own cutout material: a child, not merged
        parts = [p for p in parts if not p.get("meshgate_cards")]
        if not parts:
            raise ModelError(f"join('{name}') got no parts")
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for p in parts:
            self._bake(p)
            p.select_set(True)
        bpy.context.view_layer.update()   # join reads matrix_world: make it current after the bakes above
        bpy.context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        obj = bpy.context.active_object
        loc = obj.matrix_world.translation.copy()   # origin back to the world origin (the asset's ground point)
        obj.location = (0, 0, 0)
        obj.data.transform(Matrix.Translation(loc))
        obj.name = obj.data.name = self._ascii(name)
        for c in cards:
            self._bake(c)
            c.parent = obj
            c.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        return obj

    def pivot(self, obj, point):
        """Move the object's origin to `point` (world meters) without moving its mesh — the hinge of a lid or door,
        the axle of a wheel, the base of a swinging sign. Call before animate()."""
        bpy.context.view_layer.update()
        local = obj.matrix_world.inverted() @ Vector(point)
        obj.data.transform(Matrix.Translation(-local))
        obj.matrix_world = obj.matrix_world @ Matrix.Translation(local)
        return obj

    def attach(self, child, parent):
        """Parent `child` to `parent` keeping its world position (moving parts under the body)."""
        bpy.context.view_layer.update()
        world = child.matrix_world.copy()
        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()   # assigning .parent resets this in Blender
        child.matrix_world = world
        return child

    # ------------------------------------------------------------------ relations: place parts by other parts

    @staticmethod
    def _world(o):
        """o's world matrix from its own transform and its parents' (matrix_world can lag behind until an update)."""
        m = o.matrix_basis.copy()
        return Kit._world(o.parent) @ o.matrix_parent_inverse @ m if o.parent is not None else m

    def _box(self, obj):
        if obj.type == "EMPTY" and obj.children:   # a group (scatter instances): the box around everything in it
            pts, todo = [], list(obj.children)
            while todo:
                c = todo.pop()
                todo += list(c.children)
                if c.type == "MESH":
                    m = self._world(c)
                    pts += [m @ v.co for v in c.data.vertices]
            pts = pts or [obj.location.copy()]
        elif obj.type == "MESH" and obj.data.users > 1:   # an instance keeps its turn: baking would unshare the mesh
            m = self._world(obj)
            pts = [m @ v.co for v in obj.data.vertices] or [obj.location.copy()]
        else:
            self._bake(obj)
            pts = [v.co + obj.location for v in obj.data.vertices] if obj.type == "MESH" and obj.data.vertices else [obj.location.copy()]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        return lo, hi

    def place(self, obj, on=None, *, at=None, sink: float | None = None):
        """Set a piece down on another piece's surface, the way you put a cup on a table: it drops straight down (−Z)
        until its lowest point meets the surface of `on`, then sinks `sink` meters in (default a hair, so it never
        floats). on=None sets it on the ground (z = 0). at = (x, y) to move it there first (else it drops where it is).
        Works on any shape under it — a table top, a rock, a roof. Returns the piece."""
        from mathutils.bvhtree import BVHTree
        lo, hi = self._box(obj)
        if at is not None:
            obj.location.x += float(at[0]) - (lo.x + hi.x) / 2
            obj.location.y += float(at[1]) - (lo.y + hi.y) / 2
            lo, hi = self._box(obj)
        size = max(hi - lo) or 0.01
        if on is None:   # the ground
            obj.location.z -= lo.z
            return obj
        self._bake(on)
        me = on.data
        bvh = BVHTree.FromPolygons([tuple(v.co + on.location) for v in me.vertices], [tuple(p_.vertices) for p_ in me.polygons])
        size = max(hi - lo) or 0.01
        best = None
        cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        for dx in (-0.35, 0.0, 0.35):   # a few rays across the footprint: the highest surface under it wins
            for dy in (-0.35, 0.0, 0.35):
                origin = Vector((cx + dx * (hi.x - lo.x), cy + dy * (hi.y - lo.y), hi.z + size * 10))
                hit = bvh.ray_cast(origin, Vector((0, 0, -1)))
                if hit[0] is not None and (best is None or hit[0].z > best):
                    best = hit[0].z
        if best is None:
            raise ModelError("place(): nothing of that piece is under it — move it over the piece first (at=)")
        depth = float(sink) if sink is not None else max(0.002, size * 0.01)
        obj.location.z += best - lo.z - depth
        return obj

    def snap(self, obj, to, *, side: str = "right", gap: float = 0.0, center: bool = True):
        """Put a piece right against another one, box to box: side = where it goes relative to `to` — "left"/"right"
        (−X/+X), "front"/"back" (−Y/+Y), "top"/"bottom" (+Z/−Z); gap = meters between them (negative overlaps, to join
        them firmly); center = also line their middles up on the other axes. Returns the piece."""
        axes = {"left": (0, -1), "right": (0, 1), "front": (1, -1), "back": (1, 1), "top": (2, 1), "bottom": (2, -1)}
        if side not in axes:
            raise ModelError(f"snap side '{side}' — use {', '.join(axes)}")
        a, sgn = axes[side]
        lo, hi = self._box(obj)
        tlo, thi = self._box(to)
        move = Vector()
        move[a] = (thi[a] + gap - lo[a]) if sgn > 0 else (tlo[a] - gap - hi[a])
        if center:
            for i in range(3):
                if i != a:
                    move[i] = (tlo[i] + thi[i]) / 2 - (lo[i] + hi[i]) / 2
        obj.location += move
        return obj

    def align(self, objs, axis: str = "x", to: str = "center", target=None):
        """Line pieces up along an axis ("x", "y" or "z"): to = "min", "center" or "max" of their boxes; target = a
        piece to line them up with (else the first one). Returns the pieces."""
        i = "xyz".index(str(axis).lower())
        pick = {"min": lambda lo, hi: lo[i], "center": lambda lo, hi: (lo[i] + hi[i]) / 2, "max": lambda lo, hi: hi[i]}[to]
        objs = list(objs)
        ref = pick(*self._box(target if target is not None else objs[0]))
        for o in objs:
            o.location[i] += ref - pick(*self._box(o))
        return objs

    def socket(self, name: str, at, rot=(0, 0, 0)):
        """An attachment point the engines see: a hand holding a weapon, where a muzzle flash or smoke starts, a
        door's hinge, where a rider sits. at = (x, y, z) meters; rot = its orientation (radians). It is exported as an
        empty named SOCKET_<name> under the asset (Unreal reads that prefix; Unity and Godot get a child transform)."""
        e = bpy.data.objects.new(f"SOCKET_{self._ascii(name)}", None)
        e.empty_display_type, e.empty_display_size = "ARROWS", 0.05
        bpy.context.collection.objects.link(e)
        e.location, e.rotation_euler = Vector(at), rot
        e["meshgate_socket"] = True
        return e

    def group(self, name: str, loc=(0, 0, 0)):
        """An empty (no mesh) to hold moving parts together — a root for a multi-part asset."""
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
        e = bpy.context.active_object
        e.name = self._ascii(name)
        return e

    def animate(self, obj, clip: str, keys, path: str = "rotation_euler", *, smooth: bool = True):
        """Keyframe an object into an animation clip. keys = [(frame, value), ...] at 30 fps; path = "rotation_euler"
        (value = (x, y, z) radians), "location" ((x, y, z) meters, relative to the parent) or "scale". Parts keyed under
        the same clip name play together as one clip in the engines. Make loops end on the value they start with; for a
        continuous spin key 0 → ±2π with smooth=False (the wrap is seamless). The piece rests where the clip starts (its
        first key): a file opened without playing the clip shows it there too."""
        if path not in {"rotation_euler", "location", "scale"}:
            raise ModelError("animate path must be rotation_euler, location or scale")
        ad = obj.animation_data or obj.animation_data_create()
        ad.action = bpy.data.actions.new(f"{self._ascii(clip)}_{obj.name}")
        obj.rotation_mode = "XYZ"
        keys = sorted(keys, key=lambda k: k[0])
        # at rest the piece is where its clip starts: a lid keyed into place above a tin would otherwise sit at the
        # origin (inside the tin) in every viewer and engine that does not play the clip
        rest = tuple(keys[0][1]) if keys else tuple(getattr(obj, path))
        for frame, value in keys:
            setattr(obj, path, value)
            obj.keyframe_insert(path, frame=int(frame))
            self._frame_end = max(self._frame_end, int(frame))
        setattr(obj, path, rest)
        compat.set_interpolation(ad.action, "BEZIER" if smooth else "LINEAR", "EASE_IN_OUT" if smooth else None)
        compat.push_to_nla(obj, self._ascii(clip))
        setattr(obj, path, rest)
        bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, self._frame_end)
        return obj

    def fur(self, surface, *, length: float = 0.03, count: int = 5000, droop: float = 0.45, width: float = 0.55,
            seed: int = 0, at=None, radius: float = 0.1, facing=None, below: float | None = None,
            above: float | None = None):
        """Real fur: hair cards — small curved strips of strands standing on a piece and drooping under their weight,
        the way game artists make fur, manes and grass tufts. Each card takes the colour of the surface under it
        (painted regions included), so a pale belly grows pale fur. length = hair length in meters; count = cards on
        the pc tier (½ on mobile-high, ¼ on mobile-mid, none on mobile-low where the coat texture carries it);
        droop 0 = straight out, 1 = lying flat downward; width = card width relative to its length. Limit where it
        grows with at + radius (at snaps to the surface), facing, below / above (keep it off eyes, noses and paws). Uses one fur material with
        cutout alpha. Not in the low-poly look (returns None). Returns the fur piece — pass it to mg.join with the rest;
        mg.rig binds it too."""
        if self._faceted or self.level == 0:
            return None
        import bisect
        from mathutils.bvhtree import BVHTree
        self._bake(surface)
        n = max(1, round(count * {3: 1.0, 2: 0.5, 1: 0.25}[self.level]))
        rng = random.Random(seed * 104729 + 7)
        sm = surface.data
        off = surface.location
        if at is not None and sm.polygons:   # a zone centre lands on the surface (it is easy to aim inside the body)
            bvh = BVHTree.FromPolygons([tuple(v.co + off) for v in sm.vertices], [tuple(p.vertices) for p in sm.polygons])
            hit = bvh.find_nearest(Vector(at))
            if hit and hit[0] is not None:
                at = tuple(hit[0])
        sm.calc_loop_triangles()
        uv = sm.uv_layers.active.data if sm.uv_layers else None
        from .finish import PAINT_ATTR
        soft = sm.color_attributes.get(PAINT_ATTR) if hasattr(sm, "color_attributes") else None
        cell_rgb = {tuple(round(x, 4) for x in self._cell_uv(nm)): c["rgb"] for nm, c in self._colors.items()}
        tris = []
        for lt in sm.loop_triangles:
            a, b, c = (sm.vertices[i].co + off for i in lt.vertices)
            nrm = (b - a).cross(c - a)
            area = nrm.length / 2
            if area <= 0:
                continue
            nrm.normalize()
            cen = (a + b + c) / 3
            if at is not None and (cen - Vector(at)).length > radius:
                continue
            if facing is not None and nrm.dot(Vector(facing).normalized()) < 0.35:
                continue
            if (below is not None and cen.z > below) or (above is not None and cen.z < above):
                continue
            rgb = cell_rgb.get(tuple(round(x, 4) for x in uv[lt.loops[0]].uv), (0.5, 0.5, 0.5)) if uv else (0.5, 0.5, 0.5)
            if soft is not None:   # the soft paint layer over the palette colour, as the bake mixes it
                col = [0.0, 0.0, 0.0, 0.0]
                for vi in lt.vertices:
                    col = [x + y / 3 for x, y in zip(col, soft.data[vi].color)]
                lin = [_linear(x) for x in rgb]
                rgb = tuple(_srgb(lin[k] * (1 - col[3]) + col[k] * col[3]) for k in range(3))
            tris.append((a, b, c, nrm, area, rgb))
        if not tris:
            raise ModelError("fur found no surface to grow on — check at / radius / facing / heights")
        cum, acc = [], 0.0
        for t in tris:
            acc += t[4]
            cum.append(acc)
        verts, faces, uvs, cols = [], [], [], []
        down = Vector((0, 0, -1))
        for _ in range(n):
            a, b, c, nrm, _area, rgb = tris[min(bisect.bisect_left(cum, rng.random() * acc), len(tris) - 1)]
            u, v = rng.random(), rng.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            root = a + (b - a) * u + (c - a) * v - nrm * length * 0.08
            L = length * rng.uniform(0.7, 1.3)
            side = nrm.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))).normalized()
            if side.length < 1e-6:
                side = nrm.orthogonal().normalized()
            w = L * width * rng.uniform(0.8, 1.2)
            d0 = nrm
            d1 = (nrm * (1 - droop) + down * droop + side.cross(nrm) * rng.uniform(-0.2, 0.2)).normalized()
            spine = [root, root + d0 * L * 0.35, root + d0 * L * 0.35 + d1 * L * 0.65]
            base = len(verts)
            for i, q in enumerate(spine):
                half = w * (0.5 - 0.15 * i)   # narrower toward the tips
                verts += [tuple(q - side * half), tuple(q + side * half)]
                uvs += [(0.0, i / 2), (1.0, i / 2)]
                shade = (0.5, 0.88, 1.12)[i]   # a dark undercoat at the roots, sun-bleached tips
                tone = tuple(min(1.0, c * shade) for c in rgb)
                cols += [tone, tone]
            for i in range(2):
                k = base + i * 2
                faces.append((k, k + 1, k + 3, k + 2))
        me = bpy.data.meshes.new("fur")
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uvl.data[li].uv = uvs[vi]
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        for i, c in enumerate(cols):
            ca.data[i].color = [_linear(x) for x in c] + [1.0]
        for poly in me.polygons:
            poly.use_smooth = True
        me.materials.append(self._fur_material())
        obj = bpy.data.objects.new("fur", me)
        obj["meshgate_cards"] = True
        bpy.context.collection.objects.link(obj)
        return obj

    def _fur_material(self):
        """One cutout material for every fur card: a strand texture (alpha = the strands), tinted by vertex colour."""
        mat = bpy.data.materials.get(f"{self._name}_fur")
        if mat:
            return mat
        px = 128
        img = bpy.data.images.new(f"{self._name}_fur_strands", px, px, alpha=True)
        rng = random.Random(11)
        data = [0.0] * (px * px * 4)
        for _ in range(80):   # strands: thin, tapering, of varied length and tone
            x0 = rng.uniform(0.03, 0.97) * px
            top = rng.uniform(0.5, 1.0)
            lean = rng.uniform(-0.1, 0.1) * px
            tone = rng.uniform(0.8, 1.0)
            for y in range(px):
                t = y / (px - 1)
                if t > top:
                    break
                half = 1.05 * (1 - t / top) + 0.3
                xc = x0 + lean * t * t
                shade = tone * (0.75 + 0.25 * t)
                for x in range(max(0, int(xc - half - 1)), min(px, int(xc + half + 2))):
                    cov = max(0.0, min(1.0, half + 0.5 - abs(x + 0.5 - xc)))
                    if cov > 0:
                        i = (y * px + x) * 4
                        data[i:i + 4] = [shade, shade, shade, max(data[i + 3], cov)]
        img.pixels = data
        img.pack()
        mat = bpy.data.materials.new(f"{self._name}_fur")
        mat.use_nodes = True
        mat.use_backface_culling = False   # cards are seen from both sides
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = "CLIP"
                mat.alpha_threshold = 0.5
            except (TypeError, AttributeError):
                pass
        nt = mat.node_tree
        pb = compat.principled(mat)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        mul = nt.nodes.new("ShaderNodeMix") if bpy.app.version >= (3, 4, 0) else nt.nodes.new("ShaderNodeMixRGB")
        if mul.bl_idname == "ShaderNodeMix":
            mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
            mul.inputs[0].default_value = 1.0
            nt.links.new(tex.outputs["Color"], mul.inputs[6])
            nt.links.new(vc.outputs["Color"], mul.inputs[7])
            nt.links.new(mul.outputs[2], pb.inputs["Base Color"])
        else:
            mul.blend_type, mul.inputs[0].default_value = "MULTIPLY", 1.0
            nt.links.new(tex.outputs["Color"], mul.inputs[1])
            nt.links.new(vc.outputs["Color"], mul.inputs[2])
            nt.links.new(mul.outputs[0], pb.inputs["Base Color"])
        cut = nt.nodes.new("ShaderNodeMath")   # the glTF exporter reads a Round on alpha as a cutout (alphaMode MASK)
        cut.operation = "ROUND"
        nt.links.new(tex.outputs["Alpha"], cut.inputs[0])
        nt.links.new(cut.outputs[0], pb.inputs["Alpha"])
        pb.inputs["Roughness"].default_value = 0.85
        return mat

    # ------------------------------------------------------------------ characters: a skeleton and clips

    def rig(self, body, joints: dict, *, tail=None, mirror: bool = True):
        """Give a character a skeleton the engines can animate (Unity Humanoid / Mixamo bone names), bound to `body` —
        the joined character mesh, so call it after mg.join. joints = world points in meters:
          "hips", "chest", "neck", "head" (the skull's base), "head_top",
          "shoulder_l", "elbow_l", "hand_l", "hip_l", "knee_l", "ankle_l", "toe_l"
        optional "spine" (between hips and chest), "fingers_l" (the hand's tip) and "toe_end_l". The character's left
        is +X; the right side is mirrored unless you give "_r" joints too (mirror=False). tail = [(x, y, z), …] adds a
        tail chain (Tail1, Tail2, …). The body bends smoothly (automatic weights); small separate pieces — eyes, a
        collar, whiskers, claws — follow their nearest bone rigidly. Model the arms relaxed: with the A-pose or T-pose
        setting the rig raises them into that pose itself. Returns the armature; add clips with mg.clip."""
        need = ["hips", "chest", "neck", "head", "head_top", "shoulder_l", "elbow_l", "hand_l", "hip_l", "knee_l",
                "ankle_l", "toe_l"]
        missing = [k for k in need if k not in joints]
        if missing:
            raise ModelError(f"rig: missing joints {', '.join(missing)}")
        J = {k: Vector(v) for k, v in joints.items()}
        J.setdefault("spine", (J["hips"] + J["chest"]) / 2)
        J.setdefault("fingers_l", J["hand_l"] + (J["hand_l"] - J["elbow_l"]) * 0.35)
        toe_dir = J["toe_l"] - J["ankle_l"]
        toe_dir.z = 0
        J.setdefault("toe_end_l", J["toe_l"] + (toe_dir.normalized() * max(toe_dir.length * 0.4, 0.01) if toe_dir.length else Vector((0, -0.02, 0))))
        for k in list(J):
            if k.endswith("_l") and (mirror or k[:-2] + "_r" not in J):
                J.setdefault(k[:-2] + "_r", Vector((-J[k].x, J[k].y, J[k].z)))
        bones = [("Hips", "hips", "spine", None), ("Spine", "spine", "chest", "Hips"), ("Chest", "chest", "neck", "Spine"),
                 ("Neck", "neck", "head", "Chest"), ("Head", "head", "head_top", "Neck")]
        for side, s_ in (("Left", "_l"), ("Right", "_r")):
            sh = J["chest"] + (J["shoulder" + s_] - J["chest"]) * 0.3
            sh.z = J["shoulder" + s_].z
            J["clavicle" + s_] = sh
            bones += [(f"{side}Shoulder", "clavicle" + s_, "shoulder" + s_, "Chest"),
                      (f"{side}UpperArm", "shoulder" + s_, "elbow" + s_, f"{side}Shoulder"),
                      (f"{side}LowerArm", "elbow" + s_, "hand" + s_, f"{side}UpperArm"),
                      (f"{side}Hand", "hand" + s_, "fingers" + s_, f"{side}LowerArm"),
                      (f"{side}UpperLeg", "hip" + s_, "knee" + s_, "Hips"),
                      (f"{side}LowerLeg", "knee" + s_, "ankle" + s_, f"{side}UpperLeg"),
                      (f"{side}Foot", "ankle" + s_, "toe" + s_, f"{side}LowerLeg"),
                      (f"{side}Toes", "toe" + s_, "toe_end" + s_, f"{side}Foot")]
        chain = [Vector(t) for t in (tail or [])]
        for i in range(len(chain) - 1):
            J[f"tail{i}"], J[f"tail{i + 1}"] = chain[i], chain[i + 1]
            bones.append((f"Tail{i + 1}", f"tail{i}", f"tail{i + 1}", "Hips" if i == 0 else f"Tail{i}"))
        self._bake(body)
        if self._faceted or self.level == 0:   # big faces bend only where they have vertices: rings at hips, spine, chest
            self._rings(body, [J[k].z for k in ("hips", "spine", "chest", "neck")])
        self._joint_loops(body, [J[k] for k in J if k.split("_")[0] in ("shoulder", "elbow", "hand", "hip", "knee", "ankle",
                                                                          "neck", "chest", "spine")])
        data = bpy.data.armatures.new(f"{self._name}_rig")
        arm = bpy.data.objects.new(f"{self._name}_rig", data)
        bpy.context.collection.objects.link(arm)
        bpy.context.view_layer.update()
        for o in bpy.context.view_layer.objects:
            o.select_set(o is arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for name, a, b, parent in bones:
            eb = data.edit_bones.new(name)
            eb.head, eb.tail = J[a], J[b]
            if (eb.tail - eb.head).length < 1e-4:
                eb.tail = eb.head + Vector((0, 0, 0.01))
            if parent:
                eb.parent = data.edit_bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        # bind: Blender's automatic (heat) weights on the body, then tidy up
        for o in bpy.context.view_layer.objects:
            o.select_set(o in (arm, body))
        bpy.context.view_layer.objects.active = arm
        try:
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        except RuntimeError as exc:   # heat weighting can refuse a mesh; the distance blend below covers it
            print(f"MeshGate rig: automatic weights unavailable ({exc})")
        if body.parent is not arm:
            body.parent = arm
        if not any(m.type == "ARMATURE" for m in body.modifiers):
            body.modifiers.new("rig", "ARMATURE").object = arm
        for name, *_ in bones:
            if name not in body.vertex_groups:
                body.vertex_groups.new(name=name)
        self._tidy_weights(body, arm)
        self._bind_cards(body, arm)
        self._set_pose(arm)
        self._rig = arm
        return arm

    def _set_pose(self, arm) -> None:
        """A-pose / T-pose: raise the arms, straight, into the chosen pose and make that the rest pose — the meshes are
        deformed into it and the bones moved, so the file's bind pose is the A or T the engines' retargeting expects.
        The rotations are kept (_pose_c): clips still play as they were designed, from the modelled pose."""
        from mathutils import Quaternion
        if self._pose == "none":
            return
        drop = math.radians(ARM_DROP[self._pose])
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        for side, sx in (("Left", 1), ("Right", -1)):
            want = Vector((sx * math.cos(drop), 0.0, -math.sin(drop)))
            acc = Quaternion()   # what the bones above have turned (the collarbone stays)
            for name in (f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"):
                b = arm.data.bones.get(name)
                if b is None:
                    break
                d = (b.tail_local - b.head_local).normalized()
                q = d.rotation_difference(acc.inverted() @ want)
                rest = b.matrix_local.to_quaternion()
                arm.pose.bones[name].rotation_quaternion = rest.inverted() @ q @ rest
                acc = acc @ q
                self._pose_c[name] = acc.copy()
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        for o in list(bpy.data.objects):   # every mesh the skeleton moves takes the new pose as its shape
            if o.type != "MESH" or not any(m.type == "ARMATURE" and m.object is arm for m in o.modifiers):
                continue
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            co = [0.0] * (3 * len(me.vertices))
            me.vertices.foreach_get("co", co)
            ev.to_mesh_clear()
            if len(co) == 3 * len(o.data.vertices):
                o.data.vertices.foreach_set("co", co)
                o.data.update()
        posed = {name: arm.pose.bones[name].matrix.copy() for name in self._pose_c}
        for o in bpy.context.view_layer.objects:
            o.select_set(o is arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for name, m in posed.items():
            arm.data.edit_bones[name].matrix = m
        bpy.ops.object.mode_set(mode="OBJECT")
        for pb in arm.pose.bones:
            pb.rotation_quaternion = Quaternion()

    @staticmethod
    def _rings(body, heights) -> None:
        """Cut the mesh across at these world heights (edge rings round the body), the loops a low-poly character's
        torso needs to bend at the spine; a cut across a flat face leaves it flat."""
        import bmesh
        me = body.data
        bm = bmesh.new()
        bm.from_mesh(me)
        off = body.matrix_world.translation.z
        for z in sorted(set(round(h, 4) for h in heights)):
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=(0, 0, z - off), plane_no=(0, 0, 1))
        bm.to_mesh(me)
        bm.free()
        me.update()

    def _bind_cards(self, body, arm):
        """Fur cards on the body follow the skeleton: each card vertex copies the weights of the nearest body vertex."""
        from mathutils.kdtree import KDTree
        cards = [c for c in bpy.data.objects if c.get("meshgate_cards") and c.parent is body]
        if not cards:
            return
        bm = body.matrix_world
        tree = KDTree(len(body.data.vertices))
        for v in body.data.vertices:
            tree.insert(bm @ v.co, v.index)
        tree.balance()
        names = {g.index: g.name for g in body.vertex_groups}
        for c in cards:
            mw = c.matrix_world.copy()
            c.parent = arm
            c.matrix_world = mw
            c.modifiers.new("rig", "ARMATURE").object = arm
            groups = {}
            for v in c.data.vertices:
                _, idx, _ = tree.find(mw @ v.co)
                for g in body.data.vertices[idx].groups:
                    name = names[g.group]
                    grp = groups.get(name) or c.vertex_groups.get(name) or c.vertex_groups.new(name=name)
                    groups[name] = grp
                    grp.add([v.index], g.weight, "REPLACE")

    def _joint_loops(self, body, joints) -> None:
        """More edge loops where a character bends — shoulders, elbows, wrists, hips, knees, ankles, neck — so the mesh
        folds instead of collapsing, the way an animator's topology is built. Within the tier's budget."""
        import bmesh
        if self.level < 1:
            return
        me = body.data
        total = sum(len(p.vertices) - 2 for p in me.polygons)
        if self._max_tris and total > 0.7 * self._max_tris:
            return
        from mathutils.bvhtree import BVHTree
        off = body.location
        bvh = BVHTree.FromPolygons([tuple(v.co + off) for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        spots = []
        for j in joints:
            hit = bvh.find_nearest(j)
            if hit and hit[0] is not None:
                spots.append((j, max(hit[3] * 1.4, 0.01)))   # about the limb's thickness around the joint
        bm = bmesh.new()
        bm.from_mesh(me)
        _tidy_bm(bm)
        # only the pieces a joint lies in bend there: a belly patch or a collar over a joint keeps its own smooth surface
        bm.verts.index_update()
        cos = [tuple(v.co + off) for v in bm.verts]
        seen, bending = set(), set()
        for f in bm.faces:
            if f in seen:
                continue
            stack, faces = [f], []
            seen.add(f)
            while stack:
                g = stack.pop()
                faces.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h not in seen:
                            seen.add(h)
                            stack.append(h)
            if self._inside_of(cos, [tuple(v.index for v in g.verts) for g in faces], [Vector(j) for j in joints]):
                bending.update(v for g in faces for v in g.verts)
        edges = [e for e in bm.edges if e.is_manifold and e.verts[0] in bending
                 and any(((e.verts[0].co + e.verts[1].co) / 2 + off - c).length < r for c, r in spots)]
        if edges and (not self._max_tris or total + len(edges) * 2 < 0.85 * self._max_tris):
            # low-poly: the new loops stay in their faces — moved vertices would break the flat facets into crumples
            _split_edges(bm, edges, smooth=0.0 if self._faceted else 0.5)
            bm.to_mesh(me)
            me.update()
        bm.free()

    @staticmethod
    def _inside_of(cos, polys, points) -> set:
        """Indices of `points` inside the closed surface (cos, polys). Two tests must agree: the nearest face's side
        (unsure on the edges of thin pieces) and ray parity."""
        from mathutils.bvhtree import BVHTree
        if not polys:
            return set()
        bvh = BVHTree.FromPolygons(cos, polys)
        ray = Vector((0.1234, 0.3171, 0.9403)).normalized()   # skewed so it rarely runs along an edge
        found = set()
        for n_, q in enumerate(points):
            hit = bvh.find_nearest(q)
            if hit[0] is None or (q - hit[0]).dot(hit[1]) >= 0:
                continue
            hits, origin = 0, q.copy()
            for _ in range(64):
                h = bvh.ray_cast(origin, ray)
                if h[0] is None:
                    break
                hits += 1
                origin = h[0] + ray * 1e-6
            if hits % 2 == 1:
                found.add(n_)
        return found

    @staticmethod
    def _bones_inside(me, mw, verts, segs) -> set:
        """Names of the bones whose segment passes through the closed piece made of `verts` (world space)."""
        keep = set(verts)
        polys = [tuple(p.vertices) for p in me.polygons if p.vertices[0] in keep]
        cos = [tuple(mw @ v.co) for v in me.vertices]
        ts = (0.2, 0.35, 0.5, 0.65, 0.8)
        pts = [a.lerp(b, t) for _, a, b in segs for t in ts]
        hit = Kit._inside_of(cos, polys, pts)
        return {segs[k // len(ts)][0] for k in hit}

    @staticmethod
    def _smooth_weights(body, verts, ours, rounds: int = 4) -> None:
        """Soften the weights across the skin (each vertex blends toward its neighbours), the way a rigger smooths
        automatic weights: joints then bend in a soft curve in every engine, instead of creasing where one bone's
        weight stops (Blender's Corrective Smooth would only help inside Blender)."""
        me = body.data
        keep = set(verts)
        if not keep:
            return
        nbr: dict = {i: [] for i in keep}
        for e in me.edges:
            a, b = e.vertices
            if a in keep and b in keep:
                nbr[a].append(b)
                nbr[b].append(a)
        w = {i: {g.group: g.weight for g in me.vertices[i].groups if g.group in ours} for i in keep}
        for _ in range(rounds):
            new = {}
            for i, ns in nbr.items():
                if not ns:
                    new[i] = w[i]
                    continue
                acc = {gi: x * 0.5 for gi, x in w[i].items()}
                for j in ns:
                    for gi, x in w[j].items():
                        acc[gi] = acc.get(gi, 0.0) + x * 0.5 / len(ns)
                new[i] = acc
            w = new
        groups = body.vertex_groups
        for i, ws in w.items():
            for gi in ours:
                if gi not in ws:
                    groups[gi].remove([i])
            for gi, x in ws.items():
                groups[gi].add([i], x, "REPLACE")

    def _tidy_weights(self, body, arm):
        """Weights a game character can use: pieces a bone runs through follow those bones, pieces stuck onto them take
        the weights of the surface under them, anything left over blends its nearest bones; ≤ 4 bones per vertex."""
        me = body.data
        n = len(me.vertices)
        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for e in me.edges:
            a, b = find(e.vertices[0]), find(e.vertices[1])
            if a != b:
                parent[a] = b
        islands: dict = {}
        for i in range(n):
            islands.setdefault(find(i), []).append(i)
        segs = [(b.name, arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones]
        idx = {g.name: g.index for g in body.vertex_groups}
        groups = body.vertex_groups
        mw = body.matrix_world
        ours = set(idx.values())
        # 1. pieces a bone runs through (the body, a limb, a head, a foot) keep their smooth heat weights, but only
        # from those bones: heat weights also reach across a gap, and a collar then stretches whenever an arm moves
        attached = []
        hosts = []
        for verts in islands.values():
            inside = self._bones_inside(me, mw, verts, segs) if len(verts) >= 8 else set()
            if not inside:
                attached.append(verts)
                continue
            hosts.append(verts)
            allowed = {idx[b] for b in inside if b in idx}
            pool = [sg for sg in segs if sg[0] in inside]
            for g in groups:
                if g.index in ours and g.index not in allowed:
                    g.remove(verts)
            for i in verts:   # vertices the heat left out blend their nearest bones of the piece
                if sum(g.weight for g in me.vertices[i].groups if g.group in ours) > 1e-4:
                    continue
                c = mw @ me.vertices[i].co
                ds = sorted(((_seg_distance(c, s[1], s[2]), s[0]) for s in pool))
                near = [(d, b) for d, b in ds[:4] if d <= ds[0][0] * 1.6 + 0.004]
                ws = [(b, 1.0 / (d + 0.004) ** 4) for d, b in near]
                tot = sum(x for _, x in ws)
                for b, x in ws:
                    groups[b].add([i], x / tot, "REPLACE")
        # 2. pieces with no bone inside — a belly patch, whiskers, eyes, a nose, ears, a collar — take the weights of
        # the surface they sit on (as Blender's Data Transfer does): they bend with the body instead of each hanging
        # on one bone and sliding out of it when the body moves
        self._smooth_weights(body, [i for verts in hosts for i in verts], ours)   # before the copies: they match it
        if hosts and attached and self._faceted:
            # low-poly faces are big: split them into the triangles the engines will draw anyway, so a patch follows
            # the very surface that bends under it (a quad folds along one diagonal when the body moves)
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(me)
            bm.free()
            me.update()
        if hosts and attached:
            from mathutils.bvhtree import BVHTree
            from mathutils.interpolate import poly_3d_calc
            wv = [mw @ v.co for v in me.vertices]
            wts = [{g.group: g.weight for g in v.groups if g.group in ours and g.weight > 1e-4} for v in me.vertices]
            trees = []   # one per host piece: an attached piece follows only the piece it sits on
            for verts in hosts:
                keep = set(verts)
                polys = [tuple(p.vertices) for p in me.polygons if p.vertices[0] in keep]
                if polys:
                    trees.append((BVHTree.FromPolygons([tuple(c) for c in wv], polys), polys))
            for verts in attached:
                if not trees:
                    break
                pts = [wv[i] for i in verts]
                step = max(1, len(pts) // 200)
                tree, polys = min(trees, key=lambda t: min((t[0].find_nearest(q)[3] or 1e9) for q in pts[::step]))
                for g in groups:
                    g.remove(verts)
                # the weights of the surface point right under each vertex, blended across its face (not the nearest
                # corners: on a big low-poly face those belong to other bones and the piece would sink in)
                copied, dist = [], []
                for q in pts:
                    loc, _, fi, d = tree.find_nearest(q)
                    acc: dict = {}
                    if fi is not None:
                        poly = polys[fi]
                        bary = poly_3d_calc([wv[i] for i in poly], loc)
                        for i, b in zip(poly, bary):
                            for gi, w in wts[i].items():
                                acc[gi] = acc.get(gi, 0.0) + w * b
                    tot = sum(acc.values()) or 1.0
                    copied.append({gi: w / tot for gi, w in acc.items() if w > 1e-5})
                    dist.append(d or 0.0)
                if max(dist) > 0.02:
                    # it stands off the surface (a collar, an eye, a whisker, a bell): a rigid accessory — the whole
                    # piece follows the weights where it touches, so it moves and never bends out of shape
                    touch = [c for c, d in zip(copied, dist) if d <= min(dist) + 0.01]
                    avg: dict = {}
                    for c in touch:
                        for gi, w in c.items():
                            avg[gi] = avg.get(gi, 0.0) + w / len(touch)
                    copied = [avg] * len(verts)
                for i, c in zip(verts, copied):   # a patch lying on the body bends with it, vertex by vertex
                    for gi, w in c.items():
                        groups[gi].add([i], w, "REPLACE")
        elif attached:   # no piece holds a bone (an odd rig): each piece follows its nearest bone rigidly
            for verts in attached:
                c = sum((mw @ me.vertices[i].co for i in verts), Vector()) / len(verts)
                bone = min(segs, key=lambda s: _seg_distance(c, s[1], s[2]))[0]
                for g in groups:
                    g.remove(verts)
                groups[bone].add(verts, 1.0, "REPLACE")
        for v in me.vertices:
            gs = sorted(((g.group, g.weight) for g in v.groups if g.weight > 1e-4), key=lambda t: -t[1])
            keep, drop = gs[:self._max_influences], gs[self._max_influences:]
            for gi, _ in drop:
                groups[gi].remove([v.index])
            total = sum(w for _, w in keep)
            if total > 0:
                for gi, w in keep:
                    groups[gi].add([v.index], w / total, "REPLACE")

    def clip(self, name: str, motion, *, strength: float = 1.0):
        """An animation clip for the rigged character (mg.rig first). motion = a preset:
          "idle"        breathing and a slow sway, 2 s loop
          "zombie_walk" a stiff shamble in place: dragging legs, slumped chest, lolling head, arms out, 1.2 s loop
          "walk"        a plain walk in place with swinging arms, 1 s loop
          "attack"      a wind-up, a lunge and a double swipe, 1 s
          "hit"         a flinch back and recover, 0.7 s
        or your own keys: {frame: {"Bone": (x, y, z) degrees about the world X / Y / Z axes, …}, …} at 30 fps (the rest
        pose is (0, 0, 0); "Hips_move": (x, y, z) meters moves the whole body). Bone names as in mg.rig: Hips, Spine,
        Chest, Neck, Head, LeftUpperArm, LeftLowerArm, LeftHand, LeftUpperLeg, LeftLowerLeg, LeftFoot (Right…),
        Tail1…. strength scales a preset. Loops end on their first pose."""
        from mathutils import Euler, Quaternion
        arm = getattr(self, "_rig", None)
        if arm is None:
            raise ModelError("clip: call mg.rig(body, joints) first")
        keys = _preset(motion, [b.name for b in arm.data.bones], float(strength)) if isinstance(motion, str) else motion
        if not keys:
            raise ModelError(f"clip: unknown motion {motion!r} — use idle, zombie_walk, walk, attack, hit or keys")
        posed = self._pose_c   # A-pose / T-pose rigs: bone → how far it was raised from the modelled pose
        if motion == "zombie_walk":   # arms modelled hanging at the sides: a zombie holds them out in front
            for side in ("Left", "Right"):
                b = arm.data.bones.get(f"{side}UpperArm")
                if b is None:
                    continue
                d = (b.tail_local - b.head_local).normalized()
                if b.name in posed:
                    d = posed[b.name].inverted() @ d   # the direction it was modelled in
                if d.z > -0.5:
                    continue
                for f in keys:
                    x, y, z = keys[f].get(f"{side}UpperArm", (0, 0, 0))
                    keys[f][f"{side}UpperArm"] = (x - 80 * float(strength), y, z)
        ad = arm.animation_data or arm.animation_data_create()
        ad.action = bpy.data.actions.new(f"{self._ascii(name)}_{arm.name}")
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        frames = sorted(int(f) for f in keys)
        used = {b for f in frames for b in keys[f]} | set(posed)   # raised arms are keyed back down too
        for f in frames:
            pose = keys[f]
            for bname in used:
                if bname == "Hips_move":
                    pb = arm.pose.bones["Hips"]
                    rest = pb.bone.matrix_local.to_3x3()
                    pb.location = rest.inverted() @ Vector(pose.get(bname, (0, 0, 0)))
                    pb.keyframe_insert("location", frame=f)
                    continue
                pb = arm.pose.bones.get(bname)
                if pb is None:
                    continue
                rot = pose.get(bname, (0, 0, 0))
                q_world = Euler([math.radians(a) for a in rot], "XYZ").to_quaternion()
                if bname in posed:   # the motion as designed, from the modelled pose: undo the raise, then move
                    up = posed.get(pb.parent.name, Quaternion()) if pb.parent else Quaternion()
                    q_world = up @ q_world @ posed[bname].inverted()
                rest = pb.bone.matrix_local.to_quaternion()
                pb.rotation_quaternion = rest.inverted() @ q_world @ rest
                pb.keyframe_insert("rotation_quaternion", frame=f)
            self._frame_end = max(self._frame_end, f)
        compat.set_interpolation(ad.action, "BEZIER", "EASE_IN_OUT")
        compat.push_to_nla(arm, self._ascii(name))
        for pb in arm.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = (0, 0, 0)
        bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, self._frame_end)
        return arm

    # ------------------------------------------------------------------ ready-made models and painting

    def model(self, uid: str, color, *, size: float, loc=(0, 0, 0), turn: float = 0.0, axis: str = "longest",
              smooth: bool = True, keep=None, drop=None, detail: float = 1.0):
        """A free model from the MeshGate library as one piece to rework — take a good base and make it yours: repaint
        it (paint), sculpt it (sculpt), cut it, add parts. uid = a model id from `meshgate.py library search`
        (downloaded first with `meshgate.py library get <uid>`); its author and licence are credited in the result.
        size = meters along `axis` ("longest", "height", "length" = Y, "width" = X); turn = degrees about Z so its
        front faces -Y. The model stands on z = 0 centred on loc (x, y), in its rest pose, painted in `color` (its own
        textures are dropped: repaint regions with paint). Take only part of it — a head, a paw, a wing — with
        keep = ((x1, y1, z1), (x2, y2, z2)), a box in the placed model's meters: faces outside it go; drop = a box whose
        faces go. Sink the cut edge into another piece of yours (the open neck of a head into a body). Dense models are
        thinned to the tier (about 2k triangles on mobile-low up to 60k on pc; detail multiplies it). Returns the piece."""
        import json as _json
        base = os.environ.get("MESHGATE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".meshgate")
        uid = str(uid).strip()
        folder = os.path.join(base, "library", uid)
        try:
            credit = _json.load(open(os.path.join(folder, "credit.json"), encoding="utf-8"))
        except (OSError, ValueError):
            raise ModelError(f"model '{uid}' is not in the library — run: meshgate.py library get {uid}") from None
        path = os.path.join(folder, credit["file"])
        before = set(bpy.data.objects)
        ext = os.path.splitext(path)[1].lower()
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        else:
            raise ModelError(f"model '{uid}': {ext} files are not supported here")
        new = [o for o in bpy.data.objects if o not in before]
        for arm in [o for o in new if o.type == "ARMATURE"]:
            arm.data.pose_position = "REST"   # the modelled shape, not a frame of a clip
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        pieces = []
        for o in [o for o in new if o.type == "MESH"]:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))   # modifiers and rest pose applied
            me.transform(o.matrix_world)
            pieces.append(me)
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.context.view_layer.update()
        if not pieces:
            raise ModelError(f"model '{uid}' has no mesh")
        import bmesh
        bm = bmesh.new()
        for me in pieces:
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new("model")
        bm.to_mesh(me)
        bm.free()
        for layer in list(me.uv_layers):
            me.uv_layers.remove(layer)
        if turn:
            me.transform(Matrix.Rotation(math.radians(turn), 4, "Z"))
        xs, ys, zs = zip(*[v.co[:] for v in me.vertices])
        dims = {"width": max(xs) - min(xs), "length": max(ys) - min(ys), "height": max(zs) - min(zs)}
        ref = max(dims.values()) if axis == "longest" else dims.get(axis)
        if not ref:
            raise ModelError("axis must be 'longest', 'height', 'length' or 'width'")
        k = float(size) / ref
        centre = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, min(zs)))
        me.transform(Matrix.Translation(Vector(loc)) @ Matrix.Scale(k, 4) @ Matrix.Translation(-centre))
        if keep is not None or drop is not None:
            def inside(c, box):
                (a, b) = (Vector(box[0]), Vector(box[1]))
                return all(min(a[i], b[i]) <= c[i] <= max(a[i], b[i]) for i in range(3))
            bm = bmesh.new()
            bm.from_mesh(me)
            gone = [f for f in bm.faces if (keep is not None and not inside(f.calc_center_median(), keep))
                    or (drop is not None and inside(f.calc_center_median(), drop))]
            bmesh.ops.delete(bm, geom=gone, context="FACES")
            bm.to_mesh(me)
            bm.free()
            if not me.polygons:
                raise ModelError(f"model '{uid}': keep / drop left nothing — the boxes are in the placed model's meters")
        obj = bpy.data.objects.new(f"model_{uid[:6]}", me)
        bpy.context.collection.objects.link(obj)
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        target = {0: 2000, 1: 6000, 2: 20000, 3: 60000}[self.level] * max(0.1, float(detail)) * (0.5 if self._faceted else 1.0)
        if tris > target:   # a scan or a hero model: thin it to what the tier can carry
            dec = obj.modifiers.new("tier", "DECIMATE")
            dec.ratio = max(0.005, target / tris)
            self._apply_modifiers(obj)
        if smooth and not self._faceted and len(me.polygons) < 20000 and self._detail["subdiv"] > 0:
            sub = obj.modifiers.new("smooth", "SUBSURF")
            sub.levels = sub.render_levels = 1
            self._apply_modifiers(obj)
        self._fix_normals(obj)
        self._finish_piece(obj, color, smooth)
        self._credits = getattr(self, "_credits", [])
        if all(c.get("uid") != uid for c in self._credits):
            self._credits.append({k_: credit.get(k_) for k_ in ("uid", "name", "author", "author_url", "url", "license",
                                                                 "license_name", "license_url")})
        return obj

    def cast(self, obj, shape: str = "cube", factor: float = 0.5, *, axes: str = "xyz"):
        """Push a piece toward a pure shape — "cube" squares up a soft, clay-like blob (a head, a body, a boulder that
        should read as a block), "sphere" rounds it, "cylinder" makes it a column. factor 0…1 = how far (0.3–0.6 keeps
        its character); axes = which directions it acts along. Works best on pieces with enough vertices (blob, skin,
        subdivided parts). Returns the piece."""
        kinds = {"cube": "CUBOID", "sphere": "SPHERE", "cylinder": "CYLINDER"}
        if shape not in kinds:
            raise ModelError(f"cast shape {shape!r} — use cube, sphere or cylinder")
        self._bake(obj)
        m = obj.modifiers.new("cast", "CAST")
        m.cast_type = kinds[shape]
        m.factor = max(0.0, min(1.0, float(factor)))
        m.use_x, m.use_y, m.use_z = ("x" in axes, "y" in axes, "z" in axes)
        m.use_radius_as_size = False
        self._apply_modifiers(obj)
        return obj

    def symmetrize(self, obj, keep: str = "+x"):
        """Make a piece exactly mirror-symmetric left to right about x = 0 — after sculpt noise, a cut or scattered
        detail that should match on both sides of a face or a body. keep = the side copied over the other ("+x" is
        the character's left, "-x" its right). Returns the piece."""
        import bmesh
        if keep not in ("+x", "-x"):
            raise ModelError("symmetrize keep= '+x' or '-x'")
        self._bake(obj)
        off = obj.location.x
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        _tidy_bm(bm)
        for v in bm.verts:   # the mirror plane is the world's x = 0, not the piece's own origin
            v.co.x += off
        bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X" if keep == "+x" else "-X",
                             dist=1e-4)
        for v in bm.verts:
            v.co.x -= off
        bm.to_mesh(me)
        bm.free()
        me.update()
        return obj

    def bounds(self, obj):
        """The piece's real box in world meters as ((min x, min y, min z), (max x, max y, max z)) — measure instead of
        guessing: a subdivided or bevelled part ends inside the box you asked for, so put a face's eyes and nose on
        its measured front (min y), a hat on its measured top. Works on groups too."""
        lo, hi = self._box(obj)
        return tuple(round(c, 5) for c in lo), tuple(round(c, 5) for c in hi)

    def patch(self, on, color, at, size, *, facing=(0, -1, 0), thickness: float = 0.006, dome: float = 0.0,
              smooth: bool = True):
        """A marking with crisp edges that lies ON a piece's surface and follows its curve — a white belly or chest, a
        bib, a face mask, a patch of moss, a label on a bottle, a bandage. Unlike a flattened sphere set on the body it
        never sticks out at its edges: the oval is projected onto `on` along `facing`. at = its centre (x, y, z), size =
        (width, height) of the oval in meters as seen from `facing` (the side it is on: (0, -1, 0) the front, (0, 0, 1)
        the top); thickness = how far it stands off the surface in the middle (its rim a third of that); dome = an
        extra bulge in the middle in meters (a round belly). Put it in the parts list like any piece."""
        from mathutils.bvhtree import BVHTree
        f = Vector(facing)
        if f.length < 1e-9:
            raise ModelError("patch: facing must be a direction such as (0, -1, 0)")
        f.normalize()
        w, h = (float(size[0]) / 2, float(size[1]) / 2)
        if w <= 0 or h <= 0:
            raise ModelError("patch: size = (width, height), both above 0")
        self._bake(on)
        mw = on.matrix_world
        bvh = BVHTree.FromPolygons([tuple(mw @ v.co) for v in on.data.vertices], [tuple(p.vertices) for p in on.data.polygons])
        up = Vector((0, 0, 1)) if abs(f.z) < 0.9 else Vector((0, 1, 0))
        u = f.cross(up).normalized()
        v = u.cross(f).normalized()
        c = Vector(at)
        if self._faceted or self.level == 0:   # coarse faces are far from the true curve: stand clear of them
            thickness = max(thickness, 0.012)
        rings = max(2, round({0: 3, 1: 4, 2: 6, 3: 8}[self.level] * (0.5 if self._faceted else 1.0)))
        n = self.seg(24)
        if not self._faceted:   # a smooth body bulges between sparse samples and would poke through the patch
            rings, n = max(rings, 4), max(n, 16)
        reach = max(w, h) * 2 + 0.3
        rim = thickness / 3
        top, bottom = [], []
        missed = 0
        for i in range(rings + 1):
            r = i / rings
            for k in range(1 if i == 0 else n):
                a = 2 * math.pi * k / n
                p0 = c + u * (w * r * math.cos(a)) + v * (h * r * math.sin(a))
                hit = bvh.ray_cast(p0 + f * reach, -f)
                q = hit[0] if hit[0] is not None else None
                if q is None:
                    missed += 1
                    q = bvh.find_nearest(p0)[0] or p0
                lift = rim + (thickness - rim) * math.sqrt(max(0.0, 1 - r * r)) + dome * (1 - r * r)
                top.append(q + f * lift)
                bottom.append(q - f * max(0.003, thickness))   # sunk in, so no gap shows at the rim
        if missed > (rings * n) // 2:
            raise ModelError(f"patch: most of the oval misses the piece — put `at` on its surface, facing {tuple(facing)}")
        # the samples follow the piece's facets; relax the patch's top (not its rim) so it reads as one smooth shape
        rim0 = 1 + (rings - 1) * n
        nb = [[] for _ in top]
        for k in range(n):
            nb[0].append(1 + k)
            for i in range(1, rings + 1):
                a_ = 1 + (i - 1) * n + k
                for j in ((1 + (i - 1) * n + (k + 1) % n), (1 + (i - 1) * n + (k - 1) % n),
                          (0 if i == 1 else 1 + (i - 2) * n + k), (1 + i * n + k if i < rings else None)):
                    if j is not None:
                        nb[a_].append(j)
        for _ in range(6):
            top = [p if i >= rim0 or not nb[i] else p.lerp(sum((top[j] for j in nb[i]), Vector()) / len(nb[i]), 0.5)
                   for i, p in enumerate(top)]
        verts = [tuple(p) for p in top] + [tuple(p) for p in bottom]
        m = len(top)
        faces, flat = [], []

        def ring(i, k):
            return 0 if i == 0 else 1 + (i - 1) * n + k % n
        for k in range(n):
            faces.append((ring(0, 0), ring(1, k), ring(1, k + 1)))
            for i in range(1, rings):
                faces.append((ring(i, k), ring(i + 1, k), ring(i + 1, k + 1), ring(i, k + 1)))
        faces += [tuple(x + m for x in reversed(fc)) for fc in list(faces)]   # the underside
        for k in range(n):   # the rim wall
            a, b = ring(rings, k), ring(rings, k + 1)
            faces.append((a, a + m, b + m, b))
            flat.append(len(faces) - 1)
        obj = self._mesh("patch", verts, faces)
        self._fix_normals(obj)
        self._finish_piece(obj, color, smooth, flat)
        obj["meshgate_patch_on"] = on.name   # join melts it into `on` where the mesh is too coarse to carry it apart
        return obj

    def paint(self, obj, color, *, at=None, radius: float = 0.1, facing=None, below: float | None = None,
              above: float | None = None, rough: float = 0.0, seed: int = 0):
        """Paint a region of a piece in another palette colour, like a texture brush — a pale belly, dark stripes and
        patches, a pink nose, exposed flesh, wounds, glowing eyes, moss on the top of a stone, rust at the bottom.
        Faces are painted when all given conditions hold: within `radius` of `at` (x, y, z), facing a direction
        (facing = (x, y, z): faces whose normal points that way, e.g. (0, 0, -1) = the underside), below / above a
        height z. rough = 0…1 frays the edge of the region with noise (natural patches). World meters. Returns obj."""
        from mathutils import noise as mnoise
        self._bake(obj)
        name = self._color_name(color)
        u, v = self._cell_uv(name)
        me = obj.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        uv = me.uv_layers.active.data
        off = obj.location
        centre = Vector(at) if at is not None else None
        face = Vector(facing).normalized() if facing is not None else None
        jitter = Vector((seed * 7.3, seed * 1.9, seed * 4.1))
        painted = 0
        if self._soft_paint and not self._vertex:
            # baked finish: a soft colour layer carries the look; the palette cell (roughness, material) switches only
            # deep inside the region, where the layer already covers fully, so no face edge shows
            weights = self._soft_layer(obj, color, centre, radius, face, below, above, rough, jitter)
            for p in me.polygons:
                ws = [weights.get(i, 0.0) for i in p.vertices]
                if max(ws) > 0.0:
                    painted += 1
                if min(ws) >= 0.85:
                    for li in p.loop_indices:
                        uv[li].uv = (u, v)
            if not painted and self.level == 3:   # a small region may fall between the faces of a coarse tier
                raise ModelError(f"paint({color!r}) touched no faces — check at / radius / facing / heights")
            return obj
        if centre is not None and not self._faceted:
            # faces are painted whole, so on a sparse mesh the region's edge follows its facets (a ragged belly patch):
            # split the edges along the edge of the region first, so it comes out round
            band = max(radius * 0.2, 0.01)
            self._refine(obj, max(radius / 7, 0.004), rounds=3, near=lambda q: abs((q - centre).length - radius) < band)
            me = obj.data
            uv = me.uv_layers.active.data
        for p in me.polygons:
            c = p.center + off
            wobble = 1.0 + rough * 0.8 * mnoise.noise(c * (1.8 / max(radius, 0.01)) + jitter) if rough else 1.0
            if centre is not None and (c - centre).length > radius * wobble:
                continue
            if face is not None and p.normal.dot(face) < 0.35 - 0.3 * rough * mnoise.noise(c * 5 + jitter):
                continue
            if below is not None and c.z > below + rough * 0.03 * mnoise.noise(c * 6 + jitter):
                continue
            if above is not None and c.z < above + rough * 0.03 * mnoise.noise(c * 6 + jitter):
                continue
            for li in p.loop_indices:
                uv[li].uv = (u, v)
            painted += 1
        if not painted and self.level == 3:
            raise ModelError(f"paint({color!r}) touched no faces — check at / radius / facing / heights")
        return obj

    def _soft_layer(self, obj, color, centre, radius, face, below, above, rough, jitter):
        """The same region as a per-vertex colour whose alpha is 1 inside and fades out over a band past the edge;
        the bake mixes it over the palette so painted patches get soft edges. Only for baked finishes."""
        from mathutils import noise as mnoise
        from .finish import PAINT_ATTR
        me = obj.data
        layer = me.color_attributes.get(PAINT_ATTR) or _paint_layer(me)
        rgb = [_linear(x) for x in self._colors[self._color_name(color)]["rgb"]]
        band = max(radius * 0.25, 0.012) if centre is not None else 0.02
        off = obj.location
        data = layer.data
        weights = {}
        for vx in me.vertices:
            c = vx.co + off
            w = 1.0
            if centre is not None:
                edge = radius * (1.0 + rough * 0.8 * mnoise.noise(c * (1.8 / max(radius, 0.01)) + jitter) if rough else 1.0)
                w = min(w, max(0.0, min(1.0, (edge + band - (c - centre).length) / (2 * band))))
            if face is not None:
                w = min(w, max(0.0, min(1.0, (vx.normal.dot(face) - 0.15) / 0.4)))
            if below is not None:
                w = min(w, max(0.0, min(1.0, (below + band - c.z) / (2 * band))))
            if above is not None:
                w = min(w, max(0.0, min(1.0, (c.z - above + band) / (2 * band))))
            if w <= 0.0:
                continue
            old = data[vx.index].color
            a = w * w * (3 - 2 * w)
            weights[vx.index] = a
            keep = old[3] * (1 - a)
            total = keep + a
            data[vx.index].color = [(old[i] * keep + rgb[i] * a) / total for i in range(3)] + [min(1.0, total)]
        return weights

    def eye(self, center, radius: float, iris, *, look=(0, -1, 0), pupil: str = "slit", pupil_size: float = 0.35,
            sclera=None):
        """A proper eye, built the way an artist builds one: a glossy ball in the iris colour (or white with `sclera=`,
        for people), a dark ring round the iris, a lighter ring toward the pupil, and a pupil set slightly in, with
        depth — the glossy ball catches the light like a cornea. center = (x, y, z), radius in meters; look = the
        direction it faces (default the front, -Y); pupil = "slit" (cats, snakes), "bar" (goats: sideways) or
        "round"; pupil_size = its width against the iris (0.2 a thin slit … 0.7 wide open). Give the iris colour glow in
        mg.color for glowing eyes: the lighter inner ring glows brighter, the dark ring dimmer. Sit it in an eye socket.
        Returns the eye as one piece."""
        iname = self._color_name(iris)
        base = self._colors[iname]
        rgb, gl = base["rgb"], base["glow"]
        # one glow strength for every ring: the pattern is in the colours, so soft paint keeps the glow smooth too
        ring = self.color(f"{iname}_ring", tuple(c * 0.12 for c in rgb), rough=0.12, glow=gl)
        inner = self.color(f"{iname}_inner", tuple(c + (1 - c) * 0.45 for c in rgb), rough=0.08, glow=gl)
        iris_c = self.color(f"{iname}_gloss", rgb, rough=0.08, glow=gl)
        dark = self.color("eye_pupil", (0.02, 0.02, 0.025), rough=0.05)
        white = self._color_name(sclera) if sclera is not None else None
        r = float(radius)
        ball = self.part("sphere", white or iris_c, loc=(0, 0, 0), scale=(2 * r, 2 * r, 2 * r), smooth=True)
        edge, mid, core = (48, 40, 18) if white else (78, 64, 28)   # iris rings, degrees from the front
        chord = lambda deg: 2 * r * math.sin(math.radians(deg) / 2)   # noqa: E731 — distance on the ball from its front
        front = (0, -r, 0)
        if white:
            self.paint(ball, ring, at=front, radius=chord(edge))
            self.paint(ball, iris_c, at=front, radius=chord(edge - 5))
        else:
            self.paint(ball, ring, at=front, radius=chord(edge))
            self.paint(ball, iris_c, at=front, radius=chord(mid))
        self.paint(ball, inner, at=front, radius=chord(core))
        w = max(0.08, min(0.9, float(pupil_size))) * r
        if pupil == "round":
            pup = self.part("sphere", dark, loc=(0, -r * 0.93, 0), scale=(w * 1.3, r * 0.2, w * 1.3), smooth=True)
        elif pupil == "bar":
            pup = self.part("sphere", dark, loc=(0, -r * 0.9, 0), scale=(r * 1.25, r * 0.22, w * 0.7), smooth=True)
        else:
            pup = self.part("sphere", dark, loc=(0, -r * 0.9, 0), scale=(w * 0.7, r * 0.22, r * 1.25), smooth=True)
        obj = self.join("eye", [ball, pup])
        d = Vector(look).normalized() if Vector(look).length > 1e-6 else Vector((0, -1, 0))
        turn = Vector((0, -1, 0)).rotation_difference(d).to_matrix().to_4x4()
        obj.data.transform(Matrix.Translation(Vector(center)) @ turn)
        obj.data.update()
        return obj

    # ------------------------------------------------------------------ sculpting: organic shapes

    def blob(self, shapes, color, *, blend: float = 1.0, detail: float = 1.0, smooth: bool = True):
        """Soft clay: balls, capsules and ellipsoids that melt into one smooth surface (Blender metaballs) — animal
        bodies and heads, paws, snouts, noses, cushions, rocks, clouds, dough. shapes = a list of dicts:
          {"ball": (x, y, z), "r": 0.2}                                   a sphere, r = its radius in meters
          {"capsule": ((x1, y1, z1), (x2, y2, z2)), "r": 0.08}            a rounded rod from point to point
          {"ellipsoid": (x, y, z), "size": (sx, sy, sz), "rot": (rx, ry, rz)}   half-sizes in meters, rot optional
        Add "cut": True to a shape to carve it away instead (eye sockets, a mouth, a hollow). Sizes are the visible sizes
        of each shape alone; where shapes touch or overlap they melt together — blend = how softly (0.5 tight … 2 very
        soft). Returns one smooth closed mesh whose density follows the tier (detail multiplies it). Refine it with
        sculpt(); keep hard-surface parts (a collar, a buckle, eyes) as ordinary parts."""
        import mathutils
        shapes = list(shapes)
        if not shapes:
            raise ModelError("blob() needs at least one shape")
        stiffness = min(10.0, max(0.5, 2.0 / max(blend, 0.05)))
        threshold = 0.6
        k = math.sqrt(1 - (threshold / stiffness) ** (1 / 3)) if threshold < stiffness else 0.5   # visible / field radius
        self._blobs = getattr(self, "_blobs", 0) + 1
        mb = bpy.data.metaballs.new(f"mgblob{self._blobs}")   # a unique base name: metaball families merge by name
        mb.threshold = threshold
        pts = []
        for sh in shapes:
            if "ball" in sh:
                el = mb.elements.new(type="BALL")
                el.co, el.radius = Vector(sh["ball"]), float(sh["r"]) / k
                pts += [Vector(sh["ball"]) + Vector((d, d, d)) * float(sh["r"]) for d in (-1, 1)]
            elif "capsule" in sh:
                a, b = (Vector(v) for v in sh["capsule"])
                el = mb.elements.new(type="CAPSULE")
                el.co, el.radius = (a + b) / 2, float(sh["r"]) / k
                el.size_x = max((b - a).length / 2, 1e-4)   # absolute half-length (the tube's straight part)
                el.rotation = (b - a).to_track_quat("X", "Z") if (b - a).length > 1e-6 else mathutils.Quaternion()
                pts += [a - Vector((sh["r"],) * 3), b + Vector((sh["r"],) * 3), a + Vector((sh["r"],) * 3), b - Vector((sh["r"],) * 3)]
            elif "ellipsoid" in sh:
                sx, sy, sz = (float(v) for v in sh["size"])
                m = max(sx, sy, sz, 1e-4)
                el = mb.elements.new(type="ELLIPSOID")
                el.co, el.radius = Vector(sh["ellipsoid"]), m / k
                el.size_x, el.size_y, el.size_z = sx / m, sy / m, sz / m
                el.rotation = mathutils.Euler(sh.get("rot", (0, 0, 0))).to_quaternion()
                pts += [Vector(sh["ellipsoid"]) + Vector((d * m,) * 3) for d in (-1, 1)]
            else:
                raise ModelError(f"blob shape {sh!r}: use a dict with 'ball', 'capsule' or 'ellipsoid'")
            el.stiffness = stiffness
            el.use_negative = bool(sh.get("cut"))
        extent = max((max(p[i] for p in pts) - min(p[i] for p in pts)) for i in range(3))
        cells = {0: 16, 1: 26, 2: 38, 3: 56}[self.level] * max(0.25, float(detail)) * (0.6 if self._faceted else 1.0)
        # never finer than the tier's smallest useful cell (in meters): a small blob must not cost as much as a body
        wanted = max(extent / cells, {0: 0.02, 1: 0.012, 2: 0.007, 3: 0.004}[self.level])
        thinnest = min((float(sh["r"]) if "r" in sh else min(float(v) for v in sh["size"])) for sh in shapes if not sh.get("cut"))
        res = max(min(wanted, thinnest * 0.6), 0.002)   # a grid coarser than a paw or an arm would lose it
        sculpted = not self._faceted   # the artist's route: a fine surface, smoothed, then clean retopology
        if sculpted:
            res = max(min(res, extent / 150, thinnest * 0.3), 0.0015)
        mb.resolution = mb.render_resolution = res
        obj = bpy.data.objects.new(f"mgblob{self._blobs}", mb)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        bpy.data.objects.remove(obj)
        bpy.data.metaballs.remove(mb)
        bpy.context.view_layer.update()
        if not me.polygons:
            raise ModelError("blob() made no surface — shapes too small, or all of them cut")
        out = bpy.data.objects.new(f"blob{self._blobs}", me)
        bpy.context.collection.objects.link(out)
        if sculpted:
            self._clean_clay(out, wanted)
        elif res < wanted * 0.8:   # built finer to keep thin parts: thin it back to the tier's density
            dec = out.modifiers.new("tier", "DECIMATE")
            dec.ratio = max(0.02, (res / wanted) ** 2)
            self._apply_modifiers(out)
        self._fix_normals(out)
        self._finish_piece(out, color, smooth)
        return out

    def _clean_clay(self, obj, cell: float, relax: bool = True) -> None:
        """Clay → a clean sculpt, the way artists finish one: relax the marching-cubes steps and the blend bulges while
        keeping the volume, then rebuild the surface as even quads at the tier's density (QuadriFlow retopology), and
        relax once more. Falls back to a decimate when QuadriFlow declines. relax=False keeps the shape's own edges (a
        union of soft blocks is already smooth where it should be)."""
        if relax:
            lap = obj.modifiers.new("relax", "LAPLACIANSMOOTH")
            lap.lambda_factor, lap.iterations = 0.6, 12
            lap.use_volume_preserve, lap.use_normalized = True, True
            self._apply_modifiers(obj)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        _tidy_bm(bm, cell * 50)   # QuadriFlow needs a clean, consistently facing surface
        broken = any(not e.is_manifold for e in bm.edges)
        bm.to_mesh(obj.data)
        bm.free()
        if broken:   # a cut shape can leave edges shared by 3 faces: a fine voxel remesh makes it one closed surface
            vox = obj.modifiers.new("watertight", "REMESH")
            vox.mode, vox.voxel_size, vox.adaptivity = "VOXEL", max(cell * 0.35, 0.0008), 0.0
            self._apply_modifiers(obj)
        area = sum(p.area for p in obj.data.polygons)
        target = max(120, int(area / (cell * cell)))   # quads of about the tier's cell size
        before = len(obj.data.polygons)
        ok = False
        if target < before:
            for o in bpy.context.view_layer.objects:
                o.select_set(o is obj)
            bpy.context.view_layer.objects.active = obj
            try:
                res = bpy.ops.object.quadriflow_remesh(target_faces=target, use_mesh_symmetry=False,
                                                       use_preserve_sharp=False, use_preserve_boundary=False,
                                                       smooth_normals=False, seed=0)
                polys = obj.data.polygons
                ok = "FINISHED" in res and len(polys) != before and \
                    sum(1 for p in polys if len(p.vertices) == 4) >= 0.9 * len(polys)
            except RuntimeError:
                ok = False
            if not ok:
                dec = obj.modifiers.new("tier", "DECIMATE")
                dec.ratio = max(0.02, target / max(before, 1))
                self._apply_modifiers(obj)
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                _tidy_bm(bm, cell * 50)   # a decimate can leave slivers behind
                bm.to_mesh(obj.data)
                bm.free()
        relax = obj.modifiers.new("relax", "LAPLACIANSMOOTH")
        relax.lambda_factor, relax.iterations = 0.35, 3
        relax.use_volume_preserve, relax.use_normalized = True, True
        self._apply_modifiers(obj)

    def skin(self, points, radii, color, *, edges=None, smooth: bool = True):
        """An organic body grown around a skeleton — limbs, tails, tentacles, necks, roots, branches, horns, snakes.
        points = [(x, y, z), …] in meters; radii = one radius per point (or a single number); edges = [(i, j), …]
        joining points (default: one chain in order). Branches are fine: a point may join three or more edges (a trunk
        forking into branches, a body with four legs). The result is smooth and closed; its density follows the tier."""
        pts = [Vector(p) for p in points]
        if len(pts) < 2:
            raise ModelError("skin() needs at least two points")
        rs = [float(radii)] * len(pts) if isinstance(radii, (int, float)) else [float(r) for r in radii]
        if len(rs) != len(pts):
            raise ModelError("skin(): give one radius per point")
        edges = [tuple(e) for e in (edges or [(i, i + 1) for i in range(len(pts) - 1)])]
        me = bpy.data.meshes.new("skin")
        me.from_pydata([tuple(p) for p in pts], edges, [])
        obj = bpy.data.objects.new("skin", me)
        bpy.context.collection.objects.link(obj)
        sk = obj.modifiers.new("skin", "SKIN")
        sk.use_smooth_shade = True
        for i, v in enumerate(me.skin_vertices[0].data):
            v.radius = (rs[i], rs[i])
            v.use_root = i == 0
        # the bare skin is square in section (a board); one level makes it eight-sided, which the low-poly look keeps
        sub = obj.modifiers.new("smooth", "SUBSURF")
        sub.levels = sub.render_levels = 1 if self._faceted else {0: 1, 1: 1, 2: 2, 3: 2}[self.level]
        self._apply_modifiers(obj)
        self._fix_normals(obj)
        self._finish_piece(obj, color, smooth)
        return obj

    def cut(self, target, cutter):
        """Carve `cutter` out of `target` (a boolean difference) — eye sockets, a paw print pressed into stone, windows,
        a notch, a broken edge. The cutter is any piece (part, blob, extrude…) and is used up: do not also put it in
        your parts list. Returns `target`."""
        self._bake(target)
        self._bake(cutter)
        mod = target.modifiers.new("cut", "BOOLEAN")
        mod.operation, mod.object = "DIFFERENCE", cutter
        if hasattr(mod, "solver"):
            mod.solver = "EXACT"
        self._apply_modifiers(target)
        self._forget(cutter)
        self._label(target)   # a boolean builds new geometry: mark it with the line of the cut
        return target

    def union(self, parts, *, fillet: float = 0.0, detail: float = 1.0):
        """Melt pieces into ONE closed mesh, the way a sculptor or a toy maker joins them — a head, a body, arms and legs
        of soft blocks; a trunk and its branches; a handle and a mug. The insides disappear, every piece keeps its
        colour, and fillet = the radius in meters of a smooth rounded blend along each seam (0.01–0.04 for a character):
        arms and a head grow out of the body instead of being stuck on it, and a rigged character bends there as one
        skin instead of its blocks pulling apart. The result is rebuilt as clean, even quads at the tier's density
        (detail scales it) on mobile-high and PC; lighter tiers and the low-poly look keep the boolean surface and crisp
        seams. Returns the one piece (the first
        of `parts`, grown); the others are used up — do not also put them in your parts list."""
        import bmesh
        from mathutils.kdtree import KDTree
        parts = [p for p in parts if p is not None]
        if not parts:
            raise ModelError("union needs pieces")
        base, others = parts[0], parts[1:]
        if not others:
            return base
        # every piece carries the same attributes (a paint layer on one of them, colours): a boolean fills a missing one
        # with whatever memory it finds, which soft paint then shows as blotches
        wanted = {}
        for o in parts:
            for at in o.data.attributes:
                if not at.name.startswith(".") and at.domain in ("POINT", "CORNER", "FACE") and at.name != "mg_piece" \
                        and at.data_type in ("FLOAT_COLOR", "BYTE_COLOR", "FLOAT", "INT", "FLOAT_VECTOR"):
                    wanted.setdefault(at.name, (at.domain, at.data_type))
        for o in parts:
            for name, (domain, kind) in wanted.items():
                if o.data.attributes.get(name) is None:
                    at = o.data.attributes.new(name, kind, domain)
                    width = {"FLOAT_COLOR": 4, "BYTE_COLOR": 4, "FLOAT_VECTOR": 3}.get(kind, 1)
                    key = "color" if "COLOR" in kind else ("vector" if kind == "FLOAT_VECTOR" else "value")
                    at.data.foreach_set(key, [0] * (width * len(at.data)) if kind == "INT" else [0.0] * (width * len(at.data)))
        for k, o in enumerate(parts):   # which piece every face came from: the seams are where two of them meet
            self._bake(o)
            attr = o.data.attributes.get("mg_piece") or o.data.attributes.new("mg_piece", "INT", "FACE")
            attr.data.foreach_set("value", [k] * len(o.data.polygons))
        coll = bpy.data.collections.new("mg_union")
        for o in others:
            coll.objects.link(o)
        mod = base.modifiers.new("union", "BOOLEAN")
        mod.operation, mod.operand_type, mod.collection = "UNION", "COLLECTION", coll
        if hasattr(mod, "solver"):
            mod.solver = "EXACT"
        self._apply_modifiers(base)
        for o in others:
            self._forget(o)
        bpy.data.collections.remove(coll)

        def seam_points():
            bm = bmesh.new()
            bm.from_mesh(base.data)
            lay = bm.faces.layers.int.get("mg_piece")
            pts = [base.matrix_world @ v.co for e in bm.edges if lay is not None and len(e.link_faces) == 2
                   and e.link_faces[0][lay] != e.link_faces[1][lay] for v in e.verts]
            bm.free()
            tree = KDTree(max(1, len(pts)))
            for i, q in enumerate(pts):
                tree.insert(q, i)
            tree.balance()
            return tree, len(pts)
        r = float(fillet)
        # rebuilt as fine quads with rounded seams where the tier has the polygons for it (mobile-high, PC); a lighter
        # tier's quads would be centimetres wide and turn a soft block into an octagon, so it keeps the boolean
        # surface of its own lighter pieces (and the low-poly look keeps it on every tier)
        if not self._faceted and self.level >= 2:
            self._remake_union(base, seam_points, r, float(detail))
        if base.data.attributes.get("mg_piece"):
            base.data.attributes.remove(base.data.attributes["mg_piece"])
        self._label(base)
        return base

    def _remake_union(self, obj, seam_points, fillet: float, detail: float) -> None:
        """The artist's route after a boolean: one watertight voxel surface, the seams relaxed into a rounded blend,
        clean quads at the tier's density (QuadriFlow), and every face's colour and paint taken back from the piece it
        lies on."""
        import bmesh
        from mathutils.bvhtree import BVHTree
        me = obj.data
        pts = [v.co.copy() for v in me.vertices]
        extent = max((max(p[k] for p in pts) - min(p[k] for p in pts)) for k in range(3)) if pts else 1.0
        cell = max(extent / ({0: 16, 1: 26, 2: 38, 3: 56}[self.level] * 1.8 * max(0.25, detail)),
                   {0: 0.02, 1: 0.012, 2: 0.007, 3: 0.004}[self.level])
        old = me.copy()   # the pieces' faces, with their colours, to read back from
        tree, count = seam_points()
        vox = obj.modifiers.new("watertight", "REMESH")
        vox.mode, vox.voxel_size, vox.adaptivity = "VOXEL", max(min(cell * 0.4, fillet * 0.3 if fillet else cell), 0.0015), 0.0
        if hasattr(vox, "use_smooth_shade"):
            vox.use_smooth_shade = True
        self._apply_modifiers(obj)
        mw = obj.matrix_world
        if fillet > 0 and count:   # relax the band round each seam: its crease fills in to a round blend
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            band = []
            for v in bm.verts:
                d = tree.find(mw @ v.co)[2]
                if d < fillet:
                    t = 1 - d / fillet
                    band.append((v, t * t * (3 - 2 * t)))
            for _ in range(int(max(6, min(30, fillet / max(cell * 0.4, 1e-4) * 3)))):
                moved = []
                for v, w in band:
                    ring = [e.other_vert(v).co for e in v.link_edges]
                    if ring:
                        moved.append((v, v.co.lerp(sum(ring, Vector()) / len(ring), 0.5 * w)))
                for v, co in moved:
                    v.co = co
            bm.to_mesh(obj.data)
            bm.free()
        self._clean_clay(obj, cell, relax=False)
        # colours back from the pieces: each new face takes the palette cell (UV), vertex colour and paint of the face
        # under it, each vertex the paint of the nearest old vertex
        bvh = BVHTree.FromPolygons([tuple(v.co) for v in old.vertices], [tuple(p.vertices) for p in old.polygons])
        me = obj.data
        ouv = old.uv_layers.active.data if old.uv_layers else None
        if ouv is not None:
            uv = me.uv_layers.get(old.uv_layers.active.name) or me.uv_layers.new(name=old.uv_layers.active.name)
        ocol = old.color_attributes.get("Col") if hasattr(old, "color_attributes") else None
        col = (me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")) if ocol else None
        for p in me.polygons:
            hit = bvh.find_nearest(p.center)
            if hit[2] is None:
                continue
            src = old.polygons[hit[2]]
            p.material_index = src.material_index
            for li in p.loop_indices:
                if ouv is not None:
                    uv.data[li].uv = ouv[src.loop_indices[0]].uv
                if col is not None:
                    col.data[li].color = ocol.data[src.loop_indices[0]].color
            p.use_smooth = src.use_smooth
        for name in [a.name for a in old.attributes if a.domain == "POINT" and a.data_type == "FLOAT_COLOR"]:
            oa = old.attributes[name]
            na = me.attributes.get(name) or me.attributes.new(name, "FLOAT_COLOR", "POINT")
            for v in me.vertices:
                hit = bvh.find_nearest(v.co)
                if hit[2] is None:
                    continue
                vs = old.polygons[hit[2]].vertices
                near = min(vs, key=lambda i: (old.vertices[i].co - v.co).length)
                na.data[v.index].color = oa.data[near].color
        if len(me.materials) < len(old.materials):
            for m in old.materials[len(me.materials):]:
                me.materials.append(m)
        bpy.data.meshes.remove(old)
        me.update()

    def bend(self, obj, angle: float, along: str = "Z", toward: str = "-Y"):
        """Bend a whole piece from its base — a curling tail, a drooping ear, a leaning trunk, a curved horn, a banana.
        along = the axis the piece's length runs along ("X", "Y", "Z", or "-Z" etc.: the base is at the low end of
        along, the tip at the high end); toward = where the tip curls ("-Y" = toward the front); angle = how far the
        tip turns, in radians (math.pi/2 = a right angle, math.pi = a U-turn). Extra rings are added so it bends
        smoothly. Returns the piece."""
        return self._deform(obj, "BEND", angle, along, toward)

    def twist(self, obj, angle: float, along: str = "Z"):
        """Twist a whole piece about its length — twisted horns, rope, wrung cloth, a gnarled trunk, a drill bit.
        angle = total turn from one end to the other in radians. Extra rings are added. Returns the piece."""
        return self._deform(obj, "TWIST", angle, along, None)

    def sculpt(self, obj, brush: str, *, at=None, radius: float = 0.1, amount: float = 0.02, to=None, path=None,
               scale: float = 12.0, strength: float = 0.6):
        """Shape a smooth piece like a sculpting brush — best on blob(), skin() or subdivided parts (many vertices):
          "grab"    move the surface near `at` by the vector `to` = (x, y, z), fading out over `radius` (pull a snout)
          "inflate" push the surface near `at` out along its normals by `amount` (negative dents: cheeks, dimples)
          "crease"  press a groove `amount` deep and `radius` wide along `path` = [(x, y, z), …] (eyelids, folds, bark)
          "noise"   roughen the surface by `amount` at `scale` bumps per meter, near `at` or everywhere (stone, bark)
          "smooth"  relax the surface near `at`, or everywhere without `at`
          "ridge"   raise a rounded ridge `amount` high and `radius` wide along `path` (eyelids, brows, lips, a skull crest)
          "pinch"   pull the surface within `radius` toward the `path` line, by `strength` 0…1 — makes a crease or ridge
                    crisp and sharp (run it after crease or ridge on the same path)
          "flatten" press the surface near `at` flat onto its average plane (or the plane facing `to`), by `strength`:
                    cheek plates, planes of a skull, a worn flat spot
          "layer"   add a layer of clay `amount` thick with a crisp edge over `radius` around `at` (paw pads, plates,
                    scales, a thickened brow).
        All positions in world meters; path points and `at` snap to the nearest point of the surface. Returns the piece."""
        import bmesh
        from mathutils import noise as mnoise
        self._bake(obj)
        # brush points land on the surface: the nearest point of the piece, so a path drawn roughly still bites
        if (path or at is not None) and obj.data.polygons:
            from mathutils.bvhtree import BVHTree
            bvh = BVHTree.FromPolygons([tuple(v.co + obj.location) for v in obj.data.vertices],
                                       [tuple(p.vertices) for p in obj.data.polygons])

            def snap(q):
                hit = bvh.find_nearest(Vector(q))
                return tuple(hit[0]) if hit and hit[0] is not None else tuple(q)
            if path:
                path = [snap(q) for q in path]
            if at is not None and brush != "grab":
                at = snap(at)
        if brush in ("crease", "ridge", "pinch") and path:
            line_ = [Vector(p) for p in path]
            near = lambda c: min(_seg_distance(c, a, b) for a, b in zip(line_, line_[1:])) < radius * 2   # noqa: E731
        elif at is not None:
            near = lambda c: (c - Vector(at)).length < radius * 1.5   # noqa: E731
        else:
            near = None
        self._refine(obj, radius / 3 if brush != "noise" or at is not None else 0.3 / max(scale, 1e-3), near=near)
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.normal_update()
        mw = Matrix.Translation(obj.location)   # after _bake only the location is left (matrix_world may be stale)
        inv = mw.inverted()
        centre = Vector(at) if at is not None else None

        def fall(d):
            u = max(0.0, 1.0 - d / max(radius, 1e-6))
            return u * u * (3 - 2 * u)

        if brush == "grab":
            if centre is None or to is None:
                raise ModelError("sculpt('grab') needs at= and to=")
            move = inv.to_3x3() @ Vector(to)
            for v in bm.verts:
                w = fall(((mw @ v.co) - centre).length)
                if w:
                    v.co += move * w
        elif brush in ("inflate", "noise"):
            for v in bm.verts:
                wp = mw @ v.co
                w = 1.0 if centre is None else fall((wp - centre).length)
                if w:
                    h = amount if brush == "inflate" else amount * mnoise.noise(wp * scale)
                    v.co += v.normal * h * w
        elif brush in ("crease", "ridge", "pinch"):
            line = [Vector(p) for p in (path or [])]
            if len(line) < 2:
                raise ModelError(f"sculpt('{brush}') needs path= with at least two points")
            k = max(0.0, min(1.0, float(strength)))
            for v in bm.verts:
                wp = mw @ v.co
                d, q = min(((_seg_distance(wp, a, b), _seg_closest(wp, a, b)) for a, b in zip(line, line[1:])),
                           key=lambda t: t[0])
                w = fall(d)
                if not w:
                    continue
                if brush == "crease":
                    v.co -= v.normal * amount * w
                elif brush == "ridge":
                    v.co += v.normal * amount * w
                else:   # pinch: slide toward the line within the surface, so its edge gets sharp
                    delta = q - wp
                    delta -= v.normal * v.normal.dot(delta)
                    v.co += delta * k * w
            # tidy the stroke like an artist's light smooth pass: shards from moved vertices go, the ridge stays
            touched = [v for v in bm.verts
                       if min(_seg_distance(mw @ v.co, a, b) for a, b in zip(line, line[1:])) < radius * 1.2]
            for _ in range(2):
                new = {}
                for v in touched:
                    if v.link_edges:
                        avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
                        new[v] = v.co.lerp(avg, 0.35)
                for v, co in new.items():
                    v.co = co
        elif brush == "flatten":
            if centre is None:
                raise ModelError("sculpt('flatten') needs at=")
            inside = [(v, fall(((mw @ v.co) - centre).length)) for v in bm.verts]
            inside = [(v, w) for v, w in inside if w]
            if inside:
                tot = sum(w for _, w in inside)
                origin = sum((v.co * w for v, w in inside), Vector()) / tot
                nrm = (inv.to_3x3() @ Vector(to)).normalized() if to is not None else \
                    sum((v.normal * w for v, w in inside), Vector()).normalized()
                k = max(0.0, min(1.0, float(strength)))
                for v, w in inside:
                    v.co -= nrm * nrm.dot(v.co - origin) * k * w
        elif brush == "layer":
            if centre is None:
                raise ModelError("sculpt('layer') needs at=")
            edge = max(radius * 0.25, 1e-6)
            for v in bm.verts:
                d = ((mw @ v.co) - centre).length
                u = max(0.0, min(1.0, (radius - d) / edge))
                if u:
                    v.co += v.normal * amount * u * u * (3 - 2 * u)
        elif brush == "smooth":
            new = {}
            for v in bm.verts:
                w = 1.0 if centre is None else fall(((mw @ v.co) - centre).length)
                if w and v.link_edges:
                    avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
                    new[v] = v.co.lerp(avg, 0.6 * w)
            for v, co in new.items():
                v.co = co
        else:
            raise ModelError(f"sculpt brush '{brush}' — use grab, inflate, crease, ridge, pinch, flatten, layer, noise or smooth")
        bm.to_mesh(me)
        me.update()
        bm.free()
        return obj

    @staticmethod
    def _axis(name):
        name = str(name).upper().strip()
        v = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}.get(name.lstrip("+-"))
        if v is None:
            raise ModelError(f"axis '{name}' — use X, Y, Z, -X, -Y or -Z")
        return -v if name.startswith("-") else v

    def _vert_cap(self) -> int:
        return {0: 1500, 1: 5000, 2: 15000, 3: 50000}[self.level]

    def _refine(self, obj, max_edge: float, rounds: int = 5, near=None):
        """Split edges longer than max_edge (sculpt needs vertices to move), within the tier's vertex cap and never
        finer than the tier's detail: a phone model gets a softer brush, not a denser mesh."""
        import bmesh
        xs, ys, zs = zip(*[v.co[:] for v in obj.data.vertices]) if obj.data.vertices else ((0,), (0,), (0,))
        extent = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1e-3)
        cells = {0: 40, 1: 70, 2: 140, 3: 300}[self.level] * (0.5 if self._faceted else 1.0)
        # and never finer than the tier's cell in meters (a little under blob's): a small skull on a phone does not
        # need millimetre edges just because it is small
        floor = {0: 0.02, 1: 0.012, 2: 0.007, 3: 0.004}[self.level] * 0.6
        max_edge = max(max_edge, extent / cells, floor)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        _tidy_bm(bm, extent)
        off = obj.location
        for _ in range(rounds):
            long = [e for e in bm.edges if e.is_manifold and e.calc_length() > max_edge   # never split a non-manifold
                    and (near is None or near((e.verts[0].co + e.verts[1].co) / 2 + off))]   # edge: Blender crashes
            if not long or len(bm.verts) + len(long) > self._vert_cap():
                break
            _split_edges(bm, long)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

    def _slice(self, obj, axis: Vector, lo: float, hi: float, n: int):
        """Cut n rings across the piece along axis (world coordinates) so a deform bends smoothly."""
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        loc = obj.location
        for i in range(1, n):
            co = axis * (lo + (hi - lo) * i / n) - loc
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=axis)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

    def _deform(self, obj, method, angle, along, toward):
        self._bake(obj)
        ax = self._axis(along)
        mw = Matrix.Translation(obj.location)   # after _bake only the location is left (matrix_world may be stale)
        vals = [(mw @ v.co).dot(ax) for v in obj.data.vertices]
        if not vals:
            return obj
        lo, hi = min(vals), max(vals)
        self._slice(obj, ax, lo, hi, max(8, self.seg(24)))
        centre = sum((mw @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
        base = centre + ax * (lo - centre.dot(ax))
        if method == "BEND":
            up = self._axis(toward)
            up = (up - ax * up.dot(ax))
            if up.length < 1e-6:
                raise ModelError("bend(): toward must be across the piece, not along it")
            up.normalize()
            # canonical frame for Blender's bend: length along +X, curling toward +Y, around Z
            rot = Matrix((ax, up, ax.cross(up))).transposed().to_4x4()
            origin_m = Matrix.Translation(base) @ rot
        else:
            z = ax
            x = Vector((1, 0, 0)) if abs(z.x) < 0.9 else Vector((0, 1, 0))
            x = (x - z * x.dot(z)).normalized()
            origin_m = Matrix.Translation(base) @ Matrix((x, z.cross(x), z)).transposed().to_4x4()
        empty = bpy.data.objects.new("mg_deform_origin", None)
        bpy.context.collection.objects.link(empty)
        empty.matrix_world = origin_m
        mod = obj.modifiers.new(method.lower(), "SIMPLE_DEFORM")
        mod.deform_method, mod.angle, mod.origin = method, float(angle), empty
        mod.deform_axis = "Z"
        bpy.context.view_layer.update()
        self._apply_modifiers(obj)
        bpy.data.objects.remove(empty)
        bpy.context.view_layer.update()
        return obj

    @staticmethod
    def _forget(obj) -> None:
        """Delete a used-up piece and its mesh. The view layer is refreshed right away: Blender 4.2+ keeps a cached object
        list that would otherwise still hand out the deleted object (a crash in 4.2, None in 5.x)."""
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        bpy.context.view_layer.update()

    def _cells(self) -> dict:
        """Palette cell (u, v) → material index, for the hero model's surface relief (finish.save_high)."""
        return {tuple(round(x, 4) for x in self._cell_uv(n)): MATERIALS.index(c["material"]) for n, c in self._colors.items()}

    def _finalize(self) -> list[str]:
        """After build(): palette textures, one root named after the asset, grounded and centred. Returns notes."""
        notes = []
        with rest_pose():
            return self._finalize_rest(notes)

    def _finalize_rest(self, notes: list) -> list[str]:
        if self._fit:
            notes += self._apply_fit()
        self._make_palette()
        laid = self._apply_tiles()
        if laid:
            notes.append(f"tiling materials: {', '.join(laid)}")
        objs = [o for o in bpy.context.scene.objects]
        meshes = [o for o in objs if o.type == "MESH"]
        if not meshes:
            raise ModelError("build(mg) made no mesh — create parts and join them")
        once = list({o.data: o for o in reversed(meshes)}.values())   # instances share a mesh: work on it once
        hidden = sum(self._cull_hidden(o) for o in once if not o.get("meshgate_cards"))
        if hidden:
            notes.append(f"removed {hidden} hidden faces (inside other pieces)")
        if self._focus and self.level >= 1 and not self._faceted:   # flat facets: extra triangles only crumple them
            added = self._apply_focus([o for o in meshes if not o.get("meshgate_cards") and o.data.users == 1])
            if added:
                notes.append(f"focus: {added:,} more triangles where the model needs detail")
        if self._faceted:
            merged = sum(self._planar(o) for o in once if not o.get("meshgate_cards") and not o.get("meshgate_tiles"))
            if merged:
                notes.append(f"low-poly: {merged:,} triangles saved by merging flat facets and re-triangulating them")
        fought = sum(self._unfight(o) for o in once if not o.get("meshgate_cards"))
        if fought:
            notes.append(f"moved {fought} faces {UNFIGHT * 1000:g} mm off surfaces they lay flat on (they would flicker)")
        thinned = self._fit_cards()
        if thinned:
            notes.append(f"fur thinned to {thinned} % of its cards to stay within the tier's triangle budget")
        if not self._faceted:
            n = sum(self._weighted_normals(o) for o in once if not o.get("meshgate_cards"))
            if n:
                notes.append(f"weighted normals on {n} mesh{'es' if n > 1 else ''} (clean shading on flat faces)")
        if self._outline:
            notes += self._ink(once, meshes)
        sockets = [o for o in objs if o.get("meshgate_socket") and o.parent is None]
        roots = [o for o in objs if o.parent is None and not o.get("meshgate_socket")]
        if len(roots) == 1:
            root = roots[0]
            root.name = self._name
            if root.type == "MESH":
                root.data.name = self._name
        else:
            root = self.group(self._name)
            for o in roots:
                self.attach(o, root)
        for sk in sockets:   # attachment points ride along with the asset
            self.attach(sk, root)
        bpy.context.view_layer.update()
        lo, hi = self._bounds(meshes)
        size = max(hi - lo)
        shift = Vector((0, 0, -lo.z))
        cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        if abs(cx) > 0.1 * size or abs(cy) > 0.1 * size:
            shift.x, shift.y = -cx, -cy
            notes.append(f"centred the footprint (was off by {cx:.2f}, {cy:.2f} m)")
        if abs(lo.z) > 0.002:
            notes.append(f"moved onto the ground (lowest point was z = {lo.z:.3f} m)")
        if shift.length > 1e-6:
            if root.type == "MESH" and not root.children and not root.animation_data:
                root.data.transform(Matrix.Translation(shift))   # keep the origin at the world origin
            else:
                root.location += shift
        bpy.context.view_layer.update()
        return notes

    def _apply_tiles(self) -> list[str]:
        """Turn the faces coloured with a tile (mg.tile) into its tiling material, laid by position. Faces are found
        by their palette cell, so joins and cuts keep them. Within the tier's material budget (the palette takes one;
        the largest tiled areas win); the others, and the low-poly look, keep the plain colour."""
        if not self._tiles or self._vertex or self._faceted:
            return []
        cells = {tuple(round(x, 4) for x in self._cell_uv(n)): n for n in self._tiles}
        users: dict = {}
        for o in bpy.context.scene.objects:
            if o.type == "MESH" and not o.get("meshgate_cards"):
                users.setdefault(o.data, []).append(o)
        found: dict = {}   # mesh → {tile name: [face indices]}
        area: dict = {}
        for me, objs in users.items():
            uv = me.uv_layers.get("UVMap") or me.uv_layers.active
            if uv is None:
                continue
            for p in me.polygons:
                n = cells.get(tuple(round(x, 4) for x in uv.data[p.loop_start].uv))
                if n:
                    found.setdefault(me, {}).setdefault(n, []).append(p.index)
                    area[n] = area.get(n, 0.0) + p.area * len(objs)
        room = len(area) if not self._max_materials else max(0, self._max_materials - 1)
        chosen = sorted(area, key=lambda n: -area[n])[:room]
        if not chosen:
            return []
        px = min({0: 256, 1: 512, 2: 1024, 3: 2048}[self.level], self._max_texture or 4096)
        if self._max_texture_mb:   # three maps per tile (+ mips) within the tier's texture memory, the palette aside
            while px > 128 and len(chosen) * 3 * px * px * 16 / 3 / 2 ** 20 > self._max_texture_mb * 0.85:
                px //= 2
        mats = {n: self._tile_material(n, px) for n in chosen}
        for me, by in found.items():
            by = {n: f for n, f in by.items() if n in mats}
            if not by:
                continue
            pieces = users[me]
            shared = len(pieces) > 1
            faces = {i for f in by.values() for i in f}
            if self._soft_paint and len(faces) < len(me.polygons):
                # a baked finish bakes the palette part into one atlas: the tiled faces become a child object of
                # each piece (placed, turned and animated with it), keeping their own material
                me = self._split_faces(me, faces, pieces)
                by = {n: self._faces_of(me, cells, n) for n in by}
            # by position: world for a single piece, the mesh's own space for instances (copies look alike) and
            # for modules (the pattern starts at the grid corner, so it carries on across snapped modules)
            m = self._world(pieces[0]) if not shared and not pieces[0].get("meshgate_module") else Matrix.Identity(4)
            for n, idx in by.items():
                if mats[n] not in list(me.materials):
                    me.materials.append(mats[n])
                slot = list(me.materials).index(mats[n])
                for i in idx:
                    me.polygons[i].material_index = slot
                self._box_uv(me, idx, m, self._tiles[n]["size"])
            used = {me.materials[p.material_index] for p in me.polygons}
            if used <= set(mats.values()):   # all tiled: out of the palette bake, and no unused palette slot
                for o in bpy.data.objects:
                    if o.data is me:
                        o["meshgate_tiles"] = True
                keep = [x for x in me.materials if x in used]
                idx = [keep.index(me.materials[p.material_index]) for p in me.polygons]
                me.materials.clear()
                for x in keep:
                    me.materials.append(x)
                me.polygons.foreach_set("material_index", idx)
        return [f"{n} ({self._tiles[n]['pattern']}, {self._tiles[n]['size']:g} m)" for n in chosen]

    def _faces_of(self, me, cells, name) -> list:
        uv = me.uv_layers.get("UVMap") or me.uv_layers.active
        return [p.index for p in me.polygons if cells.get(tuple(round(x, 4) for x in uv.data[p.loop_start].uv)) == name]

    def _split_faces(self, me, faces: set, objs):
        """Move `faces` of a mesh into a new mesh; each object using it gets a child holding the new one."""
        import bmesh
        new = me.copy()
        for target, drop in ((new, lambda f: f.index not in faces), (me, lambda f: f.index in faces)):
            bm = bmesh.new()
            bm.from_mesh(target)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if drop(f)], context="FACES")
            bm.to_mesh(target)
            bm.free()
            target.update()
        for o in objs:
            child = bpy.data.objects.new(f"{o.name}_tiles", new)
            bpy.context.collection.objects.link(child)
            child.parent = o   # identity under the piece: moves, turns and animates with it
            child.matrix_parent_inverse = Matrix.Identity(4)
            child["meshgate_tiles"] = True
        return new

    @staticmethod
    def _box_uv(me, faces, m, size: float) -> None:
        """Lay a tile by position (box projection): walls take it upright, floors and roofs from above."""
        uv = me.uv_layers.get("UVMap") or me.uv_layers.active
        rot = m.to_3x3()
        for i in faces:
            p = me.polygons[i]
            n = rot @ p.normal
            ax = max(range(3), key=lambda k: abs(n[k]))
            for li in p.loop_indices:
                co = m @ me.vertices[me.loops[li].vertex_index].co
                if ax == 2:
                    u, v = co.x, co.y if n.z > 0 else -co.y
                elif ax == 0:
                    u, v = (co.y if n.x > 0 else -co.y), co.z
                else:
                    u, v = (-co.x if n.y > 0 else co.x), co.z
                uv.data[li].uv = (u / size, v / size)

    def _tile_material(self, name: str, px: int):
        from . import tiles
        from .finish import _occlusion
        spec = self._tiles[name]
        imgs = tiles.make_images(bpy, f"{self._name}_{name}", spec, px, self._tmp)
        mat = bpy.data.materials.new(f"{self._name}_{name}")
        mat.use_nodes = True
        mat.use_backface_culling = True
        nt = mat.node_tree
        pb = compat.principled(mat)

        def tex(img, y):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image, t.location = img, (-700, y)
            return t
        c = tex(imgs["basecolor"], 300)
        nt.links.new(c.outputs["Color"], pb.inputs["Base Color"])
        r = tex(imgs["orm"], 0)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-400, 0)
        nt.links.new(r.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], pb.inputs["Roughness"])
        nt.links.new(sep.outputs[2], pb.inputs["Metallic"])
        _occlusion(nt, sep.outputs[0])
        nrm = tex(imgs["normal"], -300)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-400, -300)
        nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], pb.inputs["Normal"])
        nt.nodes.active = c
        return mat

    @staticmethod
    def _weighted_normals(obj) -> int:
        """Weighted normals, the game artist's standard finish for hard surfaces: big flat faces keep flat shading and
        the small bevels between them take the curvature, so a low-poly box reads clean and solid. Sharp edges stay."""
        me = obj.data
        if not me.polygons or not any(p.use_smooth for p in me.polygons):
            return 0
        sharing = [o for o in bpy.data.objects if o.data is me and o is not obj]
        if sharing:   # Blender applies modifiers to single-user meshes only: finish a copy, then share it again
            obj.data = me.copy()
            done = Kit._weighted_normals(obj)
            for o in sharing:
                o.data = obj.data
            if me.users == 0:
                bpy.data.meshes.remove(me)
            return done
        if hasattr(me, "use_auto_smooth"):   # ≤ 4.0: custom normals need auto smooth
            me.use_auto_smooth = True
        mod = obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
        mod.mode, mod.weight, mod.keep_sharp = "FACE_AREA", 50, True
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            if obj.modifiers[0] is not mod:   # before an armature: normals are part of the mesh, not of the pose
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:
                obj.modifiers.remove(mod)
                return 0
        return 1

    def _apply_fit(self) -> list[str]:
        """Proportions fitted to the reference picture: each height band of the model is made as wide as the picture's
        (the ratios come from comparing their outlines), with a smooth profile between bands — vertices and the
        skeleton's joints alike, so a rigged character still bends where it should. At most ±20 % per band."""
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.users == 1]
        if not meshes:
            return []
        lo, hi = self._bounds(meshes)
        h = max(hi.z - lo.z, 1e-6)
        cx = (lo.x + hi.x) / 2
        pts = sorted(((a + b) / 2, max(0.8, min(1.2, r))) for a, b, r in self._fit)
        if all(abs(r - 1) < 0.04 for _, r in pts):
            return []
        sm = [(t, (pts[max(i - 1, 0)][1] + 2 * r + pts[min(i + 1, len(pts) - 1)][1]) / 4) for i, (t, r) in enumerate(pts)]

        def ratio(z):
            t = (z - lo.z) / h
            if t <= sm[0][0]:
                return sm[0][1]
            for (t0, r0), (t1, r1) in zip(sm, sm[1:]):
                if t <= t1:
                    u = (t - t0) / max(t1 - t0, 1e-6)
                    u = u * u * (3 - 2 * u)
                    return r0 + (r1 - r0) * u
            return sm[-1][1]

        def warp(w):
            return Vector((cx + (w.x - cx) * ratio(w.z), w.y, w.z))
        for o in meshes:
            mw, inv = o.matrix_world, o.matrix_world.inverted()
            for v in o.data.vertices:
                v.co = inv @ warp(mw @ v.co)
            o.data.update()
        for arm in [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]:
            for x in bpy.context.view_layer.objects:
                x.select_set(x is arm)
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.mode_set(mode="EDIT")
            aw, ainv = arm.matrix_world, arm.matrix_world.inverted()
            for eb in arm.data.edit_bones:
                eb.head, eb.tail = ainv @ warp(aw @ eb.head), ainv @ warp(aw @ eb.tail)
            bpy.ops.object.mode_set(mode="OBJECT")
        widest = max(sm, key=lambda p: abs(p[1] - 1))
        return [f"proportions fitted to the reference: widths scaled by {min(r for _, r in sm):.2f}–"
                f"{max(r for _, r in sm):.2f} (most at {widest[0] * 100:.0f} % of the height)"]

    def _ink(self, once, meshes) -> list[str]:
        """The toon ink line, as games draw it: an inverted hull — each mesh gets a slightly fatter copy of itself turned
        inside out in a flat dark material; only its back faces are drawn, so a line shows round the silhouette and at
        folds, and it bends with the skeleton. The phone tiers below mobile-high keep their triangles and draw calls."""
        if self.level < 2:
            return []
        total = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
        if self._max_tris and total * 2 > self._max_tris:
            return [f"ink line skipped: it would double {total:,} triangles past the tier's {self._max_tris:,}"]
        mats = {m for o in once for m in o.data.materials if m}
        if self._max_materials and len(mats) + 1 > self._max_materials:
            return ["ink line skipped: the tier allows no extra material"]
        lo, hi = self._bounds(meshes)
        width = max(0.003, min(0.02, max(hi - lo) * 0.01))   # about 1 cm on a 1 m character
        ink = bpy.data.materials.get(f"{self._name}_ink") or bpy.data.materials.new(f"{self._name}_ink")
        ink.use_nodes = True
        ink.use_backface_culling = True
        b = compat.principled(ink)
        b.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1.0)
        b.inputs["Roughness"].default_value = 1.0
        done = 0
        for o in once:
            if o.get("meshgate_cards") or o.get("meshgate_tiles") or not o.data.polygons:
                continue
            me = o.data
            me.materials.append(ink)
            slot = len(me.materials) - 1
            n = len(me.polygons)
            mod = o.modifiers.new("ink", "SOLIDIFY")
            mod.thickness, mod.offset = width, 1.0
            mod.use_flip_normals, mod.use_rim = True, False
            mod.use_even_offset = False   # even thickness spikes out at sharp tips (a cone's point, a drip)
            with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o]):
                if o.modifiers[0] is not mod:   # before an armature: the hull is part of the mesh and gets its weights
                    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
                bpy.ops.object.modifier_apply(modifier=mod.name)
            if len(me.polygons) != 2 * n:
                continue
            idx = [0] * len(me.polygons)   # the original faces come first, the inside-out shell after them (3.5–5.2)
            me.polygons.foreach_get("material_index", idx)
            idx[n:] = [slot] * n
            me.polygons.foreach_set("material_index", idx)
            thin = self._thin_faces(me, n, width * 3)   # a whisker or a thin rim would drown in a line thicker than it
            if thin:
                import bmesh
                bm = bmesh.new()
                bm.from_mesh(me)
                bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[n + i] for i in thin], context="FACES")
                bm.to_mesh(me)
                bm.free()
            me.update()
            done += 1
        return [f"ink line: an inverted hull {width * 1000:.0f} mm wide on {done} mesh{'es' if done != 1 else ''} (toon)"] if done else []

    @staticmethod
    def _thin_faces(me, n: int, limit: float) -> list[int]:
        """Indices (below n) of faces on pieces thinner than `limit` in their smallest dimension."""
        parent = list(range(len(me.vertices)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for p in me.polygons[:n]:
            vs = p.vertices
            for v in vs[1:]:
                a, b = find(vs[0]), find(v)
                if a != b:
                    parent[a] = b
        lo: dict = {}
        hi: dict = {}
        for p in me.polygons[:n]:
            for v in p.vertices:
                r, co = find(v), me.vertices[v].co
                lo[r] = Vector((min(lo[r][k], co[k]) for k in range(3))) if r in lo else co.copy()
                hi[r] = Vector((max(hi[r][k], co[k]) for k in range(3))) if r in hi else co.copy()
        thin = {r for r in lo if min(hi[r] - lo[r]) < limit}
        return [p.index for p in me.polygons[:n] if find(p.vertices[0]) in thin]

    @staticmethod
    def _planar(obj) -> int:
        """Low-poly finish for things that do not bend (crates, fences, stones): faces lying in one plane merge into one
        facet and are re-triangulated evenly ("beauty"), so a flat side reads as one clean plane instead of a fan of
        slivers. Colour edges, seams and sharp edges stay. A rigged mesh keeps its loops (it bends there)."""
        import bmesh
        if any(m.type == "ARMATURE" for m in obj.modifiers) or obj.data.shape_keys or not obj.data.polygons:
            return 0
        me = obj.data
        before = sum(len(p.vertices) - 2 for p in me.polygons)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts[:], edges=bm.edges[:],
                                 delimit={"MATERIAL", "SEAM", "SHARP", "UV"})
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        after = len(bm.faces)
        if after >= before:
            bm.free()
            return 0
        bm.to_mesh(me)
        bm.free()
        me.update()
        return before - after

    @staticmethod
    def _unfight(obj) -> int:
        """Faces of one piece lying flat on a face of another piece, facing the same way — a cap flush with a post's
        top, a wheel's face in the box front, a decal set exactly on the surface. Engines draw such pairs flickering
        (z-fighting) or black. The smaller piece's faces are moved a hair out along their normals. Returns faces moved."""
        import bmesh
        from mathutils.bvhtree import BVHTree
        if obj.data.shape_keys or len(obj.data.polygons) > 60000:
            return 0
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        island = {}
        sizes = []
        for f in bm.faces:
            if f.index in island:
                continue
            k, stack, n = len(sizes), [f], 0
            island[f.index] = k
            while stack:
                g = stack.pop()
                n += 1
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in island:
                            island[h.index] = k
                            stack.append(h)
            sizes.append(n)
        if len(sizes) < 2:
            bm.free()
            return 0
        tree = BVHTree.FromBMesh(bm)
        eps = 0.0004
        moved = set()
        for f in bm.faces:
            k = island[f.index]
            c, nrm = f.calc_center_median(), f.normal
            for co, hn, j, d in tree.find_nearest_range(c, eps):
                if j is None or island[j] == k or hn.dot(nrm) < 0.995:
                    continue
                # f's centre lies on the other face: they overlap there. Move the smaller piece's face.
                other = bm.faces[j]
                if sizes[k] < sizes[island[j]] or (sizes[k] == sizes[island[j]] and k < island[j]):
                    moved.add(f.index)
                else:
                    moved.add(other.index)
        if moved:
            push: dict = {}
            for i in moved:
                f = bm.faces[i]
                for v in f.verts:
                    push[v] = push.get(v, Vector()) + f.normal
            for v, d in push.items():
                if d.length > 1e-9:
                    v.co += d.normalized() * UNFIGHT
            bm.to_mesh(obj.data)
            obj.data.update()
        bm.free()
        return len(moved)

    def _fit_cards(self) -> int:
        """Fur cards are the part a tier can lose most gracefully: when the model is over its triangle budget, drop a
        random share of the cards (never below 30 %) so it fits. Returns the percentage kept, 0 when nothing changed."""
        import bmesh
        if not self._max_tris:
            return 0
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        total = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
        cards = [o for o in objs if o.get("meshgate_cards")]
        card_tris = sum(len(p.vertices) - 2 for o in cards for p in o.data.polygons)
        over = total - self._max_tris * 0.95
        if over <= 0 or not card_tris:
            return 0
        keep = max(0.3, 1.0 - over / card_tris)
        rng = random.Random(7)
        for o in cards:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            drop, seen = [], set()
            for f in bm.faces:   # a card is a connected strip: keep or drop it whole
                if f.index in seen:
                    continue
                strip, todo = [], [f]
                while todo:
                    g = todo.pop()
                    if g.index in seen:
                        continue
                    seen.add(g.index)
                    strip.append(g)
                    todo += [h for e in g.edges for h in e.link_faces if h.index not in seen]
                if rng.random() > keep:
                    drop += strip
            if drop:
                bmesh.ops.delete(bm, geom=drop, context="FACES")
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
        return round(keep * 100)

    def _apply_focus(self, meshes) -> int:
        """Smoothly subdivide the faces inside focus regions, within the tier's budget. Returns triangles added."""
        import bmesh
        # the room left in the tier's budget counts everything drawn: other meshes, fur cards and instance copies
        total = sum(len(p.vertices) - 2 for o in bpy.context.scene.objects if o.type == "MESH" for p in o.data.polygons)
        room = (self._max_tris or 10 ** 9) * 0.85 - total
        added = 0
        for rounds in range(2):
            for o in meshes:
                if room <= 0:
                    return added
                off = o.location
                bm = bmesh.new()
                bm.from_mesh(o.data)
                _tidy_bm(bm)
                edges = []
                floor = {0: 0.02, 1: 0.012, 2: 0.007, 3: 0.004}[self.level] * 1.5   # already this fine: leave it
                for e in bm.edges:
                    mid = (e.verts[0].co + e.verts[1].co) / 2 + off
                    if e.is_manifold and e.calc_length() > floor and any((mid - c).length < r and st > rounds
                                                                         for c, r, st in self._focus):
                        edges.append(e)
                if not edges:
                    bm.free()
                    continue
                before = sum(len(f.verts) - 2 for f in bm.faces)
                est = len(edges) * 2   # a rough cost: about two triangles per split edge
                if est > room:
                    bm.free()
                    continue
                _split_edges(bm, edges, smooth=0.6)
                after = sum(len(f.verts) - 2 for f in bm.faces)
                bm.to_mesh(o.data)
                bm.free()
                o.data.update()
                added += after - before
                room -= after - before
        return added

    def _facts(self) -> dict:
        """Geometry facts for the AI, measured on the built model (not guessed from a render): pieces floating free
        of everything else, which lines of code spend the triangles, how symmetric the model is. Pieces are named by
        the build-code line that made them."""
        from mathutils.bvhtree import BVHTree
        from mathutils.kdtree import KDTree
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.get("meshgate_cards")
                  and not o.get("meshgate_collision_for")]
        if not meshes:
            return {}
        with rest_pose():
            pieces, tris_by_line, all_pts = [], {}, []
            for o in meshes:
                me = o.data
                mw = o.matrix_world
                src = me.attributes.get(SRC_ATTR)
                lines = [0] * len(me.vertices)
                if src is not None:
                    src.data.foreach_get("value", lines)
                for poly in me.polygons:
                    ln = lines[poly.vertices[0]]
                    tris_by_line[ln] = tris_by_line.get(ln, 0) + len(poly.vertices) - 2
                parent = list(range(len(me.vertices)))

                def find(i):
                    while parent[i] != i:
                        parent[i] = parent[parent[i]]
                        i = parent[i]
                    return i
                for e in me.edges:
                    a, b = find(e.vertices[0]), find(e.vertices[1])
                    if a != b:
                        parent[a] = b
                groups: dict = {}
                for i in range(len(me.vertices)):
                    groups.setdefault(find(i), []).append(i)
                world = [mw @ v.co for v in me.vertices]
                all_pts += world[::max(1, len(world) // 3000)]
                for verts in sorted(groups.values(), key=len, reverse=True)[:400]:
                    pts = [world[i] for i in verts]
                    ln = max(set(lines[i] for i in verts), key=lambda x: sum(1 for i in verts if lines[i] == x))
                    pieces.append({"line": ln, "verts": verts, "pts": pts, "obj": o})
            lo = Vector([min(p[i] for p in all_pts) for i in range(3)])
            hi = Vector([max(p[i] for p in all_pts) for i in range(3)])
            size = max(hi - lo) or 1.0
            tol = max(0.004, 0.012 * size)
            floating = []
            if 1 < len(pieces):
                # one tree over every piece's faces; a piece floats when no other piece comes within tol of it
                verts_w, faces_w, face_piece = [], [], []
                for k, pc in enumerate(pieces):
                    me = pc["obj"].data
                    vset = set(pc["verts"])
                    base = len(verts_w)
                    idx = {}
                    for i in pc["verts"]:
                        idx[i] = len(verts_w) - base
                        verts_w.append(tuple(pc["obj"].matrix_world @ me.vertices[i].co))
                    for poly in me.polygons:
                        if poly.vertices[0] in vset:
                            faces_w.append(tuple(base + idx[i] for i in poly.vertices))
                            face_piece.append(k)
                tree = BVHTree.FromPolygons(verts_w, faces_w) if faces_w else None
                # contacts both ways (a leg's top touches the table top even where the top has no vertex), then what
                # is held up: everything connected to a piece on the ground
                touch = {k: set() for k in range(len(pieces))}
                reach = max(tol, 0.25 * size)
                for k, pc in enumerate(pieces):
                    for q in pc["pts"][::max(1, len(pc["pts"]) // 80)]:
                        nearest: dict = {}   # the closest face of each other piece
                        for h in (tree.find_nearest_range(q, reach) if tree else []):
                            j = face_piece[h[2]]
                            if j != k and (j not in nearest or h[3] < nearest[j][3]):
                                nearest[j] = h
                        for j, h in nearest.items():
                            # touching, or sunk into it (behind its nearest face): an ear set into a head is held
                            if h[3] <= tol or (q - h[0]).dot(h[1]) < 0:
                                touch[k].add(j)
                                touch[j].add(k)
                held = {k for k, pc in enumerate(pieces) if min(p.z for p in pc["pts"]) <= lo.z + tol}
                todo = list(held)
                while todo:
                    for j in touch[todo.pop()]:
                        if j not in held:
                            held.add(j)
                            todo.append(j)
                for k, pc in enumerate(pieces):
                    if k in held or tree is None:
                        continue
                    sample = pc["pts"][::max(1, len(pc["pts"]) // 60)]
                    gap = min((h[3] for q in sample[:20] for h in tree.find_nearest_range(q, size)
                               if face_piece[h[2]] in held), default=size)
                    floating.append({"line": pc["line"], "what": self._sources.get(pc["line"], "piece"),
                                     "gap_cm": round(gap * 100, 1),
                                     "at": [round(x, 3) for x in (sum(pc["pts"], Vector()) / len(pc["pts"]))]})
            kd = KDTree(len(all_pts))
            for i, q in enumerate(all_pts):
                kd.insert(q, i)
            kd.balance()
            cx = (lo.x + hi.x) / 2
            mirror = sum(kd.find(Vector((2 * cx - q.x, q.y, q.z)))[2] for q in all_pts[::max(1, len(all_pts) // 500)])
            mirror /= max(1, len(all_pts[::max(1, len(all_pts) // 500)]))
        total = sum(tris_by_line.values()) or 1
        top = sorted(((ln, n) for ln, n in tris_by_line.items() if ln), key=lambda t: -t[1])[:6]
        uv = json.loads(bpy.context.scene.get("mg_uv", "{}") or "{}")
        modules = []
        for m in self._modules:
            if not m.name or m.name not in bpy.data.objects:
                continue
            g, (fx, fy) = m["meshgate_grid"], m["meshgate_footprint"]
            vs = [v.co for v in m.data.vertices] or [Vector()]
            mlo = Vector([min(v[i] for v in vs) for i in range(3)])
            mhi = Vector([max(v[i] for v in vs) for i in range(3)])
            off = []
            tol = max(0.01, g * 0.005)
            if fx and (abs(mlo.x) > tol or abs(mhi.x - fx * g) > tol):   # 0: a post at the corner, centred on it
                off.append(f"x runs {mlo.x:.3f}…{mhi.x:.3f} m, the grid wants 0…{fx * g:g}")
            if fy and (abs(mlo.y) > tol or abs(mhi.y - fy * g) > tol):
                off.append(f"y runs {mlo.y:.3f}…{mhi.y:.3f} m, the grid wants 0…{fy * g:g}")
            if mlo.z < -tol:
                off.append(f"it reaches {mlo.z:.3f} m below its floor")
            modules.append({"name": m["meshgate_module"], "grid_m": g, "footprint": [fx, fy],
                            "size_m": [round(x, 3) for x in (mhi - mlo)], "off_grid": off})
        return {"floating": floating[:12], "uv": uv or None, "modules": modules or None,
                "triangles_by_line": [{"line": ln, "what": self._sources.get(ln, "piece"), "tris": n,
                                       "share": round(n / total, 3)} for ln, n in top],
                "asymmetry": round(mirror / size, 4), "size_m": [round(x, 3) for x in (hi - lo)]}

    @staticmethod
    def _cull_hidden(obj, eps: float = 2e-4) -> int:
        """Delete faces that sit wholly inside another closed piece of the same mesh — an arm sunk into a body, a spine
        base inside a stem, a pot's top under the soil. Nobody sees them; they only cost triangles. Faces that cross the
        other piece's surface stay, so no hole shows. On a rigged character a face is only removed when both pieces follow
        the same bone: an arm sunk into a body swings away from it, and the body under it must still be there.
        Two tests must agree (nearest surface normal and ray parity), so an unsure face is kept. Returns faces removed."""
        import bmesh
        from mathutils.bvhtree import BVHTree
        if obj.data.shape_keys:
            return 0
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        island: dict = {}
        islands: list[list] = []
        for f in bm.faces:
            if f in island:
                continue
            idx, stack, faces = len(islands), [f], []
            island[f] = idx
            while stack:
                g = stack.pop()
                faces.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h not in island:
                            island[h] = idx
                            stack.append(h)
            islands.append(faces)
        if len(islands) < 2:
            bm.free()
            return 0
        bone = {}   # island → the bone that moves it most (rigged meshes only)
        dl = bm.verts.layers.deform.active
        if dl is not None and any(m.type == "ARMATURE" for m in obj.modifiers):
            for idx, faces in enumerate(islands):
                tot: dict = {}
                for v in {v for f in faces for v in f.verts}:
                    for g, w in v[dl].items():
                        tot[g] = tot.get(g, 0.0) + w
                bone[idx] = max(tot, key=tot.get) if tot else None
        solids = []   # (island, tree, lo, hi, sign) for closed pieces only
        for idx, faces in enumerate(islands):
            if len(faces) < 4 or any(len(e.link_faces) != 2 for f in faces for e in f.edges):
                continue
            verts = list({v for f in faces for v in f.verts})
            vi = {v: k for k, v in enumerate(verts)}
            polys = [[vi[v] for v in f.verts] for f in faces]
            cos = [v.co.copy() for v in verts]
            vol = sum(cos[p[0]].dot(cos[p[k]].cross(cos[p[k + 1]])) for p in polys for k in range(1, len(p) - 1))
            if abs(vol) < 1e-12:
                continue
            lo = Vector([min(c[k] for c in cos) for k in range(3)])
            hi = Vector([max(c[k] for c in cos) for k in range(3)])
            solids.append((idx, BVHTree.FromPolygons(cos, polys), lo, hi, 1.0 if vol > 0 else -1.0))
        if not solids:
            bm.free()
            return 0
        ray = Vector((0.1234, 0.3171, 0.9403)).normalized()   # skewed so it rarely runs along an edge

        def inside(tree, sign, co):
            loc, normal, _, dist = tree.find_nearest(co)
            if loc is None or dist < eps or sign * (co - loc).dot(normal) >= 0:
                return False
            hits, origin = 0, co.copy()
            for _ in range(64):
                hit = tree.ray_cast(origin, ray)
                if hit[0] is None:
                    break
                hits += 1
                origin = hit[0] + ray * 1e-6
            return hits % 2 == 1

        cache: dict = {}
        dead = []
        for f in bm.faces:
            own = island[f]
            pts = [v.co for v in f.verts]
            flo = Vector([min(c[k] for c in pts) for k in range(3)])
            fhi = Vector([max(c[k] for c in pts) for k in range(3)])
            for idx, tree, lo, hi, sign in solids:
                if idx == own or any(flo[k] < lo[k] or fhi[k] > hi[k] for k in range(3)):
                    continue
                if bone and bone.get(idx) != bone.get(own):   # they move apart when animated
                    continue
                ok = True
                for v in f.verts:
                    key = (v.index, idx)
                    if key not in cache:
                        cache[key] = inside(tree, sign, v.co)
                    if not cache[key]:
                        ok = False
                        break
                if ok and inside(tree, sign, f.calc_center_median()):
                    dead.append(f)
                    break
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="FACES")
            bm.to_mesh(obj.data)
            obj.data.update()
        bm.free()
        return len(dead)

    def _dims(self) -> list[float]:
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        with rest_pose():
            lo, hi = self._bounds(meshes)
        return [round(v, 3) for v in (hi - lo)]

    # ------------------------------------------------------------------ internals

    def _reset_scene(self):
        s = bpy.context.scene
        s.unit_settings.system = "METRIC"
        s.unit_settings.scale_length = 1.0
        s.render.fps = 30
        s.frame_start, s.frame_end = 1, 1
        s.cursor.location = (0, 0, 0)

    @staticmethod
    def _ascii(name: str) -> str:
        out = "".join(c if (c.isascii() and (c.isalnum() or c in "_-.")) else "_" for c in str(name)).strip("_")
        return out or "part"

    def _mesh(self, label, verts, faces):
        me = bpy.data.meshes.new(label)
        me.from_pydata(verts, [], faces)
        me.validate()
        me.update()
        obj = bpy.data.objects.new(label, me)
        bpy.context.collection.objects.link(obj)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        return obj

    @staticmethod
    def _flip(me):
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()

    @staticmethod
    def _fix_normals(obj):
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()

    def _place(self, obj, loc, scale, rot):
        obj.scale = scale
        obj.rotation_euler = rot
        obj.location = loc
        self._bake(obj, keep_location=True)

    @staticmethod
    def _bake(obj, keep_location: bool = True):
        """Apply rotation and scale into the mesh (contract: scale 1); location stays on the object."""
        if obj.type != "MESH":
            return
        m = Matrix.LocRotScale(None, obj.rotation_euler, obj.scale) if hasattr(Matrix, "LocRotScale") else \
            obj.rotation_euler.to_matrix().to_4x4() @ Matrix.Diagonal((*obj.scale, 1))
        if any(abs(s - 1) > 1e-9 for s in obj.scale) or any(abs(r) > 1e-9 for r in obj.rotation_euler):
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            obj.data.transform(m)
            if obj.scale.x * obj.scale.y * obj.scale.z < 0:
                Kit._flip(obj.data)
            obj.rotation_euler = (0, 0, 0)
            obj.scale = (1, 1, 1)

    @staticmethod
    def _apply_modifiers(obj):
        for m in list(obj.modifiers):
            try:
                with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
                    bpy.ops.object.modifier_apply(modifier=m.name)
            except RuntimeError as exc:   # a modifier with nothing to do (e.g. 0 subdivision levels) is "disabled"
                if "disabled" not in str(exc):
                    raise
                obj.modifiers.remove(m)

    def _finish_piece(self, obj, color, smooth: bool, flat_faces=()):
        me = obj.data
        self._label(obj)
        smooth = smooth and not self._faceted
        flat = set(flat_faces)
        for p in me.polygons:
            p.use_smooth = bool(smooth) and p.index not in flat
        if smooth and hasattr(me, "use_auto_smooth"):   # ≤ 4.0: keep caps and hard corners crisp
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(40)
        elif smooth and hasattr(me, "set_sharp_from_angle"):   # 4.1+: same, as sharp edges (glTF splits normals there)
            me.set_sharp_from_angle(angle=math.radians(40))
        name = self._color_name(color)
        u, v = self._cell_uv(name)
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        for loop in me.uv_layers.active.data:
            loop.uv = (u, v)
        me.materials.clear()
        if self._vertex:
            c = self._colors[name]
            attr = me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
            lin = [_linear(x) for x in c["rgb"]] + [1.0]
            attr.data.foreach_set("color", lin * len(attr.data))
            me.materials.append(self._group_material(name))
        else:
            me.materials.append(self._mat)

    def _label(self, obj) -> None:
        """Mark a piece with the line of build code that made it (an integer vertex attribute that survives joins),
        so geometry facts can point the AI at its own code: 'the part from line 88 floats 3 cm above the rest'."""
        import inspect
        line, what = 0, "piece"
        for fr in inspect.stack()[1:12]:
            if fr.filename == "<generated>":
                line = fr.lineno
                break
            if fr.function in _PUBLIC and what == "piece":
                what = fr.function
        me = obj.data
        attr = me.attributes.get(SRC_ATTR) or me.attributes.new(SRC_ATTR, "INT", "POINT")
        attr.data.foreach_set("value", [line] * len(me.vertices))
        if line:
            self._sources.setdefault(line, what)

    def _group_material(self, name: str):
        """Vertex mode: the material for a colour — shared by every colour with the same metal and glow."""
        c = self._colors[name]
        key = ("metal" if c["metal"] >= 0.5 else "base", tuple(round(x, 3) for x in c["rgb"]) if c["glow"] > 0 else None)
        if key not in self._groups:
            label = key[0] if key[1] is None else f"glow{sum(1 for k in self._groups if k[1] is not None) + 1}"
            m = bpy.data.materials.new(f"{self._name}_{label}")
            m.use_nodes = True
            m.use_backface_culling = True
            nt = m.node_tree
            b = compat.principled(m)
            vc = nt.nodes.new("ShaderNodeVertexColor")
            vc.layer_name = "Col"
            vc.location = (-400, 200)
            nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
            b.inputs["Metallic"].default_value = 1.0 if key[0] == "metal" else 0.0
            if key[1] is not None:
                compat.set_input(b, "Emission Color", tuple(_linear(x) for x in c["rgb"]) + (1.0,))
                b.inputs["Emission Strength"].default_value = c["glow"]
            self._groups[key] = {"mat": m, "rough": []}
        self._groups[key]["rough"].append(c["rough"])
        return self._groups[key]["mat"]

    def _fold_groups(self) -> None:
        """Vertex mode on a tier with fewer materials allowed (mobile-low: 2): fold the smallest groups into the plain
        one. Their colour stays in the vertices; only metal and glow of those parts are lost."""
        if not self._max_materials or len(self._groups) <= self._max_materials:
            return
        base_key = ("base", None)
        if base_key not in self._groups:
            base_key = max(self._groups, key=lambda k: len(self._groups[k]["rough"]))
        base = self._groups[base_key]
        for key in sorted((k for k in self._groups if k != base_key), key=lambda k: len(self._groups[k]["rough"])):
            if len(self._groups) <= self._max_materials:
                break
            gone = self._groups.pop(key)
            base["rough"] += gone["rough"]
            for o in bpy.context.scene.objects:
                if o.type == "MESH":
                    for slot in o.material_slots:
                        if slot.material == gone["mat"]:
                            slot.material = base["mat"]
            bpy.data.materials.remove(gone["mat"])

    def _color_name(self, color) -> str:
        if isinstance(color, str) and color in self._colors:
            return color
        if isinstance(color, str) and not color.startswith("#"):
            raise ModelError(f"colour '{color}' is not defined — call mg.color('{color}', (r, g, b)) first")
        rgb = _rgb(color)
        key = "c_" + "".join(f"{round(c * 255):02x}" for c in rgb)
        return self.color(key, rgb)

    def _cell_uv(self, name: str) -> tuple[float, float]:
        i = self._colors[name]["index"]
        return ((i % CELLS) + 0.5) / CELLS, ((i // CELLS) + 0.5) / CELLS

    @staticmethod
    def _bounds(objs):
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return lo, hi

    def _image(self, suffix: str, fill, non_color: bool):
        px, cell = PALETTE_PX, PALETTE_PX // CELLS
        buf = [0.0] * (px * px * 4)
        for c in self._colors.values():
            rgba = fill(c)
            cx, cy = c["index"] % CELLS, c["index"] // CELLS   # Blender images are bottom-up: row 0 is the bottom
            for y in range(cy * cell, (cy + 1) * cell):
                row = (y * px + cx * cell) * 4
                buf[row:row + cell * 4] = rgba * cell
        for i in range(3, len(buf), 4):
            buf[i] = 1.0
        img = bpy.data.images.new(f"{self._name}_{suffix}", px, px, alpha=False)
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(buf)
        path = os.path.join(self._tmp, f"{self._name}_{suffix}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.pack()
        img.filepath_raw = f"//textures/{self._name}_{suffix}.png"
        return img

    def _make_palette(self):
        if not self._colors:
            self.color("default", (0.7, 0.7, 0.7))
        if self._vertex:   # no textures: set each group's roughness to the mean of its colours
            self._fold_groups()
            for g in self._groups.values():
                compat.principled(g["mat"]).inputs["Roughness"].default_value = sum(g["rough"]) / len(g["rough"])
            return self._mat
        nt = self._mat.node_tree
        b = compat.principled(self._mat)
        base = self._image("basecolor", lambda c: list(c["rgb"]) + [1.0], False)
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = base; tex.interpolation = "Closest"; tex.location = (-600, 300)
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        # glTF metallicRoughness: G = roughness, B = metallic, read through Separate Color
        orm = self._image("orm", lambda c: [material_code(c.get("material", "plain")), c["rough"], c["metal"], 1.0], True)
        t2 = nt.nodes.new("ShaderNodeTexImage"); t2.image = orm; t2.interpolation = "Closest"; t2.location = (-600, 0)
        sep = nt.nodes.new("ShaderNodeSeparateColor"); sep.location = (-300, 0)
        nt.links.new(t2.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], b.inputs["Roughness"])
        nt.links.new(sep.outputs[2], b.inputs["Metallic"])
        peak = max(c["glow"] for c in self._colors.values())
        if peak > 0:
            emi = self._image("emissive", lambda c: [x * c["glow"] / peak for x in c["rgb"]] + [1.0], False)
            t3 = nt.nodes.new("ShaderNodeTexImage"); t3.image = emi; t3.interpolation = "Closest"; t3.location = (-600, -300)
            nt.links.new(t3.outputs["Color"], compat.socket(b, "Emission Color"))
            b.inputs["Emission Strength"].default_value = peak
        return self._mat


def _preset(motion: str, bones: list, k: float) -> dict:
    """Keyframes for a named motion over the humanoid bones present: {frame: {bone: (x, y, z) world degrees}}."""
    tails = [b for b in bones if b.startswith("Tail")]
    out: dict = {}

    def put(f, b, v):
        if b in bones or b == "Hips_move":
            out.setdefault(f, {})[b] = tuple(x * k for x in v) if b != "Hips_move" else tuple(x * k for x in v)
    if motion in ("zombie_walk", "walk"):
        n = 36 if motion == "zombie_walk" else 30
        zombie = motion == "zombie_walk"
        for f in range(0, n + 1, 3):
            ph = 2 * math.pi * f / n
            s, c = math.sin(ph), math.cos(ph)
            swing = 22 if zombie else 28
            put(f, "LeftUpperLeg", (-swing * s, 0, 0))
            put(f, "RightUpperLeg", (swing * s, 0, 0))
            put(f, "LeftLowerLeg", (30 * max(0.0, -c) + 5, 0, 0))
            put(f, "RightLowerLeg", (30 * max(0.0, c) + 5, 0, 0))
            put(f, "Hips", (0, 5 * s if zombie else 2 * s, 6 * s))
            put(f, "Hips_move", (0, 0, -0.012 * math.cos(2 * ph)))
            put(f, "Spine", (4 if zombie else 0, 0, -3 * s))
            put(f, "Chest", (10 if zombie else 2, -3 * s if zombie else 0, -4 * s))
            put(f, "Head", (6 * math.sin(2 * ph) + (8 if zombie else 0), 14 * s if zombie else 0, 0))
            if zombie:   # arms held out, bobbing out of step
                put(f, "LeftUpperArm", (6 * math.sin(ph + 1.5), 0, 3 * s))
                put(f, "RightUpperArm", (6 * math.sin(ph - 1.5), 0, 3 * s))
                put(f, "LeftLowerArm", (-5 * max(0.0, s), 0, 0))
                put(f, "RightLowerArm", (-5 * max(0.0, -s), 0, 0))
            else:
                put(f, "LeftUpperArm", (25 * s, 0, 0))
                put(f, "RightUpperArm", (-25 * s, 0, 0))
            for i, t in enumerate(tails):
                put(f, t, (0, 0, 16 * math.sin(ph - 0.7 * (i + 1))))
    elif motion == "idle":
        for f in range(0, 61, 6):
            ph = 2 * math.pi * f / 60
            s = math.sin(ph)
            put(f, "Chest", (3 * s, 0, 0))
            put(f, "Spine", (1.5 * s, 0, 0))
            put(f, "Head", (-2 * s, 5 * math.sin(ph + 0.8), 0))
            put(f, "LeftUpperArm", (-3 * s, 0, 0))
            put(f, "RightUpperArm", (-3 * math.sin(ph + 0.6), 0, 0))
            for i, t in enumerate(tails):
                put(f, t, (0, 0, 10 * math.sin(ph - 0.6 * (i + 1))))
    elif motion == "attack":
        poses = {0: (0, 0, 0, 0), 8: (-45, -10, -10, 0.0), 13: (40, 20, 15, -0.05), 18: (-20, 5, -5, -0.04),
                 22: (45, 25, 18, -0.06), 30: (0, 0, 0, 0)}
        for f, (arm, chest, head, lunge) in poses.items():
            put(f, "LeftUpperArm", (arm, 0, 0))
            put(f, "RightUpperArm", (arm * (0.6 if f in (13, 18) else 1.0), 0, 0))
            put(f, "LeftLowerArm", (max(0, arm) * 0.3, 0, 0))
            put(f, "RightLowerArm", (max(0, arm) * 0.3, 0, 0))
            put(f, "Chest", (chest, 0, 0))
            put(f, "Head", (head, 0, 0))
            put(f, "Hips_move", (0, lunge, 0))
            for i, t in enumerate(tails):
                put(f, t, (-chest * 0.6, 0, 0))
    elif motion == "hit":
        poses = {0: (0, 0), 4: (-16, -22), 9: (-8, -10), 14: (3, 4), 20: (0, 0)}
        for f, (chest, head) in poses.items():
            put(f, "Chest", (chest, 0, 0))
            put(f, "Spine", (chest * 0.5, 0, 0))
            put(f, "Head", (head, 0, 0))
            put(f, "LeftUpperArm", (-chest, 0, 0))
            put(f, "RightUpperArm", (-chest, 0, 0))
            put(f, "Hips_move", (0, -chest * 0.002, 0))
    return out
