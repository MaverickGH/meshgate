"""MeshGate live link: an AI tool drives this Blender through the kit, seeing what it builds.

A small server on localhost (a random port and token, written to ~/.meshgate/blender_link.json) takes one JSON request
per line and answers with one JSON line. `meshgate.py mcp` turns these into MCP tools for Claude Code and other AI
clients. Requests:

    {"token": …, "cmd": "info"}                                  the live scene: objects, sizes, triangles
    {"token": …, "cmd": "run", "code": "def build(mg): …", "tier": "pc", "look": "none"}
                                                                   build kit code into the "MeshGate live" scene
    {"token": …, "cmd": "facts"}                                 measured facts: floating pieces, triangles per line…
    {"token": …, "cmd": "measure", "a": "line 9", "b": "line 15"} the gap between two parts (build lines or objects)
    {"token": …, "cmd": "render", "closeups": [...]}             a sheet of four views (+ close-ups), as a PNG path
    {"token": …, "cmd": "export", "path": "…/asset.glb"}         a checked GLB (+ FBX) by the MeshGate contract

Only kit code runs (the same guard rails as `meshgate.py gen`): no raw bpy, no files, no network. Builds go to their
own scene, so the artist's scene is never touched. In the open Blender the server runs beside the UI (requests are
handled on Blender's main thread by a timer); a background Blender serves with serve_forever().
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import math
import os
import queue
import random
import secrets
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import bpy
import mathutils

from . import export, modeling

HERE = Path(__file__).resolve().parent
LIVE_SCENE = "MeshGate live"
_state: dict = {"server": None, "thread": None, "queue": None, "token": None, "port": None}


def link_file() -> Path:
    base = os.environ.get("MESHGATE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".meshgate")
    return Path(base) / "blender_link.json"


def _safety():
    here = HERE / "kitlib" / "safety.py"
    src = here if here.exists() else HERE.parents[1] / "generate" / "safety.py"
    spec = importlib.util.spec_from_file_location("meshgate_live_safety", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _window():
    if bpy.app.background:   # a background Blender has a stand-in window; switching its scene crashes the exporter
        return None
    wm = bpy.context.window_manager
    return bpy.context.window or (wm.windows[0] if wm and len(wm.windows) else None)


def _live_scene(clear: bool) -> bpy.types.Scene:
    """The scene live builds go to. A background Blender is ours alone: its scene becomes the live one. In the open
    Blender a scene of its own, shown in the window — the artist's scene stays as it was."""
    win = _window()
    if win is None:
        scene = bpy.context.scene
        scene.name = LIVE_SCENE
    else:
        scene = bpy.data.scenes.get(LIVE_SCENE) or bpy.data.scenes.new(LIVE_SCENE)
        win.scene = scene
    if clear:
        for o in list(scene.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    return scene


def _in_scene(scene):
    """A context for the kit: the window showing the live scene, or (background) the scene itself."""
    win = _window()
    if win is not None:
        return bpy.context.temp_override(window=win, scene=scene, view_layer=scene.view_layers[0])
    return contextlib.nullcontext()   # background: the live scene is the current one; an override without a
    #                                   window crashes the glTF exporter (it sets context.window.scene)


def _scene_objects():
    scene = bpy.data.scenes.get(LIVE_SCENE) or bpy.context.scene
    return scene, [o for o in scene.objects if o.type in ("MESH", "ARMATURE", "EMPTY")]


# ---------------------------------------------------------------------------- commands (main thread)

def cmd_info(req: dict) -> dict:
    scene, objs = _scene_objects()
    out = []
    for o in objs:
        item = {"name": o.name, "type": o.type, "location": [round(x, 4) for x in o.matrix_world.translation]}
        if o.type == "MESH":
            pts = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
            item["size_m"] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(3)]
            item["tris"] = sum(len(p.vertices) - 2 for p in o.data.polygons)
            item["materials"] = [m.name for m in o.data.materials if m]
        out.append(item)
    return {"scene": scene.name, "objects": out, "tris": sum(i.get("tris", 0) for i in out)}


