"""Engine-readiness tools: collision proxies, LOD meshes, browser preview.

Proxies and LODs are ordinary hidden-from-render meshes tagged with custom properties, so the canonical
GLB never contains them; export.py renames and reveals them only for the engine variant that needs them.
"""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import socket
import threading
import webbrowser

import bpy
import bmesh


def _wire(obj):
    obj.display_type = "WIRE"
    obj.hide_render = True
    obj.show_in_front = True


def add_collision(context, targets, shape: str = "CONVEX") -> list[bpy.types.Object]:
    """For each mesh: a child proxy (convex hull or box) in the mesh's own space, tagged meshgate_collision_for."""
    made = []
    for src in [o for o in targets if o.type == "MESH" and not o.get("meshgate_collision_for")]:
        for old in [c for c in src.children if c.get("meshgate_collision_for") == src.name]:
            bpy.data.objects.remove(old, do_unlink=True)
        bm = bmesh.new()
        if shape == "BOX":
            xs, ys, zs = zip(*[v.co for v in src.data.vertices]) if src.data.vertices else ((0,), (0,), (0,))
            lo = (min(xs), min(ys), min(zs)); hi = (max(xs), max(ys), max(zs))
            verts = [bm.verts.new((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
            bmesh.ops.convex_hull(bm, input=verts)
        else:
            for v in src.data.vertices:
                bm.verts.new(v.co)
            if len(bm.verts) >= 4:
                bmesh.ops.convex_hull(bm, input=list(bm.verts))
            # keep engines happy: UE caps convex hulls, Godot is fine, but fewer faces is always cheaper
            if len(bm.faces) > 250:
                bmesh.ops.dissolve_limit(bm, angle_limit=0.087, verts=list(bm.verts), edges=list(bm.edges))
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        mesh = bpy.data.meshes.new(f"COL_{src.name}")
        bm.to_mesh(mesh); bm.free()
        mesh.uv_layers.new(name="UVMap")   # engines and the validator expect UVs on every exported mesh
        proxy = bpy.data.objects.new(f"COL_{src.name}", mesh)
        for coll in src.users_collection:
            coll.objects.link(proxy)
        proxy.parent = src
        proxy.matrix_parent_inverse.identity()
        proxy["meshgate_collision_for"] = src.name
        _wire(proxy)
        made.append(proxy)
    return made


def make_lods(context, targets, ratios=(0.5, 0.25)) -> list[bpy.types.Object]:
    """Decimated copies `<name>_LODn` next to the source (same parent and transform), hidden from render."""
    made = []
    for src in [o for o in targets if o.type == "MESH" and not o.get("meshgate_lod_of") and not o.get("meshgate_collision_for")]:
        for old in [o for o in context.scene.objects if o.get("meshgate_lod_of") == src.name]:
            bpy.data.objects.remove(old, do_unlink=True)
        for level, ratio in enumerate(ratios, start=1):
            lod = src.copy()
            lod.data = src.data.copy()
            lod.name = f"{src.name}_LOD{level}"
            lod.animation_data_clear()
            for coll in src.users_collection:
                coll.objects.link(lod)
            lod.parent = src.parent
            lod.matrix_world = src.matrix_world.copy()
            if lod.data.shape_keys:   # a decimation cannot apply over shape keys: the morphs come back after it
                lod.shape_key_clear()
            dec = lod.modifiers.new("meshgate_lod", "DECIMATE")
            dec.ratio = ratio
            with context.temp_override(object=lod, active_object=lod, selected_objects=[lod]) if hasattr(context, "temp_override") else _legacy_override(context, lod):
                bpy.ops.object.modifier_apply(modifier=dec.name)
            if lod.get("meshgate_morphs"):   # spatial morphs fit the lighter copy as they fit the tier
                from . import morphs
                morphs.reapply(lod)
            lod["meshgate_lod_of"] = src.name
            lod["meshgate_lod_level"] = level
            lod.hide_render = True
            lod.hide_set(True)
            made.append(lod)
    return made


class _legacy_override:  # Blender < 3.2 has no temp_override; select + activate instead
    def __init__(self, context, obj):
        self.context, self.obj = context, obj

    def __enter__(self):
        for o in self.context.view_layer.objects:
            o.select_set(False)
        self.obj.select_set(True)
        self.context.view_layer.objects.active = self.obj

    def __exit__(self, *exc):
        return False


# ----------------------------------------------------------------------------
# browser preview: serve the export folder + the bundled viewer from inside Blender
# ----------------------------------------------------------------------------

_server = None
_server_root = None


def _viewer_source() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "viewer"), os.path.join(here, "..", "..", "..", "targets", "web")):
        if os.path.isfile(os.path.join(candidate, "meshgate-viewer.js")):
            return candidate
    return None


def _free_port(preferred: int = 8771) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return 0


def preview(glb_path: str) -> str:
    """Copy the viewer next to the GLB, serve that folder on localhost, open the browser. Returns the URL."""
    global _server, _server_root
    glb_path = os.path.abspath(bpy.path.abspath(glb_path))
    root = os.path.dirname(glb_path)
    src = _viewer_source()
    if not src:
        raise RuntimeError("viewer files are not bundled with this add-on build")
    dest = os.path.join(root, "_meshgate_viewer")
    os.makedirs(dest, exist_ok=True)
    for name in ("index.html", "app.js", "meshgate-viewer.js"):
        shutil.copy2(os.path.join(src, name), os.path.join(dest, name))
    if _server is None or _server_root != root:
        stop_preview()
        handler = functools.partial(_QuietHandler, directory=root)
        port = _free_port()
        _server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        _server_root = root
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{_server.server_address[1]}/_meshgate_viewer/index.html?glb=/{os.path.basename(glb_path)}"
    webbrowser.open(url)
    return url


def stop_preview() -> None:
    global _server, _server_root
    if _server is not None:
        _server.shutdown()
        _server.server_close()
    _server = None
    _server_root = None


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".glb": "model/gltf-binary", ".js": "text/javascript", ".hdr": "image/vnd.radiance"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass
