"""Any local or remote generator you already run: --mesh-cmd "python run.py {image} --out {out}".

Placeholders: {image} (reference image path, may be empty), {prompt} (the description), {out} (a .glb/.obj path the
command must write), {out_dir}. The command runs in the output folder; its output file is refined like any other.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from . import net as http

INFO = {"id": "command", "label": "Your own command", "inputs": ["image", "text"], "license": "yours",
        "url": "docs/generation.md"}


def available() -> bool:
    return True


def generate(*, image: str | None, prompt: str | None, out_dir: Path, log=print, **opts) -> Path:
    template = opts.get("mesh_cmd")
    if not template:
        raise http.ProviderError('give --mesh-cmd "your-generator {image} --out {out}"')
    ext = ".obj" if "{out_obj}" in template else ".glb"
    out = out_dir / f"raw_command{ext}"
    import os
    parts = shlex.split(template, posix=os.name != "nt")   # POSIX rules would eat the backslashes of Windows paths
    parts = [str(Path(c).resolve()) if ("/" in c or "\\" in c or c.startswith(".")) and "{" not in c and not c.startswith("-")
             and Path(c).exists() else c for c in parts]   # the command runs in the output folder
    subs = {"{image}": image or "", "{prompt}": prompt or "", "{out}": str(out), "{out_obj}": str(out),
            "{out_dir}": str(out_dir)}
    cmd = []
    for p in parts:
        for k, v in subs.items():
            p = p.replace(k, v)
        cmd.append(p)
    proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=int(opts.get("timeout") or 3600))
    (out_dir / "command.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode or not out.exists():
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-10:])
        raise http.ProviderError(f"the mesh command failed (exit {proc.returncode}) or wrote no {out.name}:\n{tail}")
    return out