def cmd_run(req: dict) -> dict:
    code = str(req.get("code") or "")
    safety = _safety()
    problems = safety.check(code)
    if problems:
        return {"ok": False, "problems": [f"safety: {p}" for p in problems]}
    tier = req.get("tier") if req.get("tier") in modeling.TIERS else "pc"
    look = req.get("look") if req.get("look") in ("none", "faceted") else "none"
    scene = _live_scene(clear=True)
    with _in_scene(scene):
        budget = export.load_profiles()["profiles"][tier]["asset"]
        kit = modeling.Kit(tier, name=str(req.get("name") or "live"), max_materials=budget["max_materials"], finish=look,
                           max_tris=budget["max_tris"], params=req.get("params") or {})
        g = safety.restricted_globals({"math": math, "random": random, "mathutils": mathutils})
        try:
            exec(compile(code, "<generated>", "exec"), g)  # noqa: S102 — passed safety.check above
            g["build"](kit)
            notes = kit._finalize()
        except Exception as exc:  # noqa: BLE001 — the error goes back to the AI
            import traceback
            frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<generated>"]
            where = f"line {frames[-1].lineno}: " if frames else ""
            return {"ok": False, "problems": [f"{where}{type(exc).__name__}: {exc}"]}
        facts = kit._facts()
    info = cmd_info({})
    return {"ok": True, "notes": notes, "facts": facts, "tris": info["tris"], "size_m": facts.get("size_m"),
            "params": kit._params, "budget_tris": budget["max_tris"]}


def cmd_facts(req: dict) -> dict:
    scene, _ = _scene_objects()
    with _in_scene(scene):
        kit = modeling.Kit.__new__(modeling.Kit)   # facts only: no palette, no scene reset
        kit._sources = {}
        return kit._facts()


def _part(spec: str, objs):
    """One part in world space as (vertices, faces): an object by name, or "line N" — what line N of the build code
    made (the pieces are merged into one mesh at the end; the line labels stay)."""
    spec = spec.strip()
    words = spec.split()
    line = int(words[-1]) if len(words) == 2 and words[0].lower() == "line" and words[1].isdigit() else None
    verts, faces = [], []
    for o in objs:
        if o.type != "MESH" or (line is None and o.name != spec):
            continue
        me, base = o.data, len(verts)
        keep = None
        if line is not None:
            src = me.attributes.get(modeling.SRC_ATTR)
            if src is None:
                continue
            keep = {k for k, d in enumerate(src.data) if d.value == line}
        verts += [tuple(o.matrix_world @ v.co) for v in me.vertices]
        faces += [tuple(base + k for k in p.vertices) for p in me.polygons
                  if keep is None or all(k in keep for k in p.vertices)]
    return verts, faces


def cmd_measure(req: dict) -> dict:
    from mathutils.bvhtree import BVHTree
    scene, objs = _scene_objects()
    a, b = str(req.get("a") or ""), str(req.get("b") or "")
    (va, fa), (vb, fb) = _part(a, objs), _part(b, objs)
    if not fa or not fb:
        names = sorted(o.name for o in objs if o.type == "MESH")
        return {"ok": False, "problems": [f"nothing found for '{a if not fa else b}' — give an object name "
                                          f"({', '.join(names)[:300]}) or \"line N\" of the build code"]}
    ta, tb = BVHTree.FromPolygons(va, fa), BVHTree.FromPolygons(vb, fb)
    overlap = bool(ta.overlap(tb))

    def nearest(vs, fs, other):   # closest a vertex of one part comes to the other's surface
        pts = sorted({k for f in fs for k in f})
        return min((other.find_nearest(mathutils.Vector(vs[k]))[3] or 0.0) for k in pts[::max(1, len(pts) // 3000)])
    gap = 0.0 if overlap else min(nearest(va, fa, tb), nearest(vb, fb, ta))
    return {"ok": True, "gap_m": round(gap, 5), "overlap": overlap, "touching": overlap or gap < 0.003}


def cmd_render(req: dict) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="meshgate-live-"))
    glb = tmp / "live.glb"
    scene, objs = _scene_objects()
    with _in_scene(scene):
        export._gltf(str(glb), selection=False, animations=False, draco=False)
    out = tmp / "views.png"
    script = HERE / "kitlib" / "render_views.py"
    if not script.exists():
        script = HERE.parents[1] / "generate" / "render_views.py"
    subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "-P", str(script), "--", str(glb), str(out),
                    str(int(req.get("px") or 1024)), str(int(req.get("samples") or 24)), "",
                    json.dumps(req.get("closeups") or [])], capture_output=True, timeout=900)
    return {"ok": out.exists(), "image": str(out) if out.exists() else None}


