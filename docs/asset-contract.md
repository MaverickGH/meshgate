**English** · [Русский](asset-contract.ru.md)

# MeshGate asset contract

A single set of rules under which one GLB opens predictably in the web and in all
engines. The validator (`core/validate_glb.py`) checks what is visible from the file;
the rest are conventions on the export side.

![The contract at a glance: meters, Y-up with the front along +Z, the origin at the bottom centre, scale 1, PBR, clean names, within the tier](img/asset-contract.svg)

## Geometry and transforms
- **Units are meters.** 1 glTF unit = 1 meter. In Blender the scene is in meters; in Maya, set the working units to meters before exporting.
- **Axes.** glTF is Y-up, right-handed. The Blender exporter converts from Z-up; in Maya (Y-up) no conversion is needed. The result is always Y-up.
- **Applied transforms.** Scale = 1, rotation = 0 on objects (apply transforms), otherwise unexpected rotations/scales pop up in the engine.
- **A meaningful origin.** The pivot is where the asset will be "attached" (the bottom for objects standing on the floor, the center for rotating ones).

## Materials
- **PBR only.** Principled BSDF (Blender) / Standard Surface → glTF `pbrMetallicRoughness`. Exotic nodes do not carry over — bake them into textures.
- **Textures** are packed into the GLB or placed next to it; sizes are powers of two (1024/2048), format WebP/PNG where possible.

## Naming
- Objects and materials — clear Latin names without spaces (`handle`, `body_metal`), because runtime code addresses them by these names.

## Optimization
- **Draco** for heavy geometry (compression by several times), if the target runtime supports it (Three.js, glTFast, Godot do; Unreal — to be verified).
- **Size limit** is 25 MB per asset by default — otherwise loading in the web is slow. Configurable with `--max-mb`.

## Rig and skin
- **Bones use Unity Humanoid names** (`Hips, Spine, Chest, Neck, Head, Left/RightShoulder, Left/RightUpperArm, Left/RightLowerArm, Left/RightHand, Left/RightUpperLeg, Left/RightLowerLeg, Left/RightFoot, Left/RightToes`). The validator also recognizes Mixamo, Rigify and UE names, but the canon is Unity: then the FBX imports as a Humanoid avatar without manual mapping, and clips retarget between characters.
- **T-pose** in the rest pose, up to 4 influences per vertex, normalized weights (sum of 1), the skin has `inverseBindMatrices`.
- **UVs on all vertices** of a skinned mesh — otherwise textures and baking in engines will not line up.

## Animations
- Skeletal/vertex animations are carried over via glTF. Complex rigs from Maya, if they break in glTF, go through the FBX/USD fallback path (see `architecture.md`).

## FBX as a fallback path
The same export (`--fbx`) produces an FBX for engine editors and rigs: meters (`UnitScaleFactor = 100`), `-Z forward / Y up`, scale 1, one take per NLA strip, embedded textures. From the contract, FBX does **not carry over**: metallic/roughness maps (only coefficients), transparency, `KHR_*` extensions. That is why FBX is not the canon but a companion to the GLB for editor import; runtime and web use GLB only. Validation — `core/validate_fbx.py` (units, axes, models, takes, embedded textures, scale).

## Collision and LODs (engine extras)
The canonical GLB contains only what renders. Collision proxies and LOD meshes live in the source scene as hidden-from-render meshes (the Blender add-on's **Add collision** / **Make LODs**) and go only into the engine variant that understands them:
- Unreal — `<name>.unreal.fbx` with `UCX_<Mesh>_NN` convex meshes, parented to their render mesh;
- Godot — `<name>.godot.glb` with `<mesh>…-convcolonly` nodes (Godot import hint → StaticBody3D + convex shape);
- Unity — `<name>.unity.fbx` with `<mesh>_LOD0.._LODn` siblings (Unity builds a LODGroup); Unreal and Godot generate LODs themselves.
A collision proxy should be convex (UE caps hulls; fewer faces is cheaper) and carry a UV map so validators stay quiet.

## Validation
A fresh import of the GLB back into the editor + `core/validate_glb.py` + a visual check in the `targets/web` viewer.

What exactly the validator checks (✗ — error, ⚠ — warning, `--strict` turns ⚠ into ✗):

| Rule | Check |
|---|---|
| Container | ✗ GLB signature/version, file length, JSON chunk; `asset.version == 2.0` |
| Scene | ✗ no scenes / no meshes; ⚠ no default scene set |
| Meters | ⚠ world extent < 1 cm (looks like mm) or > 100 m (looks like cm, or it is a scene) |
| Origin | a note if the bottom of the asset is noticeably below the origin |
| Transforms | ⚠ scale ≠ 1 on nodes with meshes; a note about nodes with `matrix` (not animatable) |
| Geometry | ⚠ no `TEXCOORD_0` (UV), no `NORMAL`, primitives are not triangles |
| Materials | ⚠ no materials; materials without `pbrMetallicRoughness` (and not unlit) |
| Rig | ⚠ skin without `inverseBindMatrices`, vertices without weights or with a sum ≠ 1, incomplete JOINTS/WEIGHTS; note: Humanoid compatibility (which bones were found/are missing) |
| Textures | ⚠ external files (not packed), not a power of two, larger than 4096 |
| Names | ⚠ nodes without a name; node/material names with spaces or non-Latin characters; animations without names |
| Extensions | ✗ a required extension outside the supported list; ⚠ an unknown one; per-target notes (Draco → not in Unreal Interchange, meshopt → web/Unity only) |
| Size | ⚠ larger than `--max-mb` (25 by default) |

What the validator **cannot** check (not visible from the file): Y-up and meters as such — only indirectly via extents; topology cleanliness; UV unwrap quality. That is the domain of the exporter and automatic refinement (roadmap v0.5).
