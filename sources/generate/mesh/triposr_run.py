"""Runs inside the TripoSR venv (see triposr.py): one image → raw GLB with vertex colours, glTF axes (front +Z).

    <venv>/bin/python triposr_run.py --repo <TripoSR> --image in.png --out raw.glb [--resolution 256] [--no-remove-bg]

Differences from TripoSR's own run.py: PyMCubes replaces torchmcubes (which needs a C++/CUDA build), Apple MPS is used
when present with a CPU fallback, and the mesh is turned to the orientation of TripoSR's demo before writing GLB.
"""

import argparse
import os
import sys
import time
import types

import numpy as np


def install_mcubes_shim():
    """TripoSR imports `torchmcubes.marching_cubes`; provide it with PyMCubes when the compiled package is missing."""
    try:
        import torchmcubes  # noqa: F401
        return "torchmcubes"
    except ImportError:
        pass
    import mcubes
    import torch

    def marching_cubes(volume, threshold):
        v, f = mcubes.marching_cubes(volume.detach().cpu().numpy().astype(np.float64), float(threshold))
        v = v[:, ::-1].copy()   # torchmcubes returns (x, y, z) with x along the last axis; PyMCubes uses index order
        return torch.from_numpy(v.astype(np.float32)), torch.from_numpy(f.astype(np.int64))

    mod = types.ModuleType("torchmcubes")
    mod.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = mod
    return "PyMCubes"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resolution", type=int, default=256)
    ap.add_argument("--foreground-ratio", type=float, default=0.85)
    ap.add_argument("--no-remove-bg", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, args.repo)
    mc = install_mcubes_shim()

    import torch
    import trimesh
    from PIL import Image
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    t0 = time.time()
    device = "mps" if torch.backends.mps.is_available() else ("cuda:0" if torch.cuda.is_available() else "cpu")
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(8192)

    img = Image.open(args.image)
    ref_mean = None
    if args.no_remove_bg:
        image = img.convert("RGB")
    else:
        import rembg
        image = remove_background(img, rembg.new_session())
        image = resize_foreground(image, args.foreground_ratio)
        rgba = np.array(image)
        fg = rgba[..., 3] > 128
        if fg.sum() > 100:
            ref_mean = rgba[fg][:, :3].astype(np.float32).mean(0)
        a = rgba.astype(np.float32) / 255.0
        a = a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5
        image = Image.fromarray((a * 255.0).astype(np.uint8))
    t1 = time.time()

    def run(dev):
        model.to(dev)
        with torch.no_grad():
            codes = model([image], device=dev)
        return model.extract_mesh(codes, True, resolution=args.resolution)[0]

    try:
        mesh = run(device)
    except Exception as exc:  # noqa: BLE001 — some ops are missing on MPS in older torch builds
        if device == "cpu":
            raise
        print(f"MESHGATE_TRIPOSR {device} failed ({type(exc).__name__}), retrying on CPU")
        device = "cpu"
        mesh = run(device)
    t2 = time.time()

    # TripoSR's colours come out darker than the picture: match the mean colour of the object in the photo
    gain_note = ""
    colours = getattr(mesh.visual, "vertex_colors", None)
    if ref_mean is not None and colours is not None and len(colours):
        c = colours[:, :3].astype(np.float32)
        gain = np.clip(ref_mean / np.maximum(c.mean(0), 1.0), 0.7, 2.5)
        colours[:, :3] = np.clip(c * gain, 0, 255).astype(np.uint8)
        mesh.visual.vertex_colors = colours
        gain_note = f", colour matched to the picture ×{gain.mean():.2f}"
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))   # Z-up → Y-up
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))    # face the viewer (+Z)
    tmp = args.out + ".part.glb"
    mesh.export(tmp)
    os.replace(tmp, args.out)   # the file appears whole or not at all
    print(f"MESHGATE_TRIPOSR {len(mesh.faces):,} triangles on {device} ({mc}); background {t1 - t0:.0f} s, "
          f"model + surface {t2 - t1:.0f} s{gain_note}")


if __name__ == "__main__":
    main()
    # PyTorch on MPS can abort while the interpreter tears down (libc++ "recursive_mutex lock failed") after the mesh
    # is already written. Nothing is left to clean up, so leave without the teardown.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
