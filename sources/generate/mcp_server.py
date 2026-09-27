#!/usr/bin/env python3
"""MeshGate MCP server: gives an AI client (Claude Code, Codex, Cursor…) live hands in Blender through the kit.

    claude mcp add meshgate -- python3 /path/to/meshgate.py mcp

Tools: kit_reference (the kit's API, rules and artist recipes), blender_build (run build(mg) code in the live scene
and get the measured facts back), blender_view (a rendered sheet of four views plus close-ups, as an image),
blender_facts, blender_measure (the gap between two parts), blender_scene, blender_export (a checked GLB + FBX).
It talks to a Blender that has the live link on (Sidebar → MeshGate → Kit → Connect AI), or starts a background
Blender itself when none is running. MCP over stdio, JSON-RPC 2.0, standard library only.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
PROTOCOL = "2024-11-05"
_headless = {"proc": None}


def link_file() -> Path:
    base = os.environ.get("MESHGATE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".meshgate")
    return Path(base) / "blender_link.json"


def _send(req: dict, timeout: float = 1800) -> dict:
    link = json.loads(link_file().read_text(encoding="utf-8"))
    with socket.create_connection(("127.0.0.1", int(link["port"])), timeout=timeout) as s:
        s.sendall((json.dumps({**req, "token": link["token"]}) + "\n").encode())
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.split(b"\n", 1)[0] or b"{}")


def _reachable() -> bool:
    try:
        return "objects" in _send({"cmd": "info"}, timeout=5)
    except (OSError, ValueError, KeyError):
        return False


def ensure_blender() -> str:
    """A live Blender to talk to: the artist's own (live link on) or a background one started here."""
    if link_file().exists() and _reachable():
        return "connected"
    import generate
    blender = generate.find_blender()
    if not blender:
        raise RuntimeError("Blender not found — install it or set MESHGATE_BLENDER, or turn the live link on in Blender")
    try:
        link_file().unlink()
    except OSError:
        pass
    _headless["proc"] = subprocess.Popen([blender, "-b", "--factory-startup", "-P", str(HERE / "live_server.py")],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(240):
        time.sleep(0.25)
        if link_file().exists() and _reachable():
            return "started a background Blender"
    raise RuntimeError("the background Blender did not start the live link")


def kit_reference() -> str:
    import generate
    rules = (HERE / "prompts" / "model.md").read_text(encoding="utf-8")
    rules = rules[rules.index("# Rules"):rules.index("# The modeling kit")] if "# Rules" in rules else ""
    recipes = sorted(p.stem for p in (HERE / "prompts" / "recipes").glob("*.md"))
    return (f"{rules}\n# The kit `mg` (build(mg) code)\n\n{generate.api_reference()}\n\n# Artist recipes\n\nAsk "
            f"kit_reference with recipe=<name> for one of: {', '.join(recipes)}.\n\nBlender axes: +Z up, the front faces "
            "-Y, meters. Build with blender_build, look with blender_view, fix what the facts report, export at the end.")


def recipe(name: str) -> str:
    p = HERE / "prompts" / "recipes" / f"{Path(name).stem}.md"
    return p.read_text(encoding="utf-8") if p.exists() else f"no recipe '{name}'"


TOOLS = [
    {"name": "kit_reference", "description": "The MeshGate modeling kit: rules, every mg.* function with its docs, and "
     "the artist recipes (pass recipe=creature|plant|rock|hardsurface|building|skeleton|library for one). Read it "
     "before building.", "inputSchema": {"type": "object", "properties": {"recipe": {"type": "string"}}}},
    {"name": "blender_build", "description": "Run kit code (a Python `def build(mg): …` using only mg, math, random, "
     "mathutils) in Blender's live scene and get back the measured facts: floating parts by code line, triangles per "
     "line, size, asymmetry. Set view=true to also get the rendered sheet.",
     "inputSchema": {"type": "object", "required": ["code"], "properties": {
         "code": {"type": "string"}, "tier": {"type": "string", "enum": ["pc", "mobile-high", "mobile-mid", "mobile-low"]},
         "look": {"type": "string", "enum": ["none", "faceted"]}, "params": {"type": "object"},
         "view": {"type": "boolean"}}}},
    {"name": "blender_view", "description": "Render the live scene from four sides (a flat thing from above) as one "
     "image; closeups = up to two extra views [{\"at\": [x,y,z], \"from\": [dx,dy,dz], \"size\": meters}].",
     "inputSchema": {"type": "object", "properties": {"closeups": {"type": "array"}}}},
    {"name": "blender_facts", "description": "Measured facts about the live scene (floating parts, triangles by line, "
     "size, asymmetry).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "blender_measure", "description": "The gap in meters between two parts, and whether they touch or "
     "overlap. A part is \"line N\" (what line N of the build code made) or an object name.",
     "inputSchema": {"type": "object", "required": ["a", "b"],
                                         "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}},
    {"name": "blender_scene", "description": "The objects in the live scene: names, sizes, triangles, materials.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "blender_export", "description": "Export the live scene as a checked GLB (+ FBX and engine variants) by "
     "the MeshGate contract.", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}},
]


def call(name: str, args: dict) -> list:
    if name == "kit_reference":
        return [{"type": "text", "text": recipe(args["recipe"]) if args.get("recipe") else kit_reference()}]
    how = ensure_blender()
    if name == "blender_build":
        rep = _send({"cmd": "run", "code": args.get("code", ""), "tier": args.get("tier", "pc"),
                     "look": args.get("look", "none"), "params": args.get("params") or {}})
        out = [{"type": "text", "text": json.dumps(rep, indent=1)[:20000]}]
        if args.get("view") and rep.get("ok"):
            out += _image(_send({"cmd": "render"}))
        return out
    if name == "blender_view":
        return _image(_send({"cmd": "render", "closeups": args.get("closeups") or []}))
    cmd = {"blender_facts": "facts", "blender_measure": "measure", "blender_scene": "info", "blender_export": "export"}.get(name)
    if not cmd:
        raise ValueError(f"unknown tool {name}")
    rep = _send({"cmd": cmd, **args})
    if name == "blender_scene":
        rep["link"] = how
    return [{"type": "text", "text": json.dumps(rep, indent=1)[:20000]}]


def _image(rep: dict) -> list:
    if not rep.get("ok") or not rep.get("image"):
        return [{"type": "text", "text": "the render failed: " + json.dumps(rep)[:2000]}]
    data = base64.b64encode(Path(rep["image"]).read_bytes()).decode()
    return [{"type": "image", "data": data, "mimeType": "image/png"}, {"type": "text", "text": rep["image"]}]


def handle(msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or PROTOCOL, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "meshgate", "version": "0.7"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            result = {"content": call(params.get("name", ""), params.get("arguments") or {}), "isError": False}
        except Exception as exc:  # noqa: BLE001 — a tool error is an answer, not a crash
            result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}
    elif method == "ping":
        result = {}
    elif mid is None:
        return None   # a notification (initialized, cancelled…)
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    if _headless["proc"]:
        _headless["proc"].terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
