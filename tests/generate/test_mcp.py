#!/usr/bin/env python3
"""The MCP server without Blender: the protocol, the tool list, the kit reference, and a clear error when no Blender
can be reached. The live tools themselves are checked against real Blenders by `meshgate.py check blender`.

    python3 tests/generate/test_mcp.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "kit_reference", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "kit_reference", "arguments": {"recipe": "creature"}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "blender_scene", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 6, "method": "no/such"},
    {"jsonrpc": "2.0", "id": 7, "method": "ping"},
]
env = {**os.environ, "MESHGATE_CONFIG_DIR": tempfile.mkdtemp(), "MESHGATE_BLENDER": str(Path(tempfile.mkdtemp()) / "no-blender")}
r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "mcp"], input="".join(json.dumps(m) + "\n" for m in msgs),
                   capture_output=True, text=True, env=env, timeout=60)
out = {m.get("id"): m for m in (json.loads(line) for line in r.stdout.splitlines() if line.strip())}

step("initialize answers with the protocol and tools capability",
     out.get(1, {}).get("result", {}).get("protocolVersion") == "2024-11-05"
     and "tools" in out[1]["result"].get("capabilities", {}), str(out.get(1))[:200])
step("a notification gets no answer", None not in out and len(out) == 7, sorted(map(str, out)))
tools = {t["name"]: t for t in out.get(2, {}).get("result", {}).get("tools", [])}
step("the tools are listed with input schemas",
     {"kit_reference", "blender_build", "blender_view", "blender_measure", "blender_export"} <= set(tools)
     and all(t.get("inputSchema", {}).get("type") == "object" for t in tools.values()), sorted(tools))
ref = (out.get(3, {}).get("result", {}).get("content") or [{}])[0].get("text", "")
step("kit_reference carries the rules and the kit API", all(k in ref for k in ("mg.place", "mg.blob", "Rules")), ref[:200])
rec = (out.get(4, {}).get("result", {}).get("content") or [{}])[0].get("text", "")
step("kit_reference gives one recipe", len(rec) > 200 and "no recipe" not in rec, rec[:120])
res5 = out.get(5, {}).get("result", {})
step("no Blender to reach: a tool error, not a crash", res5.get("isError") is True, str(res5)[:200])
step("an unknown method is a JSON-RPC error", out.get(6, {}).get("error", {}).get("code") == -32601, str(out.get(6)))
step("ping", out.get(7, {}).get("result") == {}, str(out.get(7)))

print("Result: " + ("all MCP checks passed." if not FAILS else f"{len(FAILS)} failed: {', '.join(FAILS)}"))
sys.exit(1 if FAILS else 0)
