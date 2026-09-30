#!/usr/bin/env python3
"""MeshGate Studio — the local app behind the desktop window (and usable in any browser).

    python3 meshgate.py studio [--port 0] [--library ~/Documents/MeshGate] [--no-browser]

Serves the Studio UI and a small JSON API on 127.0.0.1 only. Generation jobs run `meshgate.py gen --events` as child
processes; the UI polls their event lines. Every API call must carry the session token (header X-MeshGate-Token or
?t=), and the Host header must be the loopback address, so other web pages and other machines cannot drive the local
AI CLIs or Blender. Pure stdlib. The desktop shell (apps/studio/desktop, Tauri) starts this server and opens its URL.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UI = HERE / "ui"
VIEWER = ROOT / "targets" / "web"
sys.path.insert(0, str(ROOT / "sources" / "generate"))
sys.path.insert(0, str(ROOT))
import meshgate as cli  # noqa: E402  tool discovery (Blender, Unity, Godot, Unreal) and the add-on installer
import bridge  # noqa: E402  send a model into an engine project or Blender
import generate  # noqa: E402  (also puts the saved API keys into the environment)
import keys  # noqa: E402
import mesh  # noqa: E402
import components  # noqa: E402  optional local models (TripoSR, Hunyuan3D, Kimodo)

VERSION = "0.6.8"
THREE_VERSION = "0.169.0"   # same as targets/web/index.html
NAME_RE = re.compile(r"^[a-z0-9_\-.]{1,80}$")
UPLOAD_RE = re.compile(r"^[0-9a-f]{16}\.(png|jpg|jpeg|webp)$")
UPLOAD_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_UPLOAD = 20 * 2 ** 20
MODEL_RE = re.compile(r"^[0-9a-f]{16}\.(glb|fbx|obj|ply|stl)$")
MAX_MODEL = 150 * 2 ** 20
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/woff2", ".woff2")


class Job:
    def __init__(self, job_id: str, cmd: list[str], name: str):
        self.id, self.name, self.cmd = job_id, name, cmd
        self.lines: list[dict] = []
        self.code: int | None = None
        self.started = time.time()
        group = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                     errors="replace", cwd=str(ROOT), bufsize=1, **group)
        self.cancelled = False
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for raw in self.proc.stdout:
            raw = raw.rstrip("\n")
            if not raw:
                continue
            try:
                self.lines.append(json.loads(raw))
            except json.JSONDecodeError:
                self.lines.append({"message": raw, "stage": "log"})
        self.code = self.proc.wait()

    def cancel(self):
        """SIGTERM to the gen run: it stops its own Blender / TripoSR / AI CLI children (sources/generate/procs.py).
        Windows has no SIGTERM for console groups, so the whole tree goes at once."""
        if self.code is not None:
            return
        self.cancelled = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
            return
        import signal
        try:
            os.kill(self.proc.pid, signal.SIGTERM)
            self.proc.wait(15)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


class Studio:
    def __init__(self, library: Path, token: str):
        self.library = library
        self.token = token
        self.jobs: dict[str, Job] = {}
        self._status = None

    def status(self, refresh: bool = False) -> dict:
        if self._status is None or refresh:
            blender = generate.find_blender()
            profiles = json.loads(generate.PROFILES.read_text(encoding="utf-8"))
            self._status = {
                "version": VERSION, "platform": platform.system(), "library": str(self.library),
                "blender": blender, "ai": generate.available_ai(),
                "signed_in": {k: generate.signed_in(k) for k, v in generate.available_ai().items() if v},
                "ai_urls": {k: v["url"] for k, v in generate.ADAPTERS.items()},
                "login_hints": generate.LOGIN_HINTS, "styles": generate.STYLES,
                "providers": mesh.status(), "image_providers": mesh.images.available(),
                "keys": keys.status(), "keys_file": str(keys.path()), "setup": generate.SETUP,
                "tools": cli.tools_status(), "components": components.status(), "bridge": bridge.status(),
                "npm": bool(shutil.which("npm")),
                "fal_models": list(mesh.fal.MODELS),
                "tiers": [{"id": t, "label": profiles["profiles"][t]["label"], "max_tris": profiles["profiles"][t]["asset"]["max_tris"],
                           "devices": profiles["profiles"][t]["devices"]} for t in profiles["order"]],
            }
        return self._status

    def upload(self, req: dict) -> str:
        """A reference picture as a data URI → library/_inputs/<hash>.<ext>; returns the id to pass to /api/gen."""
        import base64
        import hashlib
        m = re.match(r"^data:(image/[a-z]+);base64,(.+)$", str(req.get("data", "")), re.S)
        if not m or m.group(1) not in UPLOAD_TYPES:
            raise ValueError("send a PNG, JPEG or WebP picture")
        raw = base64.b64decode(m.group(2), validate=False)
        if len(raw) > MAX_UPLOAD:
            raise ValueError("the picture is larger than 20 MB")
        sig = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"RIFF": "webp"}
        if not any(raw.startswith(k) for k in sig):
            raise ValueError("the file is not a PNG, JPEG or WebP picture")
        name = f"{hashlib.sha256(raw).hexdigest()[:16]}.{UPLOAD_TYPES[m.group(1)]}"
        folder = self.library / "_inputs"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(raw)
        return name

    def upload_model(self, req: dict) -> dict:
        """A model of your own (GLB, FBX, OBJ, PLY or STL) as base64 → library/_inputs/models/<hash>.<ext>;
        returns the id to pass to /api/gen as "mesh". The file is checked by its first bytes, not only its name."""
        import base64
        import hashlib
        ext = Path(str(req.get("filename", ""))).suffix.lower().lstrip(".")
        if ext not in {"glb", "fbx", "obj", "ply", "stl"}:
            raise ValueError("send a GLB, FBX, OBJ, PLY or STL model (a .gltf with separate files: export it as .glb)")
        data = str(req.get("data", ""))
        raw = base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data, validate=False)
        if not raw:
            raise ValueError("the file is empty")
        if len(raw) > MAX_MODEL:
            raise ValueError("the model is larger than 150 MB")
        head = raw[:1024]
        ok = {"glb": head.startswith(b"glTF"),
              "fbx": head.startswith(b"Kaydara FBX Binary") or b"FBXHeaderExtension" in head or head.lstrip().startswith(b"; FBX"),
              "ply": head.startswith(b"ply"),
              "stl": len(raw) >= 84,
              "obj": b"\0" not in head and bool(re.search(rb"^\s*(v|o|g|#|mtllib)\s", head, re.M))}[ext]
        if not ok:
            raise ValueError(f"the file does not look like a .{ext} model")
        name = f"{hashlib.sha256(raw).hexdigest()[:16]}.{ext}"
        folder = self.library / "_inputs" / "models"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(raw)
        return {"id": name, "name": generate.slug(Path(str(req.get("filename"))).stem, words=6)}

    def start(self, req: dict) -> Job:
        desc = str(req.get("description", "")).strip()
        image = str(req.get("image") or "")
        if image and not UPLOAD_RE.match(image):
            raise ValueError("unknown picture — upload it again")
        image_path = self.library / "_inputs" / image if image else None
        if image_path and not image_path.is_file():
            raise ValueError("the picture is gone — upload it again")
        model = str(req.get("mesh") or "")
        if model and not MODEL_RE.match(model):
            raise ValueError("unknown model file — upload it again")
        model_path = self.library / "_inputs" / "models" / model if model else None
        if model_path and not model_path.is_file():
            raise ValueError("the model file is gone — upload it again")
        if not desc and not image_path and not model_path:
            raise ValueError("describe the model or add a picture first")
        name = generate.slug(str(req.get("name") or desc or ("imported" if model_path else "from_picture")),
                             words=6 if req.get("name") else 3)
        tiers = [t for t in req.get("tiers", []) if t in generate.ORDER] or list(generate.ORDER)
        targets = [t for t in req.get("targets", []) if t in {"web", "unity", "godot", "unreal"}]
        cmd = [sys.executable, str(ROOT / "meshgate.py"), "gen", *([desc] if desc else []), "--name", name, "--events",
               "--style", str(req.get("style") or "stylized"), "--tiers", ",".join(tiers),
               "--targets", ",".join(targets) or "web", "--attempts", str(max(1, min(6, int(req.get("attempts") or 3)))),
               "--collision", req.get("collision") if req.get("collision") in {"none", "box", "convex"} else "none",
               "--out-dir", str(self.library / name)]
        if float(req.get("size") or 0) > 0:
            cmd += ["--size", str(float(req["size"]))]
        if model_path:   # your own model: cleaned, re-topologised per tier, baked and checked like a generated one
            cmd += ["--mesh", str(model_path)]
        elif image_path:
            cmd += ["--image", str(image_path)]
        if req.get("split") is True:
            cmd.append("--split")
        engine = req.get("engine") if req.get("engine") in {"auto", "kit", "mesh"} else "auto"
        cmd += ["--engine", engine]
        if req.get("provider") in mesh.PROVIDERS and req.get("provider") != "command":
            cmd += ["--provider", req["provider"]]
        if req.get("fal_model") in mesh.fal.MODELS:
            cmd += ["--fal-model", req["fal_model"]]
        caps = req.get("tris") or {}
        if isinstance(caps, dict):
            pairs = [f"{k}={int(v)}" for k, v in caps.items() if k in generate.ORDER and str(v).strip().isdigit() and int(v) >= 12]
            if pairs:
                cmd += ["--tris", ",".join(pairs)]
        if req.get("concept") in {"sheet", "single"} and not image_path and not model_path:
            cmd += ["--concept", req["concept"]]
        if req.get("texture") in generate.TEXTURES and req.get("texture") != "auto":
            cmd += ["--texture", req["texture"]]
        review = int(req.get("review") or 0)
        if 0 < review <= 4:
            cmd += ["--review", str(review)]
        if req.get("topology") in {"tri", "quad"}:
            cmd += ["--topology", req["topology"]]
        if req.get("pose") in {"a", "t"}:
            cmd += ["--pose", req["pose"]]
        if req.get("outline") in {"on", "off"}:
            cmd += ["--outline", req["outline"]]
        if req.get("pbr") is True:
            cmd.append("--pbr")
        if str(req.get("anim") or "").strip():
            cmd += ["--anim", str(req["anim"]).strip()[:1000]]
        if req.get("image_provider") in mesh.images.PROVIDERS:
            cmd += ["--image-provider", req["image_provider"]]
        if req.get("colors") in {"texture", "vertex"}:
            cmd += ["--colors", req["colors"]]
        if float(req.get("detail") or 1) != 1:
            cmd += ["--detail", str(max(0.2, min(3.0, float(req["detail"]))))]
        if float(req.get("turn") or 0):
            cmd += ["--turn", str(float(req["turn"]) % 360)]
        if req.get("ai_cmd"):
            cmd += ["--ai-cmd", str(req["ai_cmd"])]
        else:
            ai = req.get("ai") if req.get("ai") in generate.ADAPTERS else "claude"
            cmd += ["--ai", ai]
        if req.get("model"):
            cmd += ["--model", str(req["model"])]
        job = Job(secrets.token_hex(6), cmd, name)
        self.jobs[job.id] = job
        return job

    def refine(self, req: dict) -> Job:
        """Work on a model that is already in the library, the way an artist iterates: new slider values (mg.param),
        a change in words for the AI, or back to an earlier version. The current state is kept as a version first;
        the build reuses the model's own settings (style, tiers, textures, topology, pose, reference picture)."""
        name = str(req.get("name") or "")
        if not re.fullmatch(r"[a-z0-9_]{1,80}", name) or not (self.library / name / "gen.json").is_file():
            raise ValueError("pick a model from the library first")
        item = self.library / name
        g = json.loads((item / "gen.json").read_text(encoding="utf-8"))
        change = str(req.get("change") or "").strip()[:2000]
        params = {str(k): float(v) for k, v in (req.get("params") or {}).items() if isinstance(v, (int, float))}
        kit = (g.get("engine") or "kit") == "kit" and g.get("code") and (item / g["code"]).is_file()
        raw = Path(g["raw"]) if g.get("raw") else None
        raw = raw if raw is None or raw.is_absolute() else item / raw
        version = str(req.get("version") or "")
        if not kit and (change or params or version or not raw or not raw.is_file()):
            raise ValueError("only models built from kit code can be tuned — a mesh can be split and its parts edited")
        edits = parse_part_edits(req["parts"]) if "parts" in req else None
        look = parse_look(req["look"]) if "look" in req else None
        # new output settings from the toolbar under the model (remesh, texture): over what the model was built with
        st = req.get("settings") if isinstance(req.get("settings"), dict) else {}
        if st:
            g = dict(g)
            if st.get("topology") in {"tri", "quad"}:
                g["topology"] = st["topology"]
            if st.get("texture") in generate.TEXTURES:
                g["texture"] = st["texture"]
            if st.get("colors") in {"texture", "vertex"}:
                g["colors"] = st["colors"]
            if isinstance(st.get("pbr"), bool):
                g["pbr"] = st["pbr"]
            if "tris" in st:   # one target for the model: every tier gets it, or less when its own budget is lower
                n = st["tris"]
                if n is not None and (not isinstance(n, int) or not 100 <= n <= 2_000_000):
                    raise ValueError("the triangle target is out of range")
                budgets = {t["id"]: t["max_tris"] for t in self.status()["tiers"]}
                g["caps"] = {t: min(n, budgets.get(t, n)) for t in (g.get("tiers") or generate.ORDER)} if n else {}
        split = bool(g.get("split") or req.get("split") is True or edits)
        code_src = item / g["code"] if kit else None
        if version:
            if not re.fullmatch(r"\d{3}", version) or not (item / "versions" / version / g["code"]).is_file():
                raise ValueError("that version is gone")
            code_src = item / "versions" / version / g["code"]
            try:
                params = json.loads((item / "versions" / version / "gen.json").read_text(encoding="utf-8")).get("params") or {}
            except (OSError, ValueError):
                params = {}
        # keep the current state as a version (code, settings, preview) before anything changes
        versions = item / "versions"
        versions.mkdir(exist_ok=True)
        n = max([int(d.name) for d in versions.iterdir() if d.is_dir() and d.name.isdigit()] or [0]) + 1
        snap = versions / f"{n:03d}"
        snap.mkdir()
        for f in (g.get("code"), "gen.json", "edits.json", "look.json", g.get("report", {}).get("preview") or f"{name}.png", "views.png"):
            if f and (item / f).is_file():
                shutil.copyfile(item / f, snap / f)
        if version:   # the parts as they were edited then, and the look chosen then
            for f in ("edits.json", "look.json"):
                old = item / "versions" / version / f
                if old.is_file():
                    shutil.copyfile(old, item / f)
                else:
                    (item / f).unlink(missing_ok=True)
        if look is not None:   # the Appearance tab's sliders and colours, applied on every rebuild
            if look.get("morphs") or look.get("colours"):
                (item / "look.json").write_text(json.dumps(look, indent=1), encoding="utf-8")
            else:
                (item / "look.json").unlink(missing_ok=True)
        if edits is not None:
            if edits:
                (item / "edits.json").write_text(json.dumps(edits, indent=1), encoding="utf-8")
            else:
                (item / "edits.json").unlink(missing_ok=True)
        if kit:
            code_path = snap / f"source_{g['code']}"   # the run reads its code from here; the result replaces the current
            shutil.copyfile(code_src, code_path)
            source = ["--code", str(code_path)]
        else:   # a mesh (generated or your own): refined again from its source file
            source = ["--mesh", str(raw)]
            if float(g.get("detail") or 1) != 1:
                source += ["--detail", str(float(g["detail"]))]
            if float(g.get("turn") or 0):
                source += ["--turn", str(float(g["turn"]))]
        cmd = [sys.executable, str(ROOT / "meshgate.py"), "gen", *([g["description"]] if g.get("description") and kit else []),
               *source, "--name", name, "--events", "--style", str(g.get("style") or "stylized"),
               "--tiers", ",".join(g.get("tiers") or generate.ORDER), "--targets", str(req.get("targets") or "web,unity"),
               "--out-dir", str(item)]
        if float(g.get("size") or 0) > 0:
            cmd += ["--size", str(float(g["size"]))]
        if g.get("texture") in generate.TEXTURES and g.get("texture") != "auto":
            cmd += ["--texture", g["texture"]]
        if g.get("topology") in {"tri", "quad"}:
            cmd += ["--topology", g["topology"]]
        if g.get("pose") in {"a", "t"}:
            cmd += ["--pose", g["pose"]]
        if g.get("outline") in {"on", "off"}:
            cmd += ["--outline", g["outline"]]
        if split:
            cmd.append("--split")
        if g.get("pbr"):
            cmd.append("--pbr")
        if g.get("colors") in {"texture", "vertex"}:
            cmd += ["--colors", g["colors"]]
        caps = g.get("caps") or {}
        if caps:
            cmd += ["--tris", ",".join(f"{k}={int(v)}" for k, v in caps.items())]
        if kit and g.get("input_image") and (item / g["input_image"]).is_file():
            cmd += ["--image", str(item / g["input_image"])]
        if params:
            cmd += ["--params", json.dumps(params)]
        if change:
            cmd += ["--edit", change]
            if req.get("ai_cmd"):
                cmd += ["--ai-cmd", str(req["ai_cmd"])]
            else:
                cmd += ["--ai", req.get("ai") if req.get("ai") in generate.ADAPTERS else "claude"]
            if req.get("model"):
                cmd += ["--model", str(req["model"])]
        job = Job(secrets.token_hex(6), cmd, name)
        self.jobs[job.id] = job
        return job

    def versions(self, item: Path, code: str | None) -> list[dict]:
        out = []
        for d in sorted((item / "versions").glob("[0-9][0-9][0-9]"), reverse=True):
            try:
                g = json.loads((d / "gen.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({"id": d.name, "time": d.stat().st_mtime, "params": g.get("params") or {}, "edit": g.get("edit"),
                        "ok": g.get("ok")})
        return out

    def library_items(self) -> list[dict]:
        items = []
        if not self.library.is_dir():
            return items
        for gen_json in self.library.glob("*/gen.json"):
            try:
                g = json.loads(gen_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rep = g.get("report") or {}
            items.append({"name": g.get("name"), "description": g.get("description"), "ok": g.get("ok"),
                          "style": g.get("style"), "tiers": {t: {k: v.get(k) for k in ("file", "tris", "max_tris", "within_budget")}
                                                             for t, v in (rep.get("tiers") or {}).items()},
                          "canonical": rep.get("canonical"), "preview": rep.get("preview"), "files": rep.get("files", []),
                          "settings": {"topology": g.get("topology") or "tri", "texture": g.get("texture") or "auto",
                                       "pbr": bool(g.get("pbr")), "colors": g.get("colors") or "texture",
                                       "tris": max((g.get("caps") or {}).values(), default=None)},
                          "files": sorted(f.name for f in gen_json.parent.iterdir() if f.suffix in {".glb", ".fbx", ".blend"}),
                          "morphs": rep.get("morphs") or [], "look": _read_json(gen_json.parent / "look.json"),
                          "palette_grid": rep.get("palette_grid"),
                          "split": bool(g.get("split")), "part_edits": _read_json(gen_json.parent / "edits.json"),
                          "palette": [{"name": k, "index": v.get("index", 0), "hex": "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in (v.get("rgb") or [0.5] * 3)[:3])}
                                      for k, v in sorted((rep.get("palette") or {}).items(), key=lambda kv: kv[1].get("index", 0))],
                          "rebuildable": bool(g.get("code") or g.get("raw")),
                          "code": g.get("code"), "clips": (rep.get("tiers") or {}).get(rep.get("canonical") or "", {}).get("clips", []),
                          "attempts": len(g.get("attempts", [])), "seconds": g.get("seconds"),
                          "engine": g.get("engine") or "kit", "provider": g.get("provider"),
                          "input_image": g.get("input_image"), "reference_image": g.get("reference_image"),
                          "history": [{"ok": a.get("ok"), "problems": a.get("problems", [])[:6]} for a in g.get("attempts", [])],
                          "ai": g.get("ai"), "model": g.get("model"),
                          "params": [{**p_, "value": (g.get("params") or {}).get(p_["name"], p_.get("value"))}
                                     for p_ in rep.get("params") or []],
                          "edit": g.get("edit"), "versions": self.versions(gen_json.parent, g.get("code")),
                          "problems": rep.get("problems", []), "time": gen_json.stat().st_mtime})
        return sorted(items, key=lambda i: i["time"], reverse=True)

    def terminal(self, ai: str, action: str) -> str:
        """Open a terminal window running a fixed install or sign-in command (see generate.SETUP)."""
        cmd = (generate.SETUP.get(ai) or {}).get(action)
        if action not in {"install", "login"} or not cmd:
            raise ValueError("nothing to run for that")
        system = platform.system()
        if system == "Darwin":
            script = cmd.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(["osascript", "-e", 'tell application "Terminal" to activate',
                              "-e", f'tell application "Terminal" to do script "{script}"'])
        elif system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "MeshGate", "cmd", "/k", cmd])
        else:
            for term in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xterm", "-e"]):
                if shutil.which(term[0]):
                    subprocess.Popen(term + ["bash", "-lc", f"{cmd}; exec bash"])
                    break
            else:
                raise ValueError(f"no terminal found — run this yourself: {cmd}")
        self._status = None
        return cmd

    def reveal_plugin(self, tool: str) -> str:
        """Open the folder of MeshGate's plugin for Blender, Unity, Godot or Unreal (to copy into a project)."""
        rel = cli.PLUGINS.get(tool)
        folder = ROOT / rel if rel else None
        if not folder or not folder.exists():
            raise ValueError("no plugin for that")
        target = folder.parent if tool in ("unity", "godot", "unreal") else folder
        opener = {"Darwin": ["open"], "Windows": ["explorer"]}.get(platform.system(), ["xdg-open"])
        subprocess.Popen(opener + [str(target)])
        return str(folder)

    def send(self, req: dict) -> dict:
        """The model into a Unity / Godot / Unreal project (its folder remembered), or opened in Blender."""
        name = str(req.get("name") or "")
        if not re.fullmatch(r"[a-z0-9_]{1,80}", name) or not (self.library / name / "gen.json").is_file():
            raise ValueError("pick a model from the library first")
        project = str(req.get("project") or "").strip() or None
        try:
            got = bridge.send(self.library / name, str(req.get("tool") or ""), project, blender=cli.find_blender())
        except OSError as exc:
            raise ValueError(f"could not copy the files: {exc}") from exc
        self._status = None   # the remembered projects changed
        return got

    def reveal(self, name: str) -> None:
        path = self.library / name
        if not NAME_RE.match(name) or not path.is_dir():
            raise ValueError("no such asset")
        opener = {"Darwin": ["open"], "Windows": ["explorer"]}.get(platform.system(), ["xdg-open"])
        subprocess.Popen(opener + [str(path)])


