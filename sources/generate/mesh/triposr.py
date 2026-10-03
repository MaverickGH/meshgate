"""TripoSR — local image → 3D (MIT code and weights, VAST-AI-Research + Stability AI). CPU, NVIDIA CUDA or Apple MPS.

    python3 meshgate.py gen --setup triposr     # one time: ~3 GB into ~/.cache/meshgate/triposr (Python 3.11 venv)
    python3 meshgate.py gen --image photo.png --engine mesh --provider triposr

The venv lives outside the repository and outside your Python; delete the folder to remove it. The model weights
(stabilityai/TripoSR, ~1.7 GB) download from Hugging Face on the first run, no account needed.
"""

from __future__ import annotations

import os
import ctypes
import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HOME = Path(os.environ.get("MESHGATE_TRIPOSR_HOME", Path.home() / ".cache" / "meshgate" / "triposr"))
REPO = HOME / "TripoSR"
VENV = HOME / "venv"
COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"   # the TripoSR revision MeshGate is tested with
SOURCE_SHA256 = "a7b3871a1b4377bef96cbfb99bdc952bdd4f5df9f65fea4208d978a343fd1162"
PACKAGES = ["torch", "omegaconf==2.3.0", "einops==0.7.0", "transformers==4.35.0", "trimesh==4.0.5", "rembg",
            "onnxruntime", "huggingface-hub<0.26", "imageio", "PyMCubes", "Pillow", "numpy<2"]
RUNNER = Path(__file__).with_name("triposr_run.py")
INFO = {"id": "triposr", "label": "TripoSR (local)", "inputs": ["image"], "needs": "meshgate.py gen --setup triposr",
        "license": "MIT (code and weights)", "url": "https://github.com/VAST-AI-Research/TripoSR",
        "vertex_srgb": True}   # its vertex colours are picture values, not linear


def python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def available() -> bool:
    return python().exists() and (REPO / "tsr").is_dir()


def _python_request() -> str:
    """Python 3.11 for this machine's real CPU. An Intel build of uv on Apple Silicon would otherwise fetch an x86_64
    Python, which has no current PyTorch or numba wheels."""
    if sys.platform == "darwin":
        arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() == "1"
        return f"cpython-3.11-macos-{'aarch64' if arm else 'x86_64'}-none"
    return "3.11"


def _torch_selection() -> tuple[str, str | None]:
    """Keep explicit choices; Windows defaults to CPU or the CUDA wheel validated for Pascal–Ada."""
    spec = os.environ.get("MESHGATE_TRIPOSR_TORCH_SPEC")
    index = os.environ.get("MESHGATE_TRIPOSR_TORCH_INDEX")
    if spec or index or sys.platform != "win32":
        return spec or "torch", index
    nvidia = shutil.which("nvidia-smi")
    if nvidia:
        try:
            result = subprocess.check_output([nvidia, "--query-gpu=compute_cap,driver_version", "--format=csv,noheader"],
                                             text=True, timeout=10).splitlines()[0]
            capability, driver = [float(v.strip()) for v in result.split(",")]
            if 6 <= capability < 10 and driver >= 520:
                return "torch==2.7.1", "https://download.pytorch.org/whl/cu118"
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            pass
    return "torch==2.7.1", "https://download.pytorch.org/whl/cpu"


