#!/usr/bin/env python3
"""Cancel really stops the work: a Studio job whose build code never ends is cancelled through the API, and the Blender
it started must be gone. On Windows the tree is taken down by taskkill /T.

    python3 tests/studio/test_cancel.py [--blender PATH]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "studio"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender")
    args = ap.parse_args()
    if args.blender:
        os.environ["MESHGATE_BLENDER"] = args.blender
    import server
    lib = Path(tempfile.mkdtemp(prefix="meshgate-cancel-"))
    loop_ai = lib / "loop_ai.py"
    loop_ai.write_text("import sys; sys.stdin.read(); print('```python\\ndef build(mg):\\n    while True:\\n        pass\\n```')\n")
    studio = server.Studio(lib, "tok")
    port = [0]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(studio, port))
    port[0] = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def post(path, body):
        c = http.client.HTTPConnection("127.0.0.1", port[0], timeout=30)
        c.request("POST", path, body=json.dumps(body), headers={"Host": f"127.0.0.1:{port[0]}", "X-MeshGate-Token": "tok",
                                                                 "Content-Type": "application/json"})
        return json.loads(c.getresponse().read())

    def blenders():
        if os.name == "nt":
            folder = str(lib).replace("'", "''")
            query = ("Get-CimInstance Win32_Process -Filter \"Name='blender.exe'\" | "
                     "Where-Object { $_.CommandLine -and $_.CommandLine.Contains('run_generated.py') "
                     f"-and $_.CommandLine.Contains('{folder}') }} | Select-Object -ExpandProperty ProcessId")
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", query], capture_output=True,
                                 text=True, check=True).stdout
        else:
            out = subprocess.run(["pgrep", "-f", f"run_generated.py.*{lib}"], capture_output=True, text=True).stdout
        return [int(p) for p in out.split()]

    job = post("/api/gen", {"description": "never ends", "engine": "kit", "ai_cmd": f"{sys.executable} {loop_ai}",
                            "attempts": 1, "tiers": ["pc"], "targets": ["web"]})
    started = time.time()
    while not blenders() and time.time() - started < 60:
        time.sleep(0.5)
    running = blenders()
    ok = bool(running)
    print(f"  {'✓' if ok else '✗'} the job started Blender ({len(running)} process)")
    post(f"/api/jobs/{job['id']}/cancel", {})
    t0 = time.time()
    while blenders() and time.time() - t0 < 30:
        time.sleep(0.5)
    gone = not blenders()
    print(f"  {'✓' if gone else '✗'} cancel stopped Blender too ({time.time() - t0:.1f} s)")
    state = studio.jobs[job["id"]]
    t0 = time.time()
    while state.code is None and time.time() - t0 < 5:
        time.sleep(0.1)
    print(f"  {'✓' if state.cancelled and state.code is not None else '✗'} the job is marked cancelled and finished")
    ok &= gone and state.cancelled and state.code is not None
    for pid in blenders():   # never leave a stuck Blender behind, even when the check failed
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=True)
        else:
            os.kill(pid, 9)
    httpd.shutdown()
    print("Result: " + ("cancel stops the whole job." if ok else "cancel left work running."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
