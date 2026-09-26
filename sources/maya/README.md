**English** · [Русский](README.ru.md)

# Source: Maya

Maya has no glTF export "out of the box", so three paths lead to the canonical GLB.
The goal is the same — get a GLB that follows the [asset contract](../../docs/asset-contract.md).

## Path A — glTF plugin (recommended for the web)
- **Maya2glTF** or **Babylon.js Exporter for Maya** (both open source). Installed as a Maya plugin, exports straight to GLB.
- Before exporting: working units — meters, delete history/freeze transforms, Standard Surface materials (carried over to PBR).

## Path B — via FBX (when rigs/animations in engines matter)
- Maya exports FBX natively (`File → Export`).
- FBX → GLB conversion: `FBX2glTF` (open-source CLI), or import the FBX into Blender and export with our `sources/blender/export_meshgate.py`.

## Path C — via USD (large scenes, studio pipeline)
- Maya writes USD natively (`mayaUsd`). USD is not suitable for the web; for Unreal/Unity — natively/via packages.

## Validation
Run any resulting GLB through `python3 core/validate_glb.py asset.glb`.

> Automation (a MEL/Python Maya→GLB export script per the contract) — on the roadmap for v0.3.