def make_handler(studio: Studio, port_ref: list):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MeshGateStudio/" + VERSION

        def log_message(self, fmt, *args):   # quiet unless MESHGATE_STUDIO_LOG names a file (debugging the desktop shell)
            target = os.environ.get("MESHGATE_STUDIO_LOG")
            if target:
                with open(target, "a", encoding="utf-8") as f:
                    f.write(f"{self.address_string()} {fmt % args}\n".replace(studio.token, "<token>"))

        # ---------------------------------------------------------------- helpers
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            return host in {f"127.0.0.1:{port_ref[0]}", f"localhost:{port_ref[0]}"}

        def _token_ok(self, query: dict) -> bool:
            given = self.headers.get("X-MeshGate-Token") or (query.get("t") or [""])[0]
            return secrets.compare_digest(given, studio.token)

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _file(self, path: Path):
            if not path.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), ctype)

        def _body(self, limit: int = MAX_UPLOAD) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit * 4 // 3 + 4096:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n) or b"{}")

        @staticmethod
        def _inside(base: Path, rel: str) -> Path | None:
            p = (base / rel).resolve()
            return p if p.is_relative_to(base.resolve()) else None

        # ---------------------------------------------------------------- routes
        def do_GET(self):
            if not self._host_ok():
                return self._json({"error": "bad host"}, 403)
            url = urlparse(self.path)
            q = parse_qs(url.query)
            path = url.path
            if path in ("/", "/index.html"):
                return self._file(UI / "index.html")
            if path.startswith("/ui/"):
                p = self._inside(UI, path[4:])
                return self._file(p) if p else self._json({"error": "not found"}, 404)
            if path.startswith("/three/"):   # vendored three.js (scripts/vendor_three.py), else the CDN
                rel = path[len("/three/"):]
                local = self._inside(UI / "vendor" / "three", rel)
                if local and local.is_file():
                    return self._file(local)
                if re.match(r"^[A-Za-z0-9_\-./]+\.js$", rel) and ".." not in rel:
                    self.send_response(302)
                    self.send_header("Location", f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/{rel}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                return self._json({"error": "not found"}, 404)
            if path.startswith("/viewer/"):
                name = path[len("/viewer/"):]
                return self._file(VIEWER / name) if name in {"meshgate-viewer.js"} else self._json({"error": "not found"}, 404)
            if not self._token_ok(q):
                return self._json({"error": "missing or wrong token"}, 401)
            if path == "/api/status":
                return self._json(studio.status(refresh="refresh" in q))
            if path == "/api/library":
                return self._json(studio.library_items())
            m = re.match(r"^/api/jobs/([0-9a-f]+)$", path)
            if m:
                job = studio.jobs.get(m.group(1))
                if not job:
                    return self._json({"error": "no such job"}, 404)
                since = int((q.get("since") or ["0"])[0])
                return self._json({"id": job.id, "name": job.name, "lines": job.lines[since:], "next": len(job.lines),
                                   "done": job.code is not None, "code": job.code, "cancelled": job.cancelled})
            m = re.match(r"^/files/([^/]+)/([^/]+)$", path)
            if m and NAME_RE.match(m.group(1)) and NAME_RE.match(m.group(2)):
                p = self._inside(studio.library, f"{m.group(1)}/{m.group(2)}")
                return self._file(p) if p else self._json({"error": "not found"}, 404)
            return self._json({"error": "not found"}, 404)

        def do_POST(self):
            if not self._host_ok():
                return self._json({"error": "bad host"}, 403)
            url = urlparse(self.path)
            if not self._token_ok(parse_qs(url.query)):
                return self._json({"error": "missing or wrong token"}, 401)
            if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                return self._json({"error": "JSON only"}, 415)
            try:
                body = self._body(MAX_MODEL if url.path == "/api/upload-model" else MAX_UPLOAD)
                if url.path == "/api/upload-model":
                    return self._json(studio.upload_model(body))
                if url.path == "/api/upload":
                    return self._json({"id": studio.upload(body)})
                if url.path == "/api/setup":
                    cid = str(body.get("provider", ""))
                    if cid not in components.COMPONENTS:
                        raise ValueError("no such component")
                    job = Job(secrets.token_hex(6), [sys.executable, str(ROOT / "meshgate.py"), "gen", "--setup", cid,
                                                     "--events"], f"setup-{cid}")
                    studio.jobs[job.id] = job
                    studio._status = None   # re-read readiness after the install
                    return self._json({"id": job.id, "name": job.name})
                if url.path == "/api/gen":
                    job = studio.start(body)
                    return self._json({"id": job.id, "name": job.name})
                if url.path == "/api/refine":
                    job = studio.refine(body)
                    return self._json({"id": job.id, "name": job.name})
                m = re.match(r"^/api/jobs/([0-9a-f]+)/cancel$", url.path)
                if m and m.group(1) in studio.jobs:
                    studio.jobs[m.group(1)].cancel()
                    return self._json({"ok": True})
                if url.path == "/api/shutdown":   # the desktop shell calls this before it quits
                    for job in list(studio.jobs.values()):
                        job.cancel()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return self._json({"ok": True})
                if url.path == "/api/install-addon":
                    job = Job(secrets.token_hex(6), [sys.executable, str(ROOT / "meshgate.py"), "install-blender"], "install-addon")
                    studio.jobs[job.id] = job
                    studio._status = None
                    return self._json({"id": job.id, "name": job.name})
                if url.path == "/api/reveal-plugin":
                    return self._json({"ok": True, "folder": studio.reveal_plugin(str(body.get("tool", "")))})
                if url.path == "/api/keys":
                    keys.save(str(body.get("name", "")), str(body.get("value", "")))
                    studio._status = None
                    return self._json({"ok": True, "keys": keys.status()})
                if url.path == "/api/terminal":
                    return self._json({"ok": True, "command": studio.terminal(str(body.get("ai", "")), str(body.get("action", "")))})
                if url.path == "/api/send":
                    return self._json({"ok": True, **studio.send(body)})
                if url.path == "/api/reveal":
                    studio.reveal(str(body.get("name", "")))
                    return self._json({"ok": True})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json({"error": str(exc)}, 400)
            return self._json({"error": "not found"}, 404)

    return Handler


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _part_change(nm: str, e: dict, copies: bool = True) -> dict:
    o = {}
    if e.get("delete") is True:
        o["delete"] = True
    mv = e.get("move")
    if mv is not None:
        if not (isinstance(mv, list) and len(mv) == 3 and all(isinstance(v, (int, float)) and abs(v) <= 1000 for v in mv)):
            raise ValueError(f"{nm}: move is [x, y, z] in metres")
        if any(abs(v) > 1e-5 for v in mv):
            o["move"] = [round(float(v), 5) for v in mv]
    for k, lo, hi, idle in (("turn", -36000, 36000, 0.0), ("scale", 0.05, 20.0, 1.0)):
        v = e.get(k)
        if v is not None:
            if not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise ValueError(f"{nm}: {k} is out of range")
            if abs(v - idle) > 1e-4:
                o[k] = round(float(v), 4)
    c = e.get("colour")
    if c:
        if not re.fullmatch(r"[a-z0-9_]{1,40}|#[0-9a-fA-F]{6}", str(c)):
            raise ValueError(f"{nm}: unknown colour")
        o["colour"] = str(c).lower()
    if copies and e.get("copies"):
        cs = e["copies"]
        if not isinstance(cs, list) or len(cs) > 50 or not all(isinstance(x, dict) for x in cs):
            raise ValueError(f"{nm}: copies is a list of up to 50 placements")
        o["copies"] = [{k: v for k, v in _part_change(nm, x, copies=False).items() if k != "delete"} for x in cs]
    return o


def parse_look(raw) -> dict:
    """The look chosen in the Appearance tab, checked: {"morphs": {name: -1…1}, "colours": {palette name: "#rrggbb"}}."""
    if not isinstance(raw, dict):
        raise ValueError("the look is an object with morphs and colours")
    morphs, colours = raw.get("morphs") or {}, raw.get("colours") or {}
    if not isinstance(morphs, dict) or not isinstance(colours, dict) or len(morphs) > 64 or len(colours) > 64:
        raise ValueError("the look has morphs and colours by name")
    out = {"morphs": {}, "colours": {}}
    for k, v in morphs.items():
        if not re.fullmatch(r"[a-z0-9_]{1,40}", str(k)) or not isinstance(v, (int, float)) or not -1 <= v <= 1:
            raise ValueError(f"morph {str(k)[:40]!r} is a value from -1 to 1")
        if abs(v) > 1e-3:
            out["morphs"][str(k)] = round(float(v), 3)
    for k, v in colours.items():
        if not re.fullmatch(r"[a-z0-9_]{1,40}", str(k)) or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
            raise ValueError(f"colour {str(k)[:40]!r} is #rrggbb")
        out["colours"][str(k)] = str(v).lower()
    return {k: v for k, v in out.items() if v}


def parse_part_edits(raw) -> dict:
    """Hand changes to a split model's parts from the part editor, checked: {part name: {"move": [x, y, z] m (Blender
    axes, Z up), "turn": degrees round the vertical, "scale": factor, "delete": bool, "colour": palette name or
    "#rrggbb", "copies": [{"move", "turn", "scale", "colour"}, …]}}."""
    if not isinstance(raw, dict) or len(raw) > 2000:
        raise ValueError("part edits must be an object of part names")
    out = {}
    for nm, e in raw.items():
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,80}", str(nm)) or not isinstance(e, dict):
            raise ValueError(f"bad part name {str(nm)[:40]!r}")
        o = _part_change(str(nm), e)
        if o:
            out[str(nm)] = o
    return out


