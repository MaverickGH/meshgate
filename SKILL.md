---
name: meshgate
description: Take a 3D asset (a .blend, a GLB/FBX, or a rigged humanoid) to an engine-ready, validated glTF and deliver it to the web (Three.js), Unity, Godot or Unreal. Use when the user wants to export a Blender model for a game engine or website, check a GLB/FBX for scale/axes/UV/PBR/naming/rig problems, bring a character to a Unity-Humanoid skeleton, or load an asset into Unity/Godot/Unreal/web with names, animations and colliders intact.
---

**English** · [Русский](SKILL.ru.md)

# MeshGate — asset gateway skill

You turn one input asset into a canonical GLB that follows the **asset contract** (`docs/asset-contract.md`) and put it into the requested runtime. Everything goes through `meshgate.py` in the repository root; do not hand-roll exporter flags or engine import settings.

Hub and spokes: sources (Blender today, Maya next) → **canonical GLB + validator** → targets (web, Unity, Godot, Unreal). FBX is a fallback beside the GLB for engine editors and rigs, never instead of it.

## 0. Before you start

```bash
python3 meshgate.py doctor
```

Note which tools exist. Blender is required for export; Unity 6000.0+, Godot 4.4+ are needed only for the matching engine checks. If a tool is missing, say so and continue with what is possible — never claim an engine check you could not run. Unreal needs no install for its check: `meshgate.py check unreal` verifies the plugin against the UE 5.4–5.6 Python API; a live editor run has not happened yet.

Ask the user only what changes the work: which **targets** (default: web + whatever engine they mention) and, for characters, whether they need **Humanoid retargeting** (Unity Mecanim / UE Mannequin).

## 1. Classify the input

