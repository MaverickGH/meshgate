#!/usr/bin/env python3
"""MeshGate Studio server without a browser: routes, token, Host check, path safety. Pure stdlib.

    python3 tests/studio/test_server.py
"""

import http.client
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "studio"))
import os  # noqa: E402
os.environ["MESHGATE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="meshgate-keys-test-")   # never touch the real ~/.meshgate
os.environ.pop("MESHY_API_KEY", None)
import server  # noqa: E402

FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


lib = Path(tempfile.mkdtemp(prefix="meshgate-studio-test-"))
(lib / "crate").mkdir()
(lib / "crate" / "crate.glb").write_bytes(b"glTF-test")
(lib / "crate" / "gen.json").write_text(json.dumps({"name": "crate", "ok": True, "description": "a crate", "attempts": [{}],
                                                    "report": {"canonical": "pc", "tiers": {"pc": {"file": "crate.glb", "tris": 12}},
                                                               "files": ["crate.glb"]}}))
(lib / "secret.txt").write_text("outside")
studio = server.Studio(lib, "tok")
port = [0]
httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(studio, port))
port[0] = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()


def req(method, path, headers=None, body=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port[0], timeout=10)
    h = {"Host": host or f"127.0.0.1:{port[0]}", **(headers or {})}
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    return r.status, r.read()


TOK = {"X-MeshGate-Token": "tok"}
s, b = req("GET", "/")
step("UI page is served", s == 200 and b"MeshGate Studio" in b)
step("viewer module is served", req("GET", "/viewer/meshgate-viewer.js")[0] == 200)
step("only the viewer file is exposed from targets/web", req("GET", "/viewer/serve.py")[0] == 404)
s3, _ = req("GET", "/three/build/three.module.js")
step("three.js is served locally or redirected to the CDN", s3 in (200, 302))
step("three route refuses odd paths", req("GET", "/three/../server.py")[0] in (400, 404))
step("API without token → 401", req("GET", "/api/status")[0] == 401)
step("API with a wrong token → 401", req("GET", "/api/status", {"X-MeshGate-Token": "nope"})[0] == 401)
step("foreign Host header → 403 (DNS rebinding)", req("GET", "/api/status", TOK, host="evil.example:80")[0] == 403)
s, b = req("GET", "/api/status", TOK)
st = json.loads(b) if s == 200 else {}
step("status lists tiers, AI CLIs and styles", s == 200 and len(st.get("tiers", [])) == 4 and "claude" in st.get("ai", {})
     and "stylized" in st.get("styles", {}))
s, b = req("GET", "/api/library?t=tok")
items = json.loads(b) if s == 200 else []
step("library reads gen.json (token in query)", s == 200 and items and items[0]["name"] == "crate" and items[0]["tiers"]["pc"]["tris"] == 12)
step("generated files are served", req("GET", "/files/crate/crate.glb?t=tok")[1] == b"glTF-test")
step("path traversal is refused", req("GET", "/files/crate/..%2Fsecret.txt?t=tok")[0] == 404
     and req("GET", "/files/../secret.txt?t=tok")[0] == 404)
step("POST needs JSON", req("POST", "/api/gen", TOK, body="description=x")[0] == 415)
s, b = req("POST", "/api/gen", {**TOK, "Content-Type": "application/json"}, body=json.dumps({"description": ""}))
step("empty description → 400", s == 400)
step("reveal refuses unknown names", req("POST", "/api/reveal", {**TOK, "Content-Type": "application/json"},
                                         body=json.dumps({"name": "../etc"}))[0] == 400)
step("unknown job → 404", req("GET", "/api/jobs/abcdef", TOK)[0] == 404)

