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


def _seg_distance(p, a, b) -> float:
    """Distance from point p to the segment a–b (sculpt crease)."""
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def _paint_layer(me):
    """An empty soft-paint layer (Blender fills new colour layers with opaque white; this one starts clear)."""
    from .finish import PAINT_ATTR
    layer = me.color_attributes.new(PAINT_ATTR, "FLOAT_COLOR", "POINT")
    layer.data.foreach_set("color", [0.0] * (4 * len(layer.data)))
    return layer


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


class Kit:
    """The `mg` object passed to build(mg)."""

    def __init__(self, tier: str = "pc", seed: int = 1, name: str = "asset", tmp: str | None = None,
                 colors: str = "texture", max_materials: int | None = None, finish: str = "none"):
        if tier not in DETAILS:
            raise ModelError(f"unknown tier {tier}")
        # "texture": one palette material with base colour / roughness-metallic / emission textures (default).
        # "vertex": no textures at all — each part's colour goes into the COLOR_0 vertex attribute, and parts share a
        # few materials grouped by metal and glow (glTF has no per-vertex roughness, so it is averaged per group).
        self._vertex = colors == "vertex"
        self._groups: dict = {}
        self._max_materials = max_materials
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
        self._frame_end = 1
        self._mat = bpy.data.materials.new(f"{name}_palette")
        self._mat.use_nodes = True
        self._mat.use_backface_culling = True   # closed meshes: single-sided in glTF (cheaper on every engine)
        self._reset_scene()

    # ------------------------------------------------------------------ public API

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
        "rust", "fabric", "ground", "bone" or "plain"; by default it is read from the name (wood_dark → wood,
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

    def part(self, kind: str, color, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), *, smooth: bool | None = None,
             subdiv: int = 0, bevel: float = 0.0, taper: float | None = None, exact: bool = False, **size):
        """One primitive piece. kind: "cube" (1 m edge), "sphere" and "ico" (radius 0.5), "cyl" and "cone" (radius 0.5,
        depth 1, along Z), "torus" (major 1, minor 0.25, lies in XY), "plane" (1 m), all centred on `loc` before scaling.
        scale = size along the primitive's OWN axes before rotation: scale=(0.2, 0.2, 1.5) + rot=(0, math.pi/2, 0) is a
        cylinder 0.2 m thick and 1.5 m long lying along X. rot = Euler radians (x, y, z). For a rod between two points use
        tube([a, b], radius). smooth = smooth shading (default: round kinds).
        subdiv = subdivision levels (tier-adjusted), bevel = bevel width in meters for crisp but soft edges.
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
            m.segments = self._detail["bevel"]
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

    def join(self, name: str, parts):
        """Merge pieces into one mesh object named `name`, origin at the world origin. One mesh per rigid part:
        join everything that never moves separately (a whole prop is usually one join)."""
        from .finish import PAINT_ATTR
        meshes_ = [p for p in parts if getattr(p, "type", None) == "MESH"]
        if any(p.data.color_attributes.get(PAINT_ATTR) for p in meshes_):
            for p in meshes_:
                if not p.data.color_attributes.get(PAINT_ATTR):
                    if p.data.users > 1:
                        p.data = p.data.copy()
                    _paint_layer(p.data)
        parts = [p for p in parts if p is not None]
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
        continuous spin key 0 → ±2π with smooth=False (the wrap is seamless)."""
        if path not in {"rotation_euler", "location", "scale"}:
            raise ModelError("animate path must be rotation_euler, location or scale")
        ad = obj.animation_data or obj.animation_data_create()
        ad.action = bpy.data.actions.new(f"{self._ascii(clip)}_{obj.name}")
        obj.rotation_mode = "XYZ"
        rest = tuple(getattr(obj, path))
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
        wanted = max(extent / cells, 0.002)
        thinnest = min((float(sh["r"]) if "r" in sh else min(float(v) for v in sh["size"])) for sh in shapes if not sh.get("cut"))
        res = max(min(wanted, thinnest * 0.6), 0.002)   # a grid coarser than a paw or an arm would lose it
        mb.resolution = mb.render_resolution = res
        obj = bpy.data.objects.new(f"mgblob{self._blobs}", mb)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        bpy.data.objects.remove(obj)
        bpy.data.metaballs.remove(mb)
        if not me.polygons:
            raise ModelError("blob() made no surface — shapes too small, or all of them cut")
        out = bpy.data.objects.new(f"blob{self._blobs}", me)
        bpy.context.collection.objects.link(out)
        if res < wanted * 0.8:   # built finer to keep thin parts: thin it back to the tier's density
            dec = out.modifiers.new("tier", "DECIMATE")
            dec.ratio = max(0.02, (res / wanted) ** 2)
            self._apply_modifiers(out)
        self._fix_normals(out)
        self._finish_piece(out, color, smooth)
        return out

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
        if not self._faceted:
            sub = obj.modifiers.new("smooth", "SUBSURF")
            sub.levels = sub.render_levels = {0: 1, 1: 1, 2: 2, 3: 2}[self.level]
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
        data = cutter.data
        bpy.data.objects.remove(cutter)
        if data and data.users == 0:
            bpy.data.meshes.remove(data)
        return target

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
               scale: float = 12.0):
        """Shape a smooth piece like a sculpting brush — best on blob(), skin() or subdivided parts (many vertices):
          "grab"    move the surface near `at` by the vector `to` = (x, y, z), fading out over `radius` (pull a snout)
          "inflate" push the surface near `at` out along its normals by `amount` (negative dents: cheeks, dimples)
          "crease"  press a groove `amount` deep and `radius` wide along `path` = [(x, y, z), …] (eyelids, folds, bark)
          "noise"   roughen the surface by `amount` at `scale` bumps per meter, near `at` or everywhere (stone, bark)
          "smooth"  relax the surface near `at`, or everywhere without `at`.
        All positions in world meters. Returns the piece."""
        import bmesh
        from mathutils import noise as mnoise
        self._bake(obj)
        if brush == "crease" and path:
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
        elif brush == "crease":
            line = [Vector(p) for p in (path or [])]
            if len(line) < 2:
                raise ModelError("sculpt('crease') needs path= with at least two points")
            for v in bm.verts:
                wp = mw @ v.co
                d = min(_seg_distance(wp, a, b) for a, b in zip(line, line[1:]))
                w = fall(d)
                if w:
                    v.co -= v.normal * amount * w
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
            raise ModelError(f"sculpt brush '{brush}' — use grab, inflate, crease, noise or smooth")
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
        cells = {0: 40, 1: 70, 2: 120, 3: 220}[self.level] * (0.5 if self._faceted else 1.0)
        max_edge = max(max_edge, extent / cells)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        off = obj.location
        for _ in range(rounds):
            long = [e for e in bm.edges if e.calc_length() > max_edge
                    and (near is None or near((e.verts[0].co + e.verts[1].co) / 2 + off))]
            if not long or len(bm.verts) + len(long) > self._vert_cap():
                break
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True)
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
        return obj

    def _finalize(self) -> list[str]:
        """After build(): palette textures, one root named after the asset, grounded and centred. Returns notes."""
        notes = []
        self._make_palette()
        objs = [o for o in bpy.context.scene.objects]
        meshes = [o for o in objs if o.type == "MESH"]
        if not meshes:
            raise ModelError("build(mg) made no mesh — create parts and join them")
        hidden = sum(self._cull_hidden(o) for o in meshes)
        if hidden:
            notes.append(f"removed {hidden} hidden faces (inside other pieces)")
        roots = [o for o in objs if o.parent is None]
        if len(roots) == 1:
            root = roots[0]
            root.name = self._name
            if root.type == "MESH":
                root.data.name = self._name
        else:
            root = self.group(self._name)
            for o in roots:
                self.attach(o, root)
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

    @staticmethod
    def _cull_hidden(obj, eps: float = 2e-4) -> int:
        """Delete faces that sit wholly inside another closed piece of the same mesh — an arm sunk into a body, a spine
        base inside a stem, a pot's top under the soil. Nobody sees them; they only cost triangles. Faces that cross the
        other piece's surface stay, so no hole shows. Pieces of one object move together, so animation is safe.
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
