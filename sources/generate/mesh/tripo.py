"""Tripo (https://www.tripo3d.ai) — cloud text → 3D and image → 3D. Set TRIPO_API_KEY (paid credits).

POST /v2/openapi/task with type text_to_model or image_to_model (the image goes up first through /upload), then poll
GET /task/{id} until status "success" and download output.pbr_model or output.model. Written from Tripo's public
API docs; not yet run against the live service. MESHGATE_TRIPO_URL overrides the base URL.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import net as http

INFO = {"id": "tripo", "label": "Tripo (cloud)", "inputs": ["image", "text"], "key_env": "TRIPO_API_KEY",
        "license": "commercial API; outputs owned per Tripo terms", "url": "https://platform.tripo3d.ai/docs"}
FAILED = {"failed", "cancelled", "banned", "expired", "unknown"}


def available() -> bool:
    return bool(os.environ.get("TRIPO_API_KEY"))


def _base() -> str:
    return os.environ.get("MESHGATE_TRIPO_URL", "https://api.tripo3d.ai/v2/openapi").rstrip("/")


def generate(*, image: str | None, prompt: str | None, out_dir: Path, log=print, **opts) -> Path:
    key = os.environ.get("TRIPO_API_KEY")
    if not key:
        raise http.ProviderError("TRIPO_API_KEY is not set — get a key at https://platform.tripo3d.ai")
    h = {"Authorization": f"Bearer {key}"}
    if image:
        up = http.multipart(f"{_base()}/upload", headers=h, field="file", path=Path(image))
        token = (up.get("data") or {}).get("image_token") or (up.get("data") or {}).get("file_token")
        if not token:
            raise http.ProviderError(f"Tripo upload returned no token: {str(up)[:300]}")
        ext = Path(image).suffix.lower().lstrip(".").replace("jpeg", "jpg") or "png"
        body = {"type": "image_to_model", "file": {"type": ext, "file_token": token}, "texture": True, "pbr": True}
        if prompt:
            body["prompt"] = prompt[:1024]
    elif prompt:
        body = {"type": "text_to_model", "prompt": prompt[:1024], "texture": True, "pbr": True}
    else:
        raise http.ProviderError("Tripo needs a description or an image")
    res = http.request("POST", f"{_base()}/task", headers=h, body=body)
    task_id = (res.get("data") or {}).get("task_id")
    if not task_id:
        raise http.ProviderError(f"Tripo returned no task id: {str(res)[:300]}")
    log(f"    Tripo {body['type']}: task {task_id}")
    task = http.poll(lambda: http.request("GET", f"{_base()}/task/{task_id}", headers=h).get("data") or {},
                     done=lambda d: d.get("status") == "success",
                     failed=lambda d: f"Tripo task {d.get('status')}" if d.get("status") in FAILED else None,
                     interval=float(os.environ.get("MESHGATE_POLL", 4)), log=log, label="Tripo")
    out = task.get("output") or {}
    url = out.get("pbr_model") or out.get("model") or out.get("base_model")
    if not url:
        raise http.ProviderError("Tripo finished without a model URL")
    return http.download(url, out_dir / "raw_tripo.glb")
