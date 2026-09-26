**English** · [Русский](README.ru.md)

# Target: Godot 4

glTF is Godot's native format: a `.glb` in `res://` is imported as a scene without plugins. On top of that — our addon with the same API as web and Unity, and a demo project with a headless check.

```
targets/godot/
├── MeshGateDemo/               Godot 4.4+ project (tested on 4.7.2, Forward+)
│   ├── addons/meshgate/        addon: MeshGateAsset, MeshGateOrbitCamera, MeshGateInteraction, MeshGateHud
│   ├── demo.tscn / demo.gd     demo scene: all samples from samples/ at runtime, lights, floor, orbit, HUD
│   ├── tests/test_meshgate.gd  headless contract check for each GLB
│   └── tests/screenshot.gd     scene snapshot to PNG
└── sync_samples.sh             copies the repository's samples/*.glb into res://samples/
```

![Demo scene in Godot: crate, hero, lantern, barrel, drone](../../docs/img/godot-demo.png)

## Quick start

```bash
targets/godot/sync_samples.sh                                   # samples/*.glb → MeshGateDemo/samples/
/Applications/Godot.app/Contents/MacOS/Godot --path targets/godot/MeshGateDemo   # run the demo (or open it in the editor)
```

In your own project: copy `addons/meshgate/` into `res://addons/`, enable the plugin in Project → Plugins, add a **MeshGateAsset** node, set `source` (`res://`, `user://` or an absolute path), and attach **MeshGateOrbitCamera** to the camera with this asset in `target`.

```gdscript
var a := MeshGateAsset.new()
a.source = "res://samples/meshgate_demo.glb"
a.colliders = MeshGateAsset.Colliders.CONVEX
a.loaded.connect(func(asset): asset.solo("lid_open"); print(asset.find("beacon_ring")))
add_child(a)
```

## Headless check

```bash
G=/Applications/Godot.app/Contents/MacOS/Godot
$G --headless --path targets/godot/MeshGateDemo --import                  # first time: import the project
$G --headless --path targets/godot/MeshGateDemo -s tests/test_meshgate.gd # contract: names, hierarchy, extents, clips, bones, collisions
$G --path targets/godot/MeshGateDemo -s tests/screenshot.gd               # snapshot → TestResults/meshgate_godot.png (needs a window)
```

The check fails if the crate has the wrong nodes/extents/clips or the lid does not open, if the hero does not have 21 Unity Humanoid bones or `wave` does not raise the arm, or if the props have the wrong nodes and animations.

## What the addon provides

| Node | What it does |
|---|---|
| `MeshGateAsset` (Node3D) | Runtime loading via `GLTFDocument`: hierarchy with names from glTF, `find("crate_lid")`, `bounds` (AABB in meters), mesh/tris/material/bone counters, animations by name (`play`, `solo`, `stop`, `set_speed`) via a generated `AnimationPlayer`, BOX / CONVEX / TRIMESH collisions, `loaded` / `failed` signals. |
| `MeshGateInteraction` (Node) | Hover and click on nodes via raycast with `material_overlay` highlighting; `hover_entered` / `hover_exited` / `clicked` signals. |
| `MeshGateOrbitCamera` (Camera3D) | LMB — orbit, RMB — pan, wheel — zoom, `F` — frame; frames the asset by itself after loading. |
| `MeshGateHud` (CanvasLayer) | Asset passport, name under the cursor, `Space` — pause, `1..9` — clip selection. |

## Contract → Godot

- Meters and Y-up match, and Godot's forward is -Z like glTF's — nothing gets rotated or scaled.
- Node names are preserved (Godot only replaces `.`, `:`, `/`, `@`, which the contract disallows anyway).
- Animations → `AnimationPlayer` with tracks by glTF names, skins → `Skeleton3D` with bones by name.
- PBR → `StandardMaterial3D`; Godot reads `KHR_materials_transmission`/`ior`/`emissive_strength`.
- Draco: Godot 4 has no decoder out of the box — load the uncompressed `.glb`.
- FBX: Godot 4 imports it via the built-in ufbx, but glTF is preferable for the editor too.