def cmd_export(req: dict) -> dict:
    path = str(req.get("path") or "")
    if not path.lower().endswith(".glb"):
        return {"ok": False, "problems": ["give a path ending in .glb"]}
    scene, objs = _scene_objects()
    with _in_scene(scene):
        res = export.export_asset(bpy.context, path, targets=["web", "unity", "godot", "unreal"], fbx=True, validate=True)
    return {"ok": res.ok, "files": res.files, "summary": export.summary_lines(res)}


COMMANDS = {"info": cmd_info, "run": cmd_run, "facts": cmd_facts, "measure": cmd_measure, "render": cmd_render,
            "export": cmd_export}


def handle(req: dict) -> dict:
    if req.get("token") != _state["token"]:
        return {"ok": False, "problems": ["wrong token"]}
    fn = COMMANDS.get(str(req.get("cmd")))
    if fn is None:
        return {"ok": False, "problems": [f"unknown command — use {', '.join(COMMANDS)}"]}
    try:
        return fn(req)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "problems": [f"{type(exc).__name__}: {exc}"]}


# ---------------------------------------------------------------------------- the server

def _accept_loop(srv: socket.socket, q: "queue.Queue"):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=_client, args=(conn, q), daemon=True).start()


def _client(conn: socket.socket, q: "queue.Queue"):
    with conn:
        buf = b""
        while True:
            try:
                chunk = conn.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    req = json.loads(line)
                except ValueError:
                    conn.sendall(b'{"ok": false, "problems": ["send one JSON object per line"]}\n')
                    continue
                done = threading.Event()
                box: dict = {}
                q.put((req, box, done))   # Blender's data is only touched on its main thread
                done.wait()
                conn.sendall((json.dumps(box.get("reply", {}), default=str) + "\n").encode())


def _drain(q) -> None:
    while True:
        try:
            req, box, done = q.get_nowait()
        except queue.Empty:
            return
        box["reply"] = handle(req)
        done.set()


def start(port: int = 0) -> dict:
    """Start the live link (once); returns {port, token} and writes them to ~/.meshgate/blender_link.json."""
    if _state["server"]:
        return {"port": _state["port"], "token": _state["token"]}
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(4)
    q: queue.Queue = queue.Queue()
    _state.update(server=srv, queue=q, token=secrets.token_urlsafe(24), port=srv.getsockname()[1])
    _state["thread"] = threading.Thread(target=_accept_loop, args=(srv, q), daemon=True)
    _state["thread"].start()
    path = link_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"port": _state["port"], "token": _state["token"], "pid": os.getpid(),
                                "blender": bpy.app.version_string}), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    if not bpy.app.background:
        bpy.app.timers.register(_tick, persistent=True)
    return {"port": _state["port"], "token": _state["token"]}


def _tick():
    if not _state["server"]:
        return None
    _drain(_state["queue"])
    return 0.1


def serve_forever() -> None:
    """Background Blender: keep answering until stopped (Ctrl-C or the process ends)."""
    import time
    start()
    print(f"MeshGate live link on 127.0.0.1:{_state['port']} (token in {link_file()})", flush=True)
    while _state["server"]:
        _drain(_state["queue"])
        time.sleep(0.05)


def stop() -> None:
    srv = _state.get("server")
    if srv:
        try:
            srv.close()
        except OSError:
            pass
    _state.update(server=None, queue=None, token=None, port=None)
    try:
        if json.loads(link_file().read_text()).get("pid") == os.getpid():
            link_file().unlink()
    except (OSError, ValueError):
        pass


def running() -> bool:
    return bool(_state["server"])