| Input | Path |
|---|---|
| `.blend` with a prop/scene | §2 → §3 |
| GLB/glTF from elsewhere | skip to §3 (validate), fix in Blender only if the validator complains |
| FBX from elsewhere | import into Blender, save `.blend`, then §2 → §3 |
| Rigged humanoid (Avaturn, Mixamo, Rigify, UE, VRoid…) | `python3 meshgate.py character in.glb --out out.glb` → §3 |
| Text prompt (a prop, a machine, a building part) | `python3 meshgate.py gen "<description>" [--size M] [--style …]` asks the user's AI CLI and delivers one validated file per tier. You are an AI yourself: you may instead write `build(mg)` against the kit (`python3 meshgate.py gen "<description>" --prompt-only` prints the API and rules) and run it with `gen --code file.py --name N`. Read the report and fix what it lists. See `docs/generation.md` |
| Picture of an object | `python3 meshgate.py gen --image pic.png [--size M]`: a neural mesh (TripoSR locally after `gen --setup triposr`, or Meshy/Tripo/fal with the user's key) refined per tier. For stylized props add `--engine kit` and write the build code yourself looking at the picture |
| A mesh from elsewhere (Sketchfab, a generator website) | `python3 meshgate.py gen --mesh file.glb --size M`: normalise, stand upright, decimate per tier, unwrap, bake |
| A character from text or a picture | not supported yet (roadmap v0.6.2). Say so; offer a parametric human (MakeHuman/MPFB) or an external generator, then `meshgate.py character` on the result |

Keep third-party assets out of git: put them in `samples/_local/` (ignored).

## 2. Prepare in Blender (only what the contract needs)

If the user works in Blender's UI, the MeshGate add-on (N → MeshGate, `sources/blender/README.md`) does all of this with Check / Fix / Export — install it for them with `python3 meshgate.py install-blender` (ask them to close Blender first). Headless, the same rules and fixes run with `export_meshgate.py --check --fix`.


Check and fix in the source scene, via a small Blender Python script run with `-b file.blend -P fix.py` — not by hand-editing exported files:

- **Meters, 1 unit = 1 m.** Real-world sizes: a crate is ~0.8 m, a human ~1.75 m.
- **Applied scale.** Object scale 1 on meshes (the exporter applies it automatically unless scale is animated).
- **Meaningful origin.** Floor props: origin at the base (min Y = 0 after export). Hinged/rotating parts: origin at the pivot (lid on its hinge, rotor at its hub).
- **Names.** ASCII, no spaces (`crate_lid`, `body_metal`). Code addresses nodes by name in every engine.
- **PBR only.** Principled BSDF with image textures or constants. Procedural node trees must be baked to textures first.
- **UVs on every mesh** that has a texture or will be lightmapped.
- **Animations as NLA strips**, one strip per clip, named (`idle`, `lid_open`). Loose actions still export, but NLA keeps GLB and FBX clip names identical.
- **Helpers hidden from render** (boolean cutters, guides): `hide_render = True` — the exporter skips them.
- **Characters:** bone names follow Unity Humanoid (`Hips, Spine, Chest, Neck, Head, Left/RightShoulder, Left/RightUpperArm, Left/RightLowerArm, Left/RightHand, Left/RightUpperLeg, Left/RightLowerLeg, Left/RightFoot, Left/RightToes`), rest pose is a T-pose, ≤ 4 weights per vertex. `meshgate.py character` handles Mixamo/Rigify/UE names.

## 3. Export and validate

```bash
python3 meshgate.py export scene.blend --out build/asset.glb --fbx      # GLB + FBX, validator runs automatically
python3 meshgate.py validate build/asset.glb build/asset.fbx --strict  # re-check anytime; --json for machines
```

Add `--draco` only for web-only delivery (Godot and Unreal cannot decode it). The run is done when the validator exits 0 with `--strict`. Map every warning to a fix in the source and re-export:

| Validator says | Fix in Blender |
|---|---|
| dimensions < 1 cm / > 100 m | wrong units: scale the scene to meters, apply scale |
| bottom is below origin | move origin to the base (`origin_set` to a cursor at min Z) |
| scale ≠ 1 on meshes | apply scale (`transform_apply(scale=True)`), or un-animate scale |
| no UV (TEXCOORD_0) | unwrap (`uv.smart_project` / `cylinder_project`) |
| no normals / non-triangle primitives | triangulate on export (default), recompute normals |
| materials without PBR | rebuild with Principled BSDF, bake procedural nodes |
| texture not power of two / > 4096 | resize to 1024/2048 |
| external texture | pack images into the .blend (`image.pack()`) |
| node/material names with spaces or non-ASCII | rename |
| vertices without weights / sum ≠ 1 | normalize all weights, assign strays to the nearest bone |
| skeleton looks humanoid but bones are missing | rename to Unity Humanoid (see §2) or run `meshgate.py character` |
| unknown/required extension | disable that material feature or accept it only for targets that support it |

Then look at it:

```bash
python3 meshgate.py serve --glb build/asset.glb
```

In the viewer check the passport (dimensions, UV, bones), play each clip, press `S` for the skeleton and `U` for the UV checker. If you have a browser tool, take a screenshot and inspect it yourself rather than asking the user.

**Quality tiers.** Ask which devices matter. Export tier variants with `--profiles mobile-low,mobile-mid,mobile-high` (the canonical GLB is the PC version) and check with `validate_glb.py --profile all`; when you generate geometry yourself, build to the tier's budget instead of decimating (see `docs/quality-tiers.md`).

## 4. Deliver to the targets

**Web.** Embed `targets/web/meshgate-viewer.js` (`createViewer(el).load(url)`) — see `targets/web/README.md`.

**Unity 6.** Add the package `https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity` (or `file:` path). Then:
- Runtime: GLB into `Assets/StreamingAssets/`, a GameObject with `MeshGateAsset` (source = file name). It is **empty in edit mode** — it loads on Play.
- Editor: GLB or FBX into `Assets/` (glTFast imports GLB; Unity imports FBX natively). For FBX, extract textures (`ModelImporter.ExtractTextures`) or materials stay grey; `MeshGateFbxMaterials` maps Blender Phong → Standard/URP Lit.
- Characters: FBX → `animationType = Human`, avatar from model. Humanoid clips then retarget to any other Humanoid.
- Put FBX instances with animations **under an empty parent**: Blender FBX keys the root object and the Animator would reset its position.
- `MeshGate → Build Demo Scene` builds a reference scene from `samples/`.

**Godot 4.** Copy `targets/godot/MeshGateDemo/addons/meshgate` into the project, enable the plugin, add `MeshGateAsset` with `source`. Editor import of `.glb` is native. No Draco.

**Unreal 5.** Export with `--targets unreal` (plus collision proxies from the add-on's Add collision for `<name>.unreal.fbx` with `UCX_`). Copy `targets/unreal/MeshGate` into `Plugins/`, then `meshgate_import.import_samples(dir)` or `import_file(path, '/Game/...')`: GLB through Interchange with the MeshGate pipeline, FBX through Interchange (5.5+) or the legacy importer; characters as Skeletal Mesh, IK Retargeter to Mannequin (`meshgate_retarget.md`). Tell the user the plugin is API-checked but not yet run in a live editor.

## 5. Verify in the engines

```bash
python3 meshgate.py check web
python3 meshgate.py check unity            # BuildAll + PlayMode tests (add --render for a PNG of the scene)
python3 meshgate.py check godot            # headless contract test
python3 meshgate.py check all
```

These run against `samples/`. For a user's new asset, add it next to the samples (or to the test lists in `targets/unity/MeshGateSample/Assets/Tests` and `targets/godot/MeshGateDemo/tests/test_meshgate.gd`) with its expected node names, clips and dimensions — a check that does not name the asset proves nothing about it.

If the Unity project is open in an Editor, batch mode will refuse it; drive the open Editor through a Unity MCP bridge if one is connected, otherwise ask the user to close it.

## 6. Report

Tell the user, in this order: what now works and where (file paths, scene), the validator verdict, which engine checks ran and their results, and what could not be verified (missing tool, Unreal). Put numbers in a short table. Do not claim a target works without a check or a screenshot.

## Pitfalls we already hit

- Runtime-loaded objects are invisible until Play — use editor imports for anything the user must see in the scene view.
- Blender FBX: embedded textures point to a non-existent `*.fbm` folder; Unity needs them extracted; roughness maps and transparency are lost.
- A clip spanning several objects becomes one take per object in FBX (one clip in GLB).
- `SkinnedMeshRenderer.bounds` is a root-bone estimate; measure characters from the mesh bind pose.
- Draco works in Three.js, glTFast and (with packages) Unity only.
- Unity's fake-null: `GetComponent<T>() ?? AddComponent<T>()` is wrong; use `TryGetComponent`.
- Blender scripting: assigning `obj.parent` from Python resets `matrix_parent_inverse` — copy it back when duplicating hierarchies, or children jump.
- macOS has no `timeout`; background a long process and poll instead.