def default_library() -> Path:
    env = os.environ.get("MESHGATE_LIBRARY")
    if env:
        return Path(env).expanduser()
    # not ~/Documents/MeshGate: on case-insensitive disks that is the same folder as a clone named "meshgate"
    return ROOT / "out" / "gen" if (ROOT / ".git").exists() else Path.home() / "Documents" / "MeshGate Assets"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows consoles and pipes default to cp1252; MeshGate prints ✓ and —
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="meshgate studio", description="MeshGate Studio: text → game-ready asset, local UI")
    ap.add_argument("--port", type=int, default=0, help="0 = any free port")
    ap.add_argument("--library", help="folder for generated assets (default: out/gen in the repo, else ~/Documents/MeshGate Assets)")
    ap.add_argument("--token", help="session token (default: MESHGATE_STUDIO_TOKEN, else random); the desktop shell sets the variable")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser (the desktop shell opens its window)")
    args = ap.parse_args(argv)
    library = Path(args.library).expanduser() if args.library else default_library()
    library.mkdir(parents=True, exist_ok=True)
    token = args.token or os.environ.get("MESHGATE_STUDIO_TOKEN") or secrets.token_urlsafe(24)
    studio = Studio(library, token)
    port_ref = [args.port]
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(studio, port_ref))
    port_ref[0] = httpd.server_address[1]
    url = f"http://127.0.0.1:{port_ref[0]}/?t={token}"
    print(f"MESHGATE_STUDIO {url}", flush=True)
    st = studio.status()
    found = ", ".join(k for k, v in st["ai"].items() if v) or "none — see meshgate.py gen --list-ai"
    print(f"MeshGate Studio {VERSION}: {url.replace(token, '<token>') if not args.token else url}\n  library: {library}\n"
          f"  blender: {st['blender'] or 'not found (MESHGATE_BLENDER)'}\n  AI CLIs: {found}\n  Ctrl+C to stop", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    import signal

    def stop(_signum, _frame):   # SIGTERM from a parent: cancel the jobs (and their Blender) before leaving
        for job in list(studio.jobs.values()):
            job.cancel()
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in studio.jobs.values():
            job.cancel()
    return 0


if __name__ == "__main__":
    sys.exit(main())