def setup(log=print) -> int:
    """Clone TripoSR at the tested revision and install its runtime into a private Python 3.11 venv."""
    if os.name == "nt":
        try:
            ctypes.WinDLL("msvcp140.dll")
        except OSError:
            log("TripoSR needs Microsoft Visual C++ Redistributable x64 (not Build Tools). "
                "Install https://aka.ms/vc14/vc_redist.x64.exe and retry Install in Studio.")
            return 1
    HOME.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if not git or (REPO.exists() and not (REPO / ".git").is_dir()):
        marker = REPO / ".meshgate-revision"
        if not marker.exists() or marker.read_text(encoding="ascii").strip() != COMMIT:
            if REPO.exists():
                raise RuntimeError(f"Unrecognized TripoSR folder: {REPO}; choose a new MESHGATE_TRIPOSR_HOME")
            log("downloading the pinned TripoSR source archive (Git is not required)…")
            url = f"https://codeload.github.com/VAST-AI-Research/TripoSR/zip/{COMMIT}"
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
                raise RuntimeError("TripoSR source checksum mismatch")
            with tempfile.TemporaryDirectory(dir=HOME) as tmp:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for name in archive.namelist():
                        path = (Path(tmp) / name).resolve()
                        if not path.is_relative_to(Path(tmp).resolve()):
                            raise RuntimeError("Unsafe TripoSR archive path")
                    archive.extractall(tmp)
                source = Path(tmp) / f"TripoSR-{COMMIT}"
                (source / ".meshgate-revision").write_text(COMMIT, encoding="ascii")
                source.rename(REPO)
    else:
        if not REPO.exists():
            subprocess.check_call([git, "clone", "-q", "https://github.com/VAST-AI-Research/TripoSR.git", str(REPO)])
        subprocess.call([git, "-C", str(REPO), "fetch", "-q", "--depth", "50", "origin"])
        subprocess.check_call([git, "-C", str(REPO), "checkout", "-q", COMMIT])
    uv = shutil.which("uv")
    torch_spec, torch_index = _torch_selection()
    packages = [torch_spec if p == "torch" else p for p in PACKAGES]
    if uv:
        if not python().exists():
            subprocess.check_call([uv, "venv", "-q", "--managed-python", "--python", _python_request(), str(VENV)])
        installer = [uv, "pip", "install", "-q", "--python", str(python())]
    else:
        base = (sys.executable if (3, 10) <= sys.version_info[:2] <= (3, 12) else
                next((p for p in ("python3.11", "python3.12", "python3.10") if shutil.which(p)), None))
        if not base:
            log("Python 3.10–3.12 or uv (https://docs.astral.sh/uv/) is needed for the TripoSR environment")
            return 1
        if not python().exists():
            subprocess.check_call([base, "-m", "venv", str(VENV)])
        subprocess.check_call([str(python()), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        installer = [str(python()), "-m", "pip", "install", "-q"]
    if torch_index:
        log(f"installing {torch_spec} from {torch_index}")
        subprocess.check_call([*installer, torch_spec, "--index-url", torch_index])
        packages = [p for p in packages if p != torch_spec]
    subprocess.check_call([*installer, *packages])
    log(f"TripoSR ready: {REPO} (venv {VENV}). The weights download on the first run.")
    return 0


def generate(*, image: str | None, prompt: str | None, out_dir: Path, log=print, **opts) -> Path:
    """image → raw GLB with vertex colours (glTF axes, front +Z). Returns the file path."""
    if not image:
        raise RuntimeError("TripoSR turns a picture into 3D — give --image (or pick a provider that takes text)")
    if not available():
        raise RuntimeError("TripoSR is not set up — run: python3 meshgate.py gen --setup triposr")
    out = out_dir / "raw_triposr.glb"
    cmd = [str(python()), str(RUNNER), "--repo", str(REPO), "--image", str(image), "--out", str(out),
           "--resolution", str(int(opts.get("resolution") or 256))]
    if opts.get("no_remove_bg"):
        cmd.append("--no-remove-bg")
    env = {**os.environ, "PYTORCH_ENABLE_MPS_FALLBACK": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    import procs   # sources/generate/procs.py: stops with the run
    proc = procs.run(cmd, env=env, timeout=int(opts.get("timeout") or 1800))
    (out_dir / "triposr.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    finished = out.exists() and any(line.startswith("MESHGATE_TRIPOSR ") and " triangles on " in line
                                    for line in proc.stdout.splitlines())
    if proc.returncode and finished:   # a crash while Python shut down, after the mesh was written whole
        log(f"    (TripoSR exited with code {proc.returncode} after writing the mesh; the mesh is complete)")
    elif proc.returncode or not out.exists():
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-12:])
        raise RuntimeError(f"TripoSR failed:\n{tail}")
    for line in proc.stdout.splitlines():
        if line.startswith("MESHGATE_TRIPOSR "):
            log("    " + line[len("MESHGATE_TRIPOSR "):])
    return out
