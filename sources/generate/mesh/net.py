"""Tiny stdlib HTTP helpers for the cloud providers: JSON calls, polling, downloads, data URIs."""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

UA = "MeshGate/0.6 (+https://github.com/MaverickGH/meshgate)"


class ProviderError(RuntimeError):
    pass


def request(method: str, url: str, *, headers: dict | None = None, body=None, timeout: int = 120) -> dict:
    data, hdrs = None, {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise ProviderError(f"{method} {url.split('?')[0]} → HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise ProviderError(f"{method} {url.split('?')[0]}: {exc.reason}") from None
    return json.loads(raw or b"{}")


def multipart(url: str, *, headers: dict, field: str, path: Path, timeout: int = 120) -> dict:
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": UA, "Content-Type": f"multipart/form-data; boundary={boundary}", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"upload → HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:600]}") from None


def download(url: str, dest: Path, timeout: int = 300) -> Path:
    if url.startswith("data:"):
        dest.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    return dest


def data_uri(path: str | Path) -> str:
    p = Path(path)
    ctype = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{ctype};base64,{base64.b64encode(p.read_bytes()).decode()}"


def poll(fetch, *, done, failed, interval: float = 5.0, timeout: float = 1800, log=None, label: str = "") -> dict:
    """Call fetch() until done(result) or failed(result) (which returns an error text); log progress changes."""
    start, last = time.time(), None
    while True:
        res = fetch()
        err = failed(res)
        if err:
            raise ProviderError(err)
        if done(res):
            return res
        progress = res.get("progress") if isinstance(res, dict) else None
        state = f"{label} {progress}%" if progress is not None else label
        if log and state != last:
            log(f"    {state}")
            last = state
        if time.time() - start > timeout:
            raise ProviderError(f"{label}: no result after {timeout:.0f} s")
        time.sleep(interval)
