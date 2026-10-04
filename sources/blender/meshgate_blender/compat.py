"""Blender version compatibility (3.5 … 5.x).

Everything that changed between versions and that MeshGate touches lives here, so the rest of the
add-on (and the demo generators) can stay version-agnostic:
  • Principled BSDF socket names (4.0 renamed Emission → Emission Color, Transmission → Transmission Weight …)
  • material blend mode (blend_method → surface_render_method in 4.2 EEVEE Next)
  • animation F-curves (layered/slotted actions in 4.4; Action.fcurves removed in 5.0)
  • exporter operator keywords (glTF/FBX options appear and disappear between releases)
"""

from __future__ import annotations

import bpy

VERSION = tuple(bpy.app.version)

_SOCKET_ALIASES = {
    "Emission": ("Emission Color", "Emission"),
    "Emission Color": ("Emission Color", "Emission"),
    "Transmission": ("Transmission Weight", "Transmission"),
    "Specular": ("Specular IOR Level", "Specular"),
    "Subsurface": ("Subsurface Weight", "Subsurface"),
    "Clearcoat": ("Coat Weight", "Clearcoat"),
    "Sheen": ("Sheen Weight", "Sheen"),
}


def principled(material: bpy.types.Material):
    """First Principled BSDF node of a node material, or None."""
    if not material or not material.use_nodes or not material.node_tree:
        return None
    return next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def socket(node: bpy.types.Node, name: str):
    """Input socket by its 3.x or 4.x+ name."""
    for candidate in _SOCKET_ALIASES.get(name, (name,)):
        s = node.inputs.get(candidate)
        if s is not None:
            return s
    raise KeyError(f"Principled BSDF has no input '{name}' in Blender {bpy.app.version_string}")


def set_input(node: bpy.types.Node, name: str, value) -> None:
    socket(node, name).default_value = value


def set_blend(material: bpy.types.Material, mode: str) -> None:
    """mode: 'OPAQUE' | 'BLEND' | 'CLIP'. glTF alphaMode follows the Alpha socket in 4.2+, this keeps EEVEE in sync."""
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = mode
        except (TypeError, AttributeError):
            pass
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "BLENDED" if mode == "BLEND" else "DITHERED"


def uses_alpha(material: bpy.types.Material | None) -> bool:
    """Does the material need an alpha channel in the export? The Alpha socket decides (linked or < 1).
    Before 4.2 an explicit blend_method also counts; from 4.2 new materials default to blend_method HASHED
    (EEVEE Next "Dithered", which is opaque), so only surface_render_method BLENDED counts there."""
    if material is None:
        return False
    b = principled(material)
    a = b.inputs.get("Alpha") if b else None
    if a is not None and (a.is_linked or a.default_value < 0.999):
        return True
    if hasattr(material, "surface_render_method"):
        return material.surface_render_method == "BLENDED"
    return getattr(material, "blend_method", "OPAQUE") in {"BLEND", "CLIP", "HASHED"}


def fcurves(action: bpy.types.Action | None) -> list:
    """All F-curves of an action — legacy (≤ 4.3) or layered/slotted (4.4+)."""
    if action is None:
        return []
    out = []
    for layer in getattr(action, "layers", []) or []:
        for strip in getattr(layer, "strips", []) or []:
            for bag in getattr(strip, "channelbags", []) or []:
                out.extend(bag.fcurves)
    if out:
        return out
    legacy = getattr(action, "fcurves", None)
    return list(legacy) if legacy is not None else []


def set_interpolation(action: bpy.types.Action, interpolation: str = "BEZIER", easing: str | None = None) -> None:
    for fc in fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            if easing:
                kp.easing = easing


def animates(obj: bpy.types.Object, data_path: str) -> bool:
    """True if the object's active action or any NLA strip keys `data_path` (e.g. 'scale')."""
    ad = obj.animation_data
    if not ad:
        return False
    actions = [ad.action] if ad.action else []
    actions += [s.action for t in ad.nla_tracks for s in t.strips if s.action]
    return any(fc.data_path == data_path for a in actions for fc in fcurves(a))


def push_to_nla(obj: bpy.types.Object, name: str | None = None) -> None:
    """Move the active action into an NLA strip of the same name (one clip per strip in glTF and FBX)."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    action = ad.action
    track = ad.nla_tracks.new()
    track.name = name or action.name
    strip = track.strips.new(name or action.name, int(action.frame_range[0]), action)
    strip.name = name or action.name
    ad.action = None


def operator_kwargs(op, **kwargs) -> tuple[dict, list[str]]:
    """Keep only keywords the operator knows in this Blender; return (kwargs, dropped names)."""
    known = {p.identifier for p in op.get_rna_type().properties}
    kept = {k: v for k, v in kwargs.items() if k in known}
    return kept, sorted(set(kwargs) - set(kept))


def smooth_mesh(mesh: bpy.types.Mesh) -> None:
    for p in mesh.polygons:
        p.use_smooth = True
