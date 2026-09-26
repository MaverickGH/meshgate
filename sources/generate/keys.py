"""API keys for AI services, kept in one local file that MeshGate Studio and `meshgate.py gen` both read.

    ~/.meshgate/keys.json      (MESHGATE_CONFIG_DIR overrides the folder; the file is readable by you only)

Environment variables win over the file, so CI and shells keep working as before. Keys are never sent anywhere but the
service they belong to, and Studio only ever shows the last four characters.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

KNOWN = {   # name → (what it unlocks, where to get it)
    "ANTHROPIC_API_KEY": ("Claude Code without signing in (kit engine)", "https://console.anthropic.com/settings/keys"),
    "OPENAI_API_KEY": ("Codex CLI, and text → picture with gpt-image-1", "https://platform.openai.com/api-keys"),
    "GEMINI_API_KEY": ("Gemini CLI without signing in (kit engine)", "https://aistudio.google.com/apikey"),
    "MESHY_API_KEY": ("Meshy: text or picture → 3D in the cloud", "https://www.meshy.ai/api"),
    "TRIPO_API_KEY": ("Tripo: text or picture → 3D in the cloud", "https://platform.tripo3d.ai"),
    "FAL_KEY": ("fal.ai: TRELLIS / Hunyuan3D / TripoSR, FLUX text → picture", "https://fal.ai/dashboard/keys"),
}


def folder() -> Path:
    return Path(os.environ.get("MESHGATE_CONFIG_DIR") or Path.home() / ".meshgate")


def path() -> Path:
    return folder() / "keys.json"


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items() if k in KNOWN and v}
    except (OSError, ValueError):
        return {}


def apply_env() -> list[str]:
    """Put saved keys into os.environ where the environment has none. Returns the names applied."""
    applied = []
    for k, v in load().items():
        if not os.environ.get(k):
            os.environ[k] = v
            applied.append(k)
    return applied


def save(name: str, value: str) -> None:
    """Store (or, with an empty value, remove) one key; the file is created readable by the owner only."""
    if name not in KNOWN:
        raise ValueError(f"unknown key {name}")
    value = value.strip()
    if any(c.isspace() for c in value) or len(value) > 400:
        raise ValueError("that does not look like an API key")
    data = load()
    if value:
        data[name] = value
    else:
        data.pop(name, None)
    folder().mkdir(parents=True, exist_ok=True)
    p = path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    os.replace(tmp, p)
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def status() -> dict:
    """name → {set, source (env|file|None), hint (last 4 chars), what, url} — never the key itself."""
    saved = load()
    out = {}
    for k, (what, url) in KNOWN.items():
        v = os.environ.get(k) or saved.get(k)
        source = "file" if k in saved and os.environ.get(k) == saved.get(k) else ("env" if os.environ.get(k) else None)
        out[k] = {"set": bool(v), "source": source, "hint": ("…" + v[-4:]) if v and len(v) > 8 else ("set" if v else ""),
                  "what": what, "url": url}
    return out
