"""Send a finished model into a game-engine project or Blender, the way DCC bridges do: one click, and the files land
where the engine picks them up (and are replaced in place the next time, so the engine re-imports them).

    python3 meshgate.py send out/gen/crate_pile --to unity --project ~/Games/MyGame
    python3 meshgate.py send out/gen/crate_pile --to blender

Where the files go:
    unity   <project>/Assets/MeshGate/<name>/   the GLB of every tier (glTFast) and the FBX (native import)
    godot   <project>/meshgate/<name>/          the GLB of every tier (Godot imports glTF itself)
    unreal  <project>/Content/MeshGate/<name>/  the FBX, else the GLB (Interchange; the editor offers to import new files)
    blender opens the model's .blend (else a new scene with its GLB) in your Blender

The project folders you use are remembered in ~/.meshgate/bridge.json (MESHGATE_CONFIG_DIR overrides the folder).
Pure stdlib.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

TOOLS = ("unity", "godot", "unreal", "blender")
LABELS = {"unity": "Unity", "godot": "Godot", "unreal": "Unreal", "blender": "Blender"}


def config_path() -> Path:
    return Path(os.environ.get("MESHGATE_CONFIG_DIR") or Path.home() / ".meshgate") / "bridge.json"


def load() -> dict:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items() if k in TOOLS and v}
    except (OSError, ValueError):
        return {}


def remember(tool: str, project: str) -> None:
    data = load()
    data[tool] = project
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(data, indent=1), encoding="utf-8")


def project_problem(tool: str, project: Path) -> str | None:
    """Why this folder is not a project of that engine (None = it is)."""
    if not project.is_dir():
        return f"{project} is not a folder"
    if tool == "unity" and not ((project / "Assets").is_dir() and (project / "ProjectSettings").is_dir()):
        return f"{project} is not a Unity project (no Assets and ProjectSettings folders)"
    if tool == "godot" and not (project / "project.godot").is_file():
        return f"{project} is not a Godot project (no project.godot)"
    if tool == "unreal" and not any(project.glob("*.uproject")):
        return f"{project} is not an Unreal project (no .uproject file)"
    return None


def status() -> dict:
    """The remembered project of every engine and whether it is still there."""
    out = {}
    for tool, p in load().items():
        if tool != "blender":
            out[tool] = {"project": p, "ok": project_problem(tool, Path(p)) is None}
    return out


def model_files(item: Path) -> dict:
    """The model's files by kind, read from its gen.json (every tier's GLB, the FBX, the .blend)."""
    g = json.loads((item / "gen.json").read_text(encoding="utf-8"))
    rep = g.get("report") or {}
    tiers = rep.get("tiers") or {}
    canon = rep.get("canonical") or next(iter(tiers), None)
    glbs = [tiers[t]["file"] for t in tiers if tiers[t].get("file", "").endswith(".glb") and (item / tiers[t]["file"]).is_file()]
    name = g.get("name") or item.name
    fbx = [f for f in (f"{name}.fbx",) if (item / f).is_file()]
    blend = [f for f in (f"{name}.blend",) if (item / f).is_file()]
    return {"name": name, "canonical": tiers.get(canon, {}).get("file") if canon else None, "glb": glbs, "fbx": fbx, "blend": blend}


def send(item: Path, tool: str, project: str | None = None, blender: str | None = None) -> dict:
    """Copy (or open) the model in `item` for `tool`. Returns {"folder", "files"} or {"opened"}. Raises ValueError."""
    if tool not in TOOLS:
        raise ValueError(f"send to one of {', '.join(TOOLS)}")
    if not (item / "gen.json").is_file():
        raise ValueError("no such model")
    files = model_files(item)
    name = files["name"]
    if tool == "blender":
        if not blender:
            raise ValueError("Blender was not found — install it or set MESHGATE_BLENDER")
        if files["blend"]:
            subprocess.Popen([blender, str(item / files["blend"][0])], start_new_session=True)
            return {"opened": files["blend"][0]}
        glb = files["canonical"] or (files["glb"] or [None])[0]
        if not glb:
            raise ValueError("the model has no file to open")
        expr = ("import bpy; bpy.ops.wm.read_homefile(use_empty=True); "
                f"bpy.ops.import_scene.gltf(filepath={str(item / glb)!r})")
        subprocess.Popen([blender, "--python-expr", expr], start_new_session=True)
        return {"opened": glb}
    project = project or load().get(tool)
    if not project:
        raise ValueError(f"choose your {LABELS[tool]} project folder first")
    root = Path(project).expanduser().resolve()
    why = project_problem(tool, root)
    if why:
        raise ValueError(why)
    if tool == "unity":
        dest, pick = root / "Assets" / "MeshGate" / name, files["glb"] + files["fbx"]
    elif tool == "godot":
        dest, pick = root / "meshgate" / name, files["glb"]
    else:
        dest, pick = root / "Content" / "MeshGate" / name, files["fbx"] or files["glb"][:1]
    if not pick:
        raise ValueError(f"the model has no file {LABELS[tool]} can import")
    dest.mkdir(parents=True, exist_ok=True)
    for f in pick:
        shutil.copyfile(item / f, dest / f)   # replaced in place: the engine re-imports it
    remember(tool, str(root))
    return {"folder": str(dest), "files": pick}
