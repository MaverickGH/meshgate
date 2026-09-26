**English** · [Русский](README.ru.md)

# Target: Unity

The canonical GLB is loaded into Unity via **Unity glTFast** (`com.unity.cloud.gltfast`, Apache-2.0) — the official fork of glTFast, installed from the Unity registry. On top of it sit our UPM package and a sample project.

```
targets/unity/
├── com.meshgate.unity/     UPM package: MeshGateAsset, MeshGateInteraction, MeshGateOrbitCamera, validation menu
└── MeshGateSample/         Unity project (6000.0): demo scene, PlayMode tests, headless build
```

Requirements: Unity **6000.0+** (glTFast 6.20 requires Unity 6). Tested on 6000.0.80f1, Built-in RP; for URP/HDRP glTFast picks the shaders itself.

![Demo scene in Unity: FBX on the left, glTF editor import in the center, runtime loading with the lid open on the right](../../docs/img/unity-demo.png)

## Quick start

**In your own project.** Package Manager → Add package from git URL:

```
https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity
```

Put `meshgate_demo.glb` into `Assets/StreamingAssets/`, add `MeshGateAsset` to an empty object (source = `meshgate_demo.glb`), and add `MeshGateOrbitCamera` to the camera with this asset in the target field. Press Play — the asset loads, the camera frames it by itself, and both animations start playing. `MeshGateInteraction` next to `MeshGateAsset` adds hover/click on nodes.

**Sample project.** Open `targets/unity/MeshGateSample` in Unity Hub (6000.0.x). The menu **MeshGate → Sample → Build Demo Scene** (in any project with the package: **MeshGate → Build Demo Scene (from repo samples)**) copies the examples from `samples/` into the project and builds `Assets/MeshGate/MeshGateDemo.unity`: on the left — FBX (native Unity import), in the center — GLB imported by the editor (glTFast ScriptedImporter), on the right — the same GLB loaded at runtime with animations, colliders and a HUD.

## Headless check (without opening the editor)

```bash
U=/Applications/Unity/Hub/Editor/6000.0.80f1/Unity.app/Contents/MacOS/Unity   # macOS; on Linux — the path to your Unity
P=targets/unity/MeshGateSample

# 1. Copy the demo GLB and FBX, import them with the editor, build the scene, run the validator, cross-check FBX against GLB
$U -batchmode -nographics -projectPath $P -executeMethod MeshGateSampleTools.BuildAll -quit -logFile -

# 2. PlayMode tests: runtime loading per the contract (hierarchy, names, scale 1, meters/Y-up, clips, the lid opens)
$U -batchmode -nographics -projectPath $P -runTests -testPlatform PlayMode -testResults $P/TestResults/playmode.xml -logFile -

# 3. Snapshot of the demo scene to PNG (needs graphics — no -nographics)
$U -batchmode -projectPath $P -runTests -testPlatform PlayMode -testFilter MeshGateSceneRenderTest -logFile -
open $P/TestResults/meshgate_unity.png
```

The first run resolves packages from the Unity registry (about a minute). The unit tests live in `Assets/Tests/PlayMode/`: they are also the specification of what "the GLB landed in Unity per the contract" means.

## What the package provides

| Component | What it does |
|---|---|
| `MeshGateAsset` | Runtime loading of `.glb` (StreamingAssets / absolute path / http): hierarchy with names from glTF, `Find("crate_lid")`, `Bounds` in meters, mesh/tris/material counters, animations by name (`Play`, `Solo`, `Stop`, `SetSpeed`), Box / Mesh / MeshConvex colliders, `onLoaded` / `onFailed` events. |
| `MeshGateInteraction` | Hover and click on nodes with highlighting — like in the web viewer; `onHoverEnter` / `onHoverExit` / `onClick` events. |
| `MeshGateOrbitCamera` | Orbit camera: LMB — orbit, RMB — pan, wheel — zoom, `F` — frame; frames the asset by itself after loading. |
| `MeshGateQuality` | Quality tiers (mobile-low … pc): render settings for the tier and `<name>.<tier>.glb` picked by every `MeshGateAsset`. |
| `MeshGateTierShowcase` | Every asset of a pack at every tier side by side with its triangle count — the sample scene `GeneratedTiers.unity` uses it on the generated pack. |
| Menu **MeshGate → Validate Selected GLB** | Runs `core/validate_glb.py` from the repository and shows the report. |
| Menu **MeshGate → Set Up Humanoid (Selected FBX)** | Extracts the textures of a MeshGate character FBX and sets its avatar to Humanoid, so clips retarget between characters. |

API details — in [com.meshgate.unity/README.md](com.meshgate.unity/README.md).

## FBX — the fallback path for the editor

The same export can output an FBX next to the GLB: `--fbx` in `export_meshgate.py`. Settings for Unity/Unreal: meters (`UnitScaleFactor = 100` → File Scale 1, object scale 1), `-Z forward / Y up`, face smoothing, tangents, each NLA strip is a separate take, textures embedded. Validation — `core/validate_fbx.py`.

