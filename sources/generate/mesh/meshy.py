"""Meshy (https://www.meshy.ai) — cloud text → 3D and image → 3D. Set MESHY_API_KEY (paid credits).

Image: POST /openapi/v1/image-to-3d with a data URI. Text: v2 text-to-3d preview (shape), then refine (texture).
MESHGATE_MESHY_URL overrides the base URL (tests use a local stand-in server).
"""

from __future__ import annotations

import os
from pathlib import Path

from . import net as http

INFO = {"id": "meshy", "label": "Meshy (cloud)", "inputs": ["image", "text"], "key_env": "MESHY_API_KEY",
        "license": "commercial API; outputs owned per Meshy terms", "url": "https://docs.meshy.ai"}


def available() -> bool:
    return bool(os.environ.get("MESHY_API_KEY"))


def _base() -> str:
    return os.environ.get("MESHGATE_MESHY_URL", "https://api.meshy.ai").rstrip("/")


def _headers() -> dict:
    key = os.environ.get("MESHY_API_KEY")
    if not key:
        raise http.ProviderError("MESHY_API_KEY is not set — get a key at https://www.meshy.ai/api")
    return {"Authorization": f"Bearer {key}"}


def _task(path: str, body: dict, log, label: str) -> dict:
    h = _headers()
    task_id = http.request("POST", f"{_base()}{path}", headers=h, body=body)["result"]
    log(f"    {label}: task {task_id}")
    return http.poll(lambda: http.request("GET", f"{_base()}{path}/{task_id}", headers=h),
                     done=lambda r: r.get("status") == "SUCCEEDED",
                     failed=lambda r: (f"Meshy {label} {r.get('status')}: {(r.get('task_error') or {}).get('message', '')}"
                                       if r.get("status") in ("FAILED", "CANCELED") else None),
                     interval=float(os.environ.get("MESHGATE_POLL", 5)), log=log, label=f"Meshy {label}")


def generate(*, image: str | None, prompt: str | None, out_dir: Path, log=print, **opts) -> Path:
    pbr = bool(opts.get("pbr", True))
    if image:
        body = {"image_url": http.data_uri(image), "should_texture": True, "enable_pbr": pbr, "topology": "triangle",
                "target_formats": ["glb"]}
        if prompt:
            body["texture_prompt"] = prompt[:800]
        task = _task("/openapi/v1/image-to-3d", body, log, "image-to-3d")
    elif prompt:
        preview = _task("/openapi/v2/text-to-3d", {"mode": "preview", "prompt": prompt[:800], "topology": "triangle"},
                        log, "text-to-3d preview")
        task = _task("/openapi/v2/text-to-3d", {"mode": "refine", "preview_task_id": preview["id"], "enable_pbr": pbr},
                     log, "text-to-3d refine")
    else:
        raise http.ProviderError("Meshy needs a description or an image")
    url = (task.get("model_urls") or {}).get("glb")
    if not url:
        raise http.ProviderError("Meshy finished without a GLB URL")
    return http.download(url, out_dir / "raw_meshy.glb")
