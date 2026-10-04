"""A background Blender that serves the MeshGate live link (started by `meshgate.py mcp` when no Blender has it on).

    blender -b --factory-startup -P sources/generate/live_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
from meshgate_blender import live  # noqa: E402

live.serve_forever()
