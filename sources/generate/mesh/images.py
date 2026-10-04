"""Text → concept picture: for image-only 3D generators (TripoSR) and as a guide for the kit engine.

Providers:
    codex   Codex CLI's built-in image generation (gpt-image-2) with your ChatGPT sign-in — no API key needed
    openai  gpt-image-1 over the API (OPENAI_API_KEY)
    fal     FLUX schnell on fal.ai (FAL_KEY)

Kinds (prompts in sources/generate/prompts):
    single  one three-quarter product shot — what image-to-3D models reconstruct best
    sheet   a 2 × 2 orthographic turnaround (front, side, back, top) — what a modeler (or the kit engine's AI) builds from

MESHGATE_OPENAI_URL overrides the OpenAI base URL; MESHGATE_CODEX points at another codex executable (tests).
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path

from . import fal
from . import net as http

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
PROVIDERS = {"codex": None, "openai": "OPENAI_API_KEY", "fal": "FAL_KEY"}   # None: a CLI, not a key
STYLES_HINT = "clean stylized game asset"


def codex_exe() -> str | None:
    return os.environ.get("MESHGATE_CODEX") or shutil.which("codex")


def available() -> dict:
    return {k: bool(codex_exe()) if k == "codex" else bool(os.environ.get(v)) for k, v in PROVIDERS.items()}


def pick(preferred: str | None = None) -> str | None:
    if preferred:
        return preferred
    return next((k for k, ok in available().items() if ok), None)


def concept_prompt(description: str, kind: str = "single", style: str | None = None) -> str:
    template = (PROMPTS / f"concept_{kind}.md").read_text(encoding="utf-8")
    return template.format(description=description.strip(), style=style or STYLES_HINT)


def _codex(prompt: str, out: Path, timeout: int, log) -> Path:
    """Codex CLI → gpt-image-2. It may only write inside its working folder (workspace-write sandbox), so it saves
    out.png there and MeshGate copies it; Codex sometimes picks its own name, so the newest PNG is the fallback."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import procs
    exe = codex_exe()
    if not exe:
        raise http.ProviderError("the Codex CLI is not installed — npm install -g @openai/codex, then codex login")
    task = (f"Use your image generation tool (gpt-image-2) to create one image.\n\nPROMPT:\n{prompt}\n\n"
            "Requirements:\n- You MUST call the image generation tool; do not write a script, call curl or draw the PNG "
            "any other way.\n- Save the PNG as out.png in your current working directory (relative path out.png).\n"
            "- Reply with only the file name of the saved PNG.")
    with tempfile.TemporaryDirectory(prefix="meshgate-codex-img-") as work:
        log("    Codex (gpt-image-2): drawing…")
        try:
            proc = procs.run([exe, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", work, task],
                             timeout=timeout, cwd=work)
        except Exception as exc:  # noqa: BLE001 — timeout or a missing binary
            raise http.ProviderError(f"Codex image generation failed: {exc}") from None
        img = Path(work) / "out.png"
        if not img.exists():
            pngs = sorted(Path(work).glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            img = pngs[0] if pngs else img
        if not img.exists():
            said = " ".join((proc.stdout + proc.stderr).split())
            low = said.lower()
            if "out of credits" in low or "usage limit" in low or "quota" in low or "rate limit" in low:
                hint = "your Codex / ChatGPT plan is out of credits or at its limit — wait or top up, or use another " \
                       "picture generator (--image-provider openai or fal)"
            elif "login" in low or "not logged in" in low or "unauthorized" in low:
                hint = "Codex is not signed in — run `codex login`"
            else:
                hint = "signed in? run `codex login`"
            raise http.ProviderError(f"Codex finished without a picture ({hint}): {said[-300:] or 'no output'}")
        shutil.copyfile(img, out)
    return out


def text_to_image(prompt: str, out: Path, provider: str | None = None, log=print, kind: str = "single",
                  style: str | None = None, timeout: int = 600) -> Path:
    """Draw a concept picture for `prompt` (a description) and save it to `out`."""
    provider = pick(provider)
    if provider is None:
        raise http.ProviderError("turning a description into a picture needs the Codex CLI (signed in) or a key: "
                                 "OPENAI_API_KEY or FAL_KEY — or pass --image")
    full = concept_prompt(prompt, kind, style)
    out = Path(out)
    if provider == "codex":
        return _codex(full, out, timeout, log)
    if provider == "fal":
        return fal.text_to_image(full, out, log)
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise http.ProviderError("OPENAI_API_KEY is not set")
        base = os.environ.get("MESHGATE_OPENAI_URL", "https://api.openai.com/v1").rstrip("/")
        log("    OpenAI gpt-image-1: drawing the reference picture")
        res = http.request("POST", f"{base}/images/generations", headers={"Authorization": f"Bearer {key}"},
                           body={"model": "gpt-image-1", "prompt": full, "size": "1024x1024", "n": 1}, timeout=300)
        item = res["data"][0]
        if item.get("b64_json"):
            out.write_bytes(base64.b64decode(item["b64_json"]))
            return out
        return http.download(item["url"], out)
    raise http.ProviderError(f"unknown picture provider {provider} — use codex, openai or fal")
