#!/usr/bin/env python3
"""Cloud mesh providers against a local stand-in server: request shapes, auth headers, polling, downloads.

    python3 tests/generate/test_providers.py

The stand-in follows each provider's documented API (Meshy image/text-to-3d, Tripo task + upload, fal queue,
OpenAI images) and serves a real GLB from samples/. It checks what MeshGate sends, not the services themselves.
"""

import base64
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sources" / "generate"))
GLB = (ROOT / "samples" / "meshgate_barrel.glb").read_bytes()
PNG = (ROOT / "docs" / "img" / "studio.png")
SEEN = []   # (method, path, headers, body)
POLLS = {}
FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


class Stand(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        return json.loads(raw) if ctype.startswith("application/json") else raw

    def _pending(self, key, done):
        POLLS[key] = POLLS.get(key, 0) + 1
        return POLLS[key] >= 2 and done   # first poll: still running

    def do_POST(self):
        body = self._body()
        SEEN.append(("POST", self.path, dict(self.headers), body))
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        if self.path.startswith("/meshy/openapi/"):
            return self._json({"result": f"task-{len(SEEN)}"})
        if self.path == "/tripo/upload":
            return self._json({"code": 0, "data": {"image_token": "tok-123"}})
        if self.path == "/tripo/task":
            return self._json({"code": 0, "data": {"task_id": "tr-1"}})
        if self.path.startswith("/fal/"):
            model = self.path[len("/fal/"):]
            return self._json({"request_id": "r1", "status_url": f"{base}/fal/{model}/requests/r1/status",
                               "response_url": f"{base}/fal/{model}/requests/r1"})
        if self.path == "/openai/images/generations":
            return self._json({"data": [{"b64_json": base64.b64encode(PNG.read_bytes()).decode()}]})
        self._json({"error": "unknown"}, 404)

    def do_GET(self):
        SEEN.append(("GET", self.path, dict(self.headers), None))
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        if self.path == "/files/model.glb":
            self.send_response(200)
            self.send_header("Content-Length", str(len(GLB)))
            self.end_headers()
            self.wfile.write(GLB)
            return
        if self.path == "/files/ref.png":
            b = PNG.read_bytes()
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        if self.path.startswith("/meshy/openapi/"):
            tid = self.path.rsplit("/", 1)[1]
            ok = self._pending(tid, True)
            return self._json({"id": tid, "status": "SUCCEEDED" if ok else "IN_PROGRESS", "progress": 100 if ok else 40,
                               "model_urls": {"glb": f"{base}/files/model.glb"} if ok else {}})
        if self.path == "/tripo/task/tr-1":
            ok = self._pending("tr-1", True)
            return self._json({"code": 0, "data": {"status": "success" if ok else "running",
                                                   "output": {"pbr_model": f"{base}/files/model.glb"} if ok else {}}})
        if self.path.startswith("/fal/") and self.path.endswith("/status"):
            ok = self._pending(self.path, True)
            return self._json({"status": "COMPLETED" if ok else "IN_PROGRESS"})
        if self.path.startswith("/fal/fal-ai/flux"):
            return self._json({"images": [{"url": f"{base}/files/ref.png"}]})
        if self.path.startswith("/fal/"):
            return self._json({"model_mesh": {"url": f"{base}/files/model.glb"}})
        self._json({"error": "unknown"}, 404)


httpd = ThreadingHTTPServer(("127.0.0.1", 0), Stand)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"
os.environ.update({"MESHY_API_KEY": "mk", "TRIPO_API_KEY": "tk", "FAL_KEY": "fk", "OPENAI_API_KEY": "ok",
                   "MESHGATE_MESHY_URL": f"{base}/meshy", "MESHGATE_TRIPO_URL": f"{base}/tripo",
                   "MESHGATE_FAL_URL": f"{base}/fal", "MESHGATE_OPENAI_URL": f"{base}/openai", "MESHGATE_POLL": "0.05"})
import mesh  # noqa: E402

quiet = lambda *_: None   # noqa: E731
tmp = Path(tempfile.mkdtemp(prefix="meshgate-providers-"))
image = str(PNG)


def posts(prefix):
    return [(p, h, b) for m, p, h, b in SEEN if m == "POST" and p.startswith(prefix)]


# Meshy: image → 3D with a data URI, then text → 3D preview + refine
SEEN.clear()
got = mesh.make("meshy", prompt=None, image=image, out_dir=tmp / "meshy_img", log=quiet)
p, h, b = posts("/meshy/openapi/v1/image-to-3d")[0]
step("meshy image: Bearer key, data URI, PBR texture", h.get("Authorization") == "Bearer mk"
     and b["image_url"].startswith("data:image/png;base64,") and b["should_texture"] and b["enable_pbr"])
step("meshy image: GLB downloaded after polling", Path(got["raw"]).read_bytes() == GLB)
SEEN.clear()
got = mesh.make("meshy", prompt="a red fire hydrant", image=None, out_dir=tmp / "meshy_txt", log=quiet)
v2 = posts("/meshy/openapi/v2/text-to-3d")
step("meshy text: preview then refine of that preview", len(v2) == 2 and v2[0][2]["mode"] == "preview"
     and v2[1][2]["mode"] == "refine" and v2[1][2]["preview_task_id"].startswith("task-"))
step("meshy text: GLB downloaded", Path(got["raw"]).read_bytes() == GLB)

# Tripo: upload then image_to_model with the token; text_to_model
SEEN.clear()
got = mesh.make("tripo", prompt=None, image=image, out_dir=tmp / "tripo", log=quiet)
up = posts("/tripo/upload")[0]
task = posts("/tripo/task")[0]
step("tripo image: multipart upload with the key", up[1].get("Authorization") == "Bearer tk"
     and up[1].get("Content-Type", "").startswith("multipart/form-data") and b"filename=\"studio.png\"" in up[2])
step("tripo image: task uses the uploaded token", task[2]["type"] == "image_to_model"
     and task[2]["file"] == {"type": "png", "file_token": "tok-123"})
step("tripo: pbr_model downloaded after polling", Path(got["raw"]).read_bytes() == GLB)
SEEN.clear()
mesh.make("tripo", prompt="a wooden cart", image=None, out_dir=tmp / "tripo_txt", log=quiet)
step("tripo text: text_to_model", posts("/tripo/task")[0][2] == {"type": "text_to_model", "prompt": "a wooden cart",
                                                                "texture": True, "pbr": True})

# fal: TRELLIS from an image; text → FLUX image → TRELLIS; Hunyuan3D field name
SEEN.clear()
got = mesh.make("fal", prompt=None, image=image, out_dir=tmp / "fal", log=quiet)
sub = posts("/fal/fal-ai/trellis")[0]
step("fal image: Key auth, image_url data URI, queue polling", sub[1].get("Authorization") == "Key fk"
     and sub[2]["image_url"].startswith("data:image/png") and Path(got["raw"]).read_bytes() == GLB)
SEEN.clear()
got = mesh.make("fal", prompt="a cactus in a pot", image=None, out_dir=tmp / "fal_txt", log=quiet)
flux = posts("/fal/fal-ai/flux/schnell")
step("fal text: FLUX draws a reference image first", flux and "ONE object" in flux[0][2]["prompt"]
     and (tmp / "fal_txt" / "reference.png").exists() and posts("/fal/fal-ai/trellis"))
SEEN.clear()
mesh.make("fal", prompt=None, image=image, out_dir=tmp / "fal_h", log=quiet, fal_model="fal-ai/hunyuan3d/v2")
step("fal hunyuan3d: input_image_url field", "input_image_url" in posts("/fal/fal-ai/hunyuan3d/v2")[0][2])

# image-only local provider without a picture: OpenAI draws the reference first (TripoSR itself is replaced by a stub)
SEEN.clear()
drawn = mesh.images.text_to_image("a street lamp", tmp / "ref.png", "openai", quiet)
gen = posts("/openai/images/generations")[0]
step("openai text → image: gpt-image-1, Bearer key, PNG written", gen[1].get("Authorization") == "Bearer ok"
     and gen[2]["model"] == "gpt-image-1" and drawn.read_bytes()[:4] == b"\x89PNG")

# errors are readable
os.environ.pop("MESHY_API_KEY")
try:
    mesh.make("meshy", prompt="x", image=None, out_dir=tmp / "nokey", log=quiet)
    step("missing key → clear error", False)
except mesh.ProviderError as exc:
    step("missing key → clear error", "MESHY_API_KEY" in str(exc))

# your own command
cmd_out = tmp / "cmd"
script = tmp / "fake_gen.py"
script.write_text("import sys, shutil; shutil.copyfile(sys.argv[1], sys.argv[2])")
got = mesh.make("command", prompt=None, image=str(ROOT / "samples" / "meshgate_barrel.glb"), out_dir=cmd_out, log=quiet,
                mesh_cmd=f"{sys.executable} {script} {{image}} {{out}}")
step("command provider: placeholders filled, output picked up", Path(got["raw"]).read_bytes() == GLB)

httpd.shutdown()
print("Result: " + ("provider checks passed." if not FAILS else f"{len(FAILS)} failed."))
sys.exit(1 if FAILS else 0)
