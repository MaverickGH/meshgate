**English** · [Русский](README.ru.md)

# com.meshgate.unity

UPM package: loading the MeshGate canonical GLB into Unity on top of [Unity glTFast](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@latest) (Apache-2.0).

## Installation

Package Manager → **Add package from git URL**:

```
https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity
```

or locally in `Packages/manifest.json`: `"com.meshgate.unity": "file:../../com.meshgate.unity"`. The `com.unity.cloud.gltfast` dependency is pulled in automatically from the Unity registry.

## Components

| Component | What it does |
|---|---|
| `MeshGateAsset` | Loads `.glb` (StreamingAssets / absolute path / http) at runtime: hierarchy with names from glTF, `Find("crate_lid")`, animations by name (`Play`, `Solo`, `Stop`, `SetSpeed`), `Bounds`, mesh/tris/material counters, colliders (Box / Mesh / MeshConvex), `onLoaded` / `onFailed` events. |
| `MeshGateInteraction` | Hover and click on nodes with highlighting and UnityEvents — like in the web viewer. |
| `MeshGateOrbitCamera` | Orbit camera: LMB — orbit, RMB — pan, wheel — zoom, `F` — frame; frames the asset by itself after loading. |
| Menu **MeshGate → Validate Selected GLB** | Runs `core/validate_glb.py` from the repository and shows the report. |
| `MeshGateFbxMaterials` (AssetPostprocessor) | For FBX from Blender (`--fbx`): maps the Phong description onto Standard/URP Lit slots — albedo, normal, emission, metallic, smoothness; finds textures among the extracted ones. Triggers on FBX files with "meshgate" in the name, or on all of them when `MeshGateFbxMaterials.applyToAll = true`. |

```csharp
var asset = gameObject.AddComponent<MeshGateAsset>();
asset.source = "meshgate_demo.glb";           // Assets/StreamingAssets/meshgate_demo.glb
asset.colliders = MeshGateColliders.Mesh;
asset.onLoaded.AddListener(a => {
    Debug.Log($"{a.MeshCount} meshes, {a.TriangleCount} tris, extents {a.Bounds.size}");
    a.Solo("lid_open");                       // only one clip
    a.Find("beacon_ring").gameObject.SetActive(false);
});
```

Editor import (drag a `.glb` into `Assets/`) is handled by glTFast itself — you get a prefab-like asset with the same hierarchy and Legacy clips.

## Contract → Unity

- glTF meters and Y-up match Unity; glTFast converts the right-handed system to left-handed (mirrors X), names and hierarchy are preserved.
- PBR `metallicRoughness` → glTFast shaders for Built-in / URP / HDRP (chosen based on the active pipeline).
- Draco / KTX2 / meshopt — require the additional packages `com.unity.cloud.draco`, `com.unity.cloud.ktx`, `com.unity.meshopt.decompress`; without them, load the uncompressed variant.
- Animations — Legacy `Animation` (clip = glTF animation name). For Mecanim, set `ImportSettings.AnimationMethod = Mecanim` and use your own controller.

Limitations: Legacy animations do not work with Timeline; `MeshGateInteraction`/`MeshGateOrbitCamera` use the old Input Manager (`ENABLE_LEGACY_INPUT_MANAGER`).