| | GLB (canon) | FBX (fallback) |
|---|---|---|
| Editor import | glTFast ScriptedImporter | native Unity, no packages |
| Runtime loading | yes (`MeshGateAsset`) | no — the FBX SDK is editor-only |
| Materials | PBR as is (metallic/roughness maps, emission, transparency) | Phong → our `MeshGateFbxMaterials` postprocessor converts to Standard/URP Lit: albedo, normal, emission, metallic (ReflectionFactor), smoothness (√(ShininessExponent/100)); the roughness map and transparency are **lost** |
| Animations | Legacy clips by name / Mecanim | Mecanim (Generic/Humanoid) — the native path for rigs |
| Web / Godot | the same file | no |

Unity keeps textures embedded in an FBX "inside" and does not assign them to materials until they are extracted (the **Extract Textures** button in the importer or `ModelImporter.ExtractTextures`) — `BuildAll` does this itself. `BuildAll` also cross-checks the FBX against the GLB: identical hierarchy, extents, scale 1 and clips — otherwise the build fails.

Rule: **FBX for the editor and rigs, GLB for runtime/web/PBR.** Both come out of the same `.blend` with a single command.

## What is visible without Play, and what only in Play

| Object in the scene | How it is loaded | Visible in the editor |
|---|---|---|
| `MeshGate Asset (FBX import)`, `MeshGate Prop FBX (…)`, `MeshGate Hero (FBX Humanoid)` | native FBX import by the editor | yes |
| `MeshGate Asset (editor import)` | GLB via glTFast ScriptedImporter | yes |
| `MeshGate Asset (runtime)`, `MeshGate Hero (runtime)` | `MeshGateAsset` from StreamingAssets | **only in Play** — in the editor it is an empty node |

That is why the row of props (lantern, barrel, drone) is placed as FBX imports (each inside an empty parent: Blender FBX bakes keys onto the root object as well, and the Animator would overwrite the root position in Play), while runtime loading is shown by the crate and the hero; the same prop GLBs are checked in the PlayMode tests.

## Characters: Humanoid and retargeting

The demo scene places `meshgate_hero` behind the crates: on the left an FBX that `BuildAll` switches to **Mecanim Humanoid** (`animationType = Human`, avatar from the model — the bones are named per Unity Humanoid, so the mapping is automatic; `Verify` fails if the avatar is invalid or fewer than 15 bones are mapped), on the right the same GLB at runtime via glTFast (skin, 21 bones, Legacy clips `idle`/`wave`). The Humanoid `wave` clip from the FBX works on any other Humanoid avatar — this is how it animates a realistic avatar in `My project` (Mecanim retargeting).

Your own character: run it through `sources/blender/animate_humanoid.py` (see `samples/README.md`) — it finds Mixamo/Rigify/UE bones and outputs a GLB + FBX per the contract.

## Tiers and LODs

![The camera pulls back and a Unity LOD Group switches the realistic toxic can from LOD0 (12,040 triangles) to LOD2 (889)](../../docs/img/unity-lods.gif)

Two ways to keep a scene light. At runtime a scene-wide **MeshGateQuality** makes every `MeshGateAsset` load
`<name>.<tier>.glb` for the chosen tier. In the editor `<name>.unity.fbx` carries `_LOD0…_LODn` meshes, and Unity builds
a LOD Group that swaps them by distance, as above.

![The Zombie Cats street in Unity at mobile-low (left) and PC (right): no shadows and a lower resolution against soft shadows](../../docs/img/tiers-unity-low-pc.png)

## Contract → Unity: what to know

- **Meters and Y-up** match Unity. glTF is right-handed, Unity is left-handed — glTFast mirrors along X; names, hierarchy and scale 1 are preserved (a test checks `localScale == 1` on all nodes).
- **Origin at the base** → `Bounds.min.y == 0`: the asset can be placed on the floor without adjustment.
- **PBR** → glTFast shaders (`glTF/PbrMetallicRoughness` or URP/HDRP variants). Emission with `KHR_materials_emissive_strength` and transparency (`BLEND`) carry over.
- **Animations** → Legacy `Animation`, clip = glTF animation name; each clip on its own layer so they can play simultaneously. For Mecanim — `ImportSettings.AnimationMethod = Mecanim` and your own controller.
- **Draco / KTX2 / meshopt** — require the packages `com.unity.cloud.draco`, `com.unity.cloud.ktx`, `com.unity.meshopt.decompress`; without them, load `meshgate_demo.glb`, not `.draco.glb`.
- Editor import (`.glb` in `Assets/`) — the same glTFast: you get a prefab asset with the same hierarchy and clips as sub-assets.

Limitations: `MeshGateInteraction` and `MeshGateOrbitCamera` use the old Input Manager (`ENABLE_LEGACY_INPUT_MANAGER`); when only the new Input System is active they stay silent — hook your own input to their public methods.
