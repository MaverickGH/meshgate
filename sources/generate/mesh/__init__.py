"""Neural mesh generators behind one interface: generate(image=, prompt=, out_dir=, log=, **opts) → raw mesh path.

    triposr  local, MIT, image → 3D (meshgate.py gen --setup triposr)
    meshy    cloud, MESHY_API_KEY, text or image → 3D
    tripo    cloud, TRIPO_API_KEY, text or image → 3D
    fal      cloud, FAL_KEY, image → 3D with TRELLIS / Hunyuan3D / TripoSR; text via FLUX → image
    command  any generator you run yourself (--mesh-cmd)

The raw result then goes through sources/generate/refine.py (Blender) to meet the contract per quality tier.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import command, fal, images, meshy, triposr, tripo
from .net import ProviderError

PROVIDERS = {m.INFO["id"]: m for m in (triposr, meshy, tripo, fal, command)}


def status() -> dict:
    """Provider id → info plus whether it can run now (installed or key set)."""
    return {pid: {**m.INFO, "ready": bool(m.available())} for pid, m in PROVIDERS.items()}


def default_provider(has_image: bool) -> str | None:
    order = ["triposr", "fal", "meshy", "tripo"] if has_image else ["meshy", "tripo", "fal", "triposr"]
    for pid in order:
        if PROVIDERS[pid].available():
            if pid == "triposr" and not has_image and not any(images.available().values()):
                continue
            return pid
    return None


def make(provider: str, *, prompt: str | None, image: str | None, out_dir: Path, log=print, **opts) -> dict:
    """Run a provider; for image-only providers without an image, draw one from the text first. Returns
    {"raw": path, "reference": image path or None}."""
    if provider not in PROVIDERS:
        raise ProviderError(f"unknown provider {provider} — use one of {', '.join(PROVIDERS)}")
    mod = PROVIDERS[provider]
    out_dir.mkdir(parents=True, exist_ok=True)
    if not image and "text" not in mod.INFO["inputs"] and prompt:
        image = str(images.text_to_image(prompt, out_dir / "reference.png", opts.get("image_provider"), log, kind="single"))
        log(f"    reference image drawn from the description: {Path(image).name}")
    raw = mod.generate(image=image, prompt=prompt, out_dir=out_dir, log=log, **opts)
    if not Path(raw).exists() or os.path.getsize(raw) == 0:
        raise ProviderError(f"{provider} produced no mesh")
    return {"raw": str(raw), "reference": image}