# reference pictures
import base64  # noqa: E402
png = (ROOT / "sources" / "generate" / "examples" / "hydrant_picture.png").read_bytes()
J = {**TOK, "Content-Type": "application/json"}
s, b = req("POST", "/api/upload", J, body=json.dumps({"data": "data:image/png;base64," + base64.b64encode(png).decode()}))
up = json.loads(b) if s == 200 else {}
step("picture upload stores it under _inputs with a content hash", s == 200 and (lib / "_inputs" / up.get("id", "x")).read_bytes() == png)
s, _ = req("POST", "/api/upload", J, body=json.dumps({"data": "data:image/png;base64," + base64.b64encode(b"<svg/>").decode()}))
step("upload refuses a non-picture with an image type", s == 400)
s, _ = req("POST", "/api/upload", J, body=json.dumps({"data": "data:text/html;base64,PGgxPg=="}))
step("upload refuses other media types", s == 400)
s, b = req("POST", "/api/gen", J, body=json.dumps({"description": "", "image": "../../etc/passwd"}))
step("gen refuses a picture id that is not an upload", s == 400)
s, b = req("POST", "/api/gen", J, body=json.dumps({"description": "", "image": "0123456789abcdef.png"}))
step("gen refuses a picture that was never uploaded", s == 400)
s, _ = req("POST", "/api/refine", J, body=json.dumps({"name": "../../etc"}))
step("refine refuses a name outside the library", s == 400)
s, _ = req("POST", "/api/refine", J, body=json.dumps({"name": "not_made_yet"}))
step("refine refuses a model that is not in the library", s == 400)
st = json.loads(req("GET", "/api/status", TOK)[1])
step("status lists mesh generators with readiness", {"triposr", "meshy", "tripo", "fal"} <= set(st.get("providers", {}))
     and all("ready" in v for v in st["providers"].values()))
# API keys: saved to the config folder, owner-only, never echoed back in full; unknown names refused
import stat  # noqa: E402
secret = "msy_test_1234567890abcdef"
s, b = req("POST", "/api/keys", J, body=json.dumps({"name": "MESHY_API_KEY", "value": secret}))
kf = Path(os.environ["MESHGATE_CONFIG_DIR"]) / "keys.json"
step("a saved key lands in keys.json, readable by the owner only", s == 200 and json.loads(kf.read_text())["MESHY_API_KEY"] == secret
     and (os.name == "nt" or stat.S_IMODE(kf.stat().st_mode) == 0o600))
st = json.loads(req("GET", "/api/status?refresh=1", TOK)[1])
step("status shows the key as set with its last four characters only", st["keys"]["MESHY_API_KEY"]["set"]
     and st["keys"]["MESHY_API_KEY"]["hint"] == "…cdef" and secret not in json.dumps(st))
step("a saved key makes its generator ready", st["providers"]["meshy"]["ready"])
step("unknown key names are refused", req("POST", "/api/keys", J, body=json.dumps({"name": "PATH", "value": "x"}))[0] == 400)
req("POST", "/api/keys", J, body=json.dumps({"name": "MESHY_API_KEY", "value": ""}))
step("an empty value removes the key", "MESHY_API_KEY" not in json.loads(kf.read_text()))
step("the terminal helper runs only listed commands", req("POST", "/api/terminal", J, body=json.dumps({"ai": "claude; rm -rf /", "action": "login"}))[0] == 400
     and req("POST", "/api/terminal", J, body=json.dumps({"ai": "claude", "action": "exec"}))[0] == 400)
st = json.loads(req("GET", "/api/status", TOK)[1])
tools = st.get("tools", {})
step("status shows Blender and every engine with its plugin folder and how to connect",
     {"python", "blender", "unity", "godot", "unreal"} <= set(tools)
     and all(tools[t].get("plugin") and tools[t].get("how") for t in ("blender", "unity", "godot", "unreal"))
     and "addon" in tools["blender"])
step("plugin folders open only for known tools", req("POST", "/api/reveal-plugin", J, body=json.dumps({"tool": "../etc"}))[0] == 400
     and req("POST", "/api/reveal-plugin", J, body=json.dumps({"tool": "python"}))[0] == 400)
step("status lists the optional components with licence, size and install command",
     {"triposr", "hunyuan3d", "kimodo"} <= set(st.get("components", {}))
     and all(c.get("license") and c.get("size") and c.get("setup") for c in st["components"].values()))
step("setup runs only listed components", req("POST", "/api/setup", J, body=json.dumps({"provider": "rm -rf"}))[0] == 400)
httpd.shutdown()
print("Result: " + ("studio server checks passed." if not FAILS else f"{len(FAILS)} failed."))
sys.exit(1 if FAILS else 0)
