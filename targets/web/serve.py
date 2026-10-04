#!/usr/bin/env python3
"""MeshGate — local static server for the viewer.
Serves the repository root (so /samples/*.glb are reachable) and opens the viewer.
    python3 targets/web/serve.py [--port 8770] [--no-browser] [--glb samples/name.glb]
"""
import argparse, functools, http.server, webbrowser
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8770)
ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
ap.add_argument("--glb", help="which GLB to open (path relative to the repository root)")
args = ap.parse_args()

root = Path(__file__).resolve().parents[2]  # repository root


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".hdr": "image/vnd.radiance",
                      ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # edit the viewer — see changes immediately
        super().end_headers()

    def log_message(self, fmt, *a):  # quieter: errors only
        if a and str(a[1]).startswith(("4", "5")):
            super().log_message(fmt, *a)


handler = functools.partial(Handler, directory=str(root))
url = f"http://localhost:{args.port}/targets/web/" + (f"?glb=/{args.glb.lstrip('/')}" if args.glb else "")
print(f"MeshGate viewer: {url}  (root: {root})")
if not args.no_browser:
    try:
        webbrowser.open(url)
    except Exception:
        pass
try:
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
except KeyboardInterrupt:
    pass
