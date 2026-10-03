"""Optional local components — big models MeshGate can install into ~/.cache/meshgate, each in its own Python venv.

    python3 meshgate.py gen --setup triposr      picture → 3D, MIT, ~3 GB, CPU, NVIDIA CUDA or Apple GPU (installed and wired in)
    python3 meshgate.py gen --setup hunyuan3d    picture → 3D, higher quality, ~10 GB, NVIDIA GPU recommended
    python3 meshgate.py gen --setup kimodo       text → character animation, ~20 GB, NVIDIA GPU, Meta Llama 3 access

Nothing here installs on its own: Studio → Status & AI → Optional components, or the commands above. Delete a
component's folder to remove it. Hunyuan3D and Kimodo are installed here first; generation uses them once a run on a
machine with a supported GPU has been checked (docs/generation.md).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from mesh import triposr

BASE = Path(os.environ.get("MESHGATE_COMPONENTS_HOME", Path.home() / ".cache" / "meshgate"))


class Component:
    """A git checkout (optional) plus a private venv with pinned packages."""

    def __init__(self, cid: str, *, label: str, what: str, python: str, packages: list[str], size: str, license_: str,
                 url: str, gpu: str, repo: str | None = None, commit: str | None = None, requirements: str | None = None,
                 editable: bool = False, extra_step: str | None = None):
        self.id, self.label, self.what, self.python_version = cid, label, what, python
        self.packages, self.size, self.license, self.url, self.gpu = packages, size, license_, url, gpu
        self.repo, self.commit, self.requirements, self.editable, self.extra_step = repo, commit, requirements, editable, extra_step
        self.home = BASE / cid
        self.checkout = self.home / "src"
        self.venv = self.home / "venv"

    def python(self) -> Path:
        return self.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def available(self) -> bool:
        return self.python().exists() and (self.home / "installed").exists()

    def ready_note(self) -> str | None:
        """What is still missing after the install, if anything (Kimodo: the Llama 3 sign-in)."""
        if self.id == "kimodo":
            token = os.environ.get("HF_TOKEN") or (Path.home() / ".cache" / "huggingface" / "token").exists()
            if not token:
                return "sign in to Hugging Face with access to Meta Llama 3 8B: hf auth login"
        return None

    def info(self) -> dict:
        return {"id": self.id, "label": self.label, "what": self.what, "size": self.size, "license": self.license,
                "url": self.url, "gpu": self.gpu, "installed": self.available(), "extra_step": self.extra_step,
                "missing": self.ready_note() if self.available() else None, "folder": str(self.home),
                "setup": f"meshgate.py gen --setup {self.id}"}

    def _python_request(self) -> str:
        if sys.platform == "darwin":
            arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() == "1"
            return f"cpython-{self.python_version}-macos-{'aarch64' if arm else 'x86_64'}-none"
        return self.python_version

    def setup(self, log=print) -> int:
        self.home.mkdir(parents=True, exist_ok=True)
        if self.repo:
            git = shutil.which("git")
            if not git:
                log("git is needed (https://git-scm.com)")
                return 1
            if not self.checkout.exists():
                log(f"fetching {self.repo}…")
                subprocess.check_call([git, "clone", "-q", self.repo, str(self.checkout)])
            subprocess.call([git, "-C", str(self.checkout), "fetch", "-q", "origin"])
            subprocess.check_call([git, "-C", str(self.checkout), "checkout", "-q", self.commit])
        uv = shutil.which("uv")
        if not uv:
            log("uv is needed for the component's Python (https://docs.astral.sh/uv/): curl -LsSf https://astral.sh/uv/install.sh | sh")
            return 1
        if not self.python().exists():
            subprocess.check_call([uv, "venv", "-q", "--python", self._python_request(), str(self.venv)])
        pip = [uv, "pip", "install", "--python", str(self.python())]
        log(f"installing {self.label} ({self.size} with the models)…")
        if self.packages:
            subprocess.check_call(pip + self.packages)
        if self.requirements:
            subprocess.check_call(pip + ["-r", str(self.checkout / self.requirements)])
        if self.editable:
            subprocess.check_call(pip + ["-e", str(self.checkout)])
        (self.home / "installed").write_text(self.commit or "", encoding="utf-8")
        log(f"{self.label} installed in {self.home}." + (f" Next: {self.extra_step}" if self.extra_step else ""))
        return 0


class _TripoSR:
    """The installed-and-wired TripoSR, seen through the same interface."""
    id, label = "triposr", "TripoSR"

    def available(self) -> bool:
        return triposr.available()

    def setup(self, log=print) -> int:
        return triposr.setup(log=log)

    def info(self) -> dict:
        return {"id": "triposr", "label": "TripoSR", "what": "picture → 3D, used by the mesh engine", "size": "~3 GB (more with CUDA)",
                "license": "MIT (code and weights)", "url": "https://github.com/VAST-AI-Research/TripoSR",
                "gpu": "CPU, NVIDIA CUDA or Apple GPU", "installed": triposr.available(), "extra_step": None, "missing": None,
                "folder": str(triposr.HOME), "setup": "meshgate.py gen --setup triposr"}


COMPONENTS = {
    "triposr": _TripoSR(),
    "hunyuan3d": Component(
        "hunyuan3d", label="Hunyuan3D-2", what="picture → 3D with finer shapes than TripoSR (Tencent)",
        python="3.10", packages=["torch", "torchvision"], requirements="requirements.txt", editable=True,
        repo="https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git", commit="f8db63096c8282cb27354314d896feba5ba6ff8a",
        size="~10 GB", url="https://github.com/Tencent-Hunyuan/Hunyuan3D-2",
        license_="Tencent Hunyuan 3D Community License — not for use in the EU, the UK or South Korea",
        gpu="NVIDIA GPU with 6 GB+ for shapes, 16 GB+ with textures; Apple GPU: shapes only, slow"),
    "kimodo": Component(
        "kimodo", label="Kimodo", what="text → animation for Humanoid characters (NVIDIA): walk, wave, shamble…",
        python="3.10", packages=["torch", "kimodo @ git+https://github.com/nv-tlabs/kimodo.git@58e781898b3d7e328a676a75d3e338c45dce3ad9"],
        size="~20 GB", url="https://github.com/nv-tlabs/kimodo",
        license_="code Apache-2.0, models NVIDIA Open Model License; text encoder Meta Llama 3 Community License",
        gpu="NVIDIA GPU (tested on RTX 3090/4090); ~3 GB VRAM with the text encoder on the CPU",
        extra_step="accept the Meta Llama 3 8B Instruct license on huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct, "
                   "then run hf auth login once"),
}


def status() -> dict:
    return {cid: c.info() for cid, c in COMPONENTS.items()}
