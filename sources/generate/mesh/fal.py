"""fal.ai (https://fal.ai) — hosted open image → 3D models; text → image → 3D with FLUX. Set FAL_KEY (paid credits).

Models (--fal-model): fal-ai/trellis (MIT, default), fal-ai/hunyuan3d/v2 (Tencent licence: not for the EU, UK or
South Korea), fal-ai/triposr (MIT). Queue API: POST queue.fal.run/<model> → poll status_url → GET response_url.
MESHGATE_FAL_URL overrides the queue base URL.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import net as http

INFO = {"id": "fal", "label": "fal.ai: TRELLIS / Hunyuan3D / TripoSR (cloud)", "inputs": ["image", "text"],
        "key_env": "FAL_KEY", "license": "per model: TRELLIS MIT, TripoSR MIT, Hunyuan3D Tencent (not EU/UK/KR)",
        "url": "https://fal.ai/models"}
MODELS = {  # model id → (image field name, where the GLB is in the output)
    "fal-ai/trellis": ("image_url", "model_mesh"),
    "fal-ai/hunyuan3d/v2": ("input_image_url", "model_mesh"),
    "fal-ai/triposr": ("image_url", "model_mesh"),
}
TEXT_TO_IMAGE = "fal-ai/flux/schnell"


def available() -> bool:
    return bool(os.environ.get("FAL_KEY"))


def _headers() -> dict:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise http.ProviderError("FAL_KEY is not set — get a key at https://fal.ai/dashboard/keys")
    return {"Authorization": f"Key {key}"}


def run(model: str, payload: dict, log, label: str) -> dict:
    base = os.environ.get("MESHGATE_FAL_URL", "https://queue.fal.run").rstrip("/")
    h = _headers()
    sub = http.request("POST", f"{base}/{model}", headers=h, body=payload)
    status_url = sub.get("status_url") or f"{base}/{model}/requests/{sub['request_id']}/status"
    response_url = sub.get("response_url") or f"{base}/{model}/requests/{sub['request_id']}"
    log(f"    fal {model}: request {sub.get('request_id')}")
    http.poll(lambda: http.request("GET", status_url, headers=h),
              done=lambda r: r.get("status") == "COMPLETED",
              failed=lambda r: f"fal {model}: {r.get('error')}" if r.get("status") in ("FAILED", "ERROR") else None,
              interval=float(os.environ.get("MESHGATE_POLL", 3)), log=log, label=label)
    return http.request("GET", response_url, headers=h)


def text_to_image(prompt: str, out: Path, log=print) -> Path:
    res = run(TEXT_TO_IMAGE, {"prompt": prompt, "image_size": "square_hd", "num_images": 1}, log, "fal FLUX")
    return http.download(res["images"][0]["url"], out)


def generate(*, image: str | None, prompt: str | None, out_dir: Path, log=print, **opts) -> Path:
    model = opts.get("fal_model") or "fal-ai/trellis"
    if model not in MODELS:
        raise http.ProviderError(f"unknown fal model {model} — use one of {', '.join(MODELS)}")
    if not image:
        if not prompt:
            raise http.ProviderError("fal needs an image or a description")
        image = str(text_to_image(image_prompt(prompt), out_dir / "reference.png", log))
        log(f"    reference image from the description: {Path(image).name}")
    field, key = MODELS[model]
    res = run(model, {field: http.data_uri(image)}, log, f"fal {model.split('/')[-1]}")
    url = (res.get(key) or {}).get("url")
    if not url:
        raise http.ProviderError(f"fal {model} finished without a mesh URL")
    return http.download(url, out_dir / "raw_fal.glb")


def image_prompt(prompt: str) -> str:
    """Image-to-3D models want one object, whole, centred, on a plain background, lit evenly."""
    from .images import concept_prompt
    return concept_prompt(prompt, "single")
