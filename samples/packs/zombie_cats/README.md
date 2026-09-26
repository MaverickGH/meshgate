**English** · [Русский](README.ru.md)

# Example pack: Zombie Cats

A cute-apocalypse location kit — 11 assets and a diorama — built entirely by one Blender script and pushed through the whole MeshGate pipeline: in-Blender contract check, export with engine variants, validator, web viewer, Unity, Godot and Unreal. It is both a showcase and a test: `python3 meshgate.py check blender` regenerates it on every Blender version and the Unity and Godot tests load every asset against this `index.json`.

![Zombie Cats in Unity: diorama, runtime zombie cat, FBX Humanoid cat, and the hero playing the cat's shamble](../../../docs/img/pack-zombie-cats-unity.png)

## How it is built (the way real stylized packs are made)

- **One palette texture** (`zc_palette`, 256², 29 colour cells) and **one PBR material** (`zc_atlas`) for the whole pack; each face samples a flat colour cell with nearest filtering. Glowing parts use `zc_glow` / `zc_lamp`. A prop is one mesh with one or two materials — one or two draw calls.
- Every prop stands on its origin at ground level, in meters, with ASCII names.
- Static props carry **collision proxies**: `<name>.unreal.fbx` has `UCX_` convex meshes, `<name>.godot.glb` has `-convcolonly` nodes (Godot turns them into StaticBody3D on import).
- **`zc_zombie_cat`** is a biped on the **Unity Humanoid** skeleton plus three tail bones, rigid head, weights by nearest bone, clips `idle` and `shamble`. Its FBX imports into Unity as a valid Humanoid avatar, so the shamble retargets onto any other humanoid (see the hero in the picture).
- **`zc_diorama`** is an 8 × 8 m street made of linked duplicates — instanced tiles and fences, three shambling cats, lamps, graves, a toxic can.

## Assets

| File | Asset | Tris | Size, m (X×Y×Z, Y up) | Clips | Bones | Engine variants |
|---|---|---|---|---|---|---|
| `zc_ground_tile.glb` | Ground tile (paw prints) | 606 | 2.00×0.04×2.00 | — | — | — |
| `zc_road_tile.glb` | Road tile (fish marks) | 308 | 2.00×0.10×2.00 | — | — | — |
| `zc_fence_broken.glb` | Broken fence (cat-ear pickets) | 1,188 | 2.00×1.10×0.77 | — | — | zc_fence_broken.unreal.fbx, zc_fence_broken.godot.glb |
| `zc_tombstone_cat.glb` | Cat tombstone | 768 | 0.70×1.08×0.40 | — | — | zc_tombstone_cat.unreal.fbx, zc_tombstone_cat.godot.glb |
| `zc_dead_tree.glb` | Dead tree + yarn | 304 | 1.28×2.47×1.15 | yarn_swing | — | zc_dead_tree.unreal.fbx, zc_dead_tree.godot.glb |
| `zc_cardboard_barricade.glb` | Box barricade (hiding cat) | 772 | 1.82×1.23×0.69 | — | — | zc_cardboard_barricade.unreal.fbx, zc_cardboard_barricade.godot.glb |
| `zc_toxic_can.glb` | Toxic cat food can | 1,132 | 0.99×1.01×0.73 | bubbles | — | zc_toxic_can.unreal.fbx, zc_toxic_can.godot.glb |
| `zc_street_lamp.glb` | Fish street lamp | 780 | 1.27×3.17×0.36 | swing | — | zc_street_lamp.unreal.fbx, zc_street_lamp.godot.glb |
| `zc_bones_pile.glb` | Fish bones | 282 | 0.66×0.07×0.47 | — | — | — |
| `zc_scratch_post_ruin.glb` | Ruined scratching post | 1,320 | 1.09×1.15×0.80 | — | — | zc_scratch_post_ruin.unreal.fbx, zc_scratch_post_ruin.godot.glb |
| `zc_zombie_cat.glb` | Zombie cat (Humanoid, idle/shamble) | 4,520 | 0.81×1.05×0.48 | idle, shamble | 24 | — |
| `zc_diorama.glb` | Diorama: zombie cat street | 21,020 | 8.60×3.20×9.19 | bubbles, idle, shamble, swing, yarn_swing | 72 | — |

Every asset also has `<name>.fbx` (except the diorama). All files satisfy the contract with `--strict`.

## Rebuild

```bash
blender -b -P sources/blender/make_pack_zombie_cats.py -- --out-dir samples/packs/zombie_cats
python3 meshgate.py samples            # rebuilds this pack together with the other samples
```

Or open `zombie_cats.blend` in Blender with the MeshGate add-on: each asset is a collection; select one and press **Export**.

## Use it

- **Web:** `python3 meshgate.py serve` → the gallery has a "Zombie Cats pack" group.
- **Unity:** `MeshGateSampleTools.BuildAll` copies the pack and builds `Assets/MeshGate/ZombieCatsDemo.unity`; `MeshGateAsset` with `playOnLoad = "shamble"` makes a cat walk at runtime.
- **Godot:** `targets/godot/sync_samples.sh`, then open `demo_pack.tscn` (the diorama with `play_on_load = "shamble"` and the collision fence).
- **Unreal:** `meshgate_import.import_pack("/path/samples/packs/zombie_cats")` — `.unreal.fbx` with UCX for static props, GLB otherwise, the cat as a Skeletal Mesh.

![Zombie Cats in Godot 4 with the shamble clip playing](../../../docs/img/pack-zombie-cats-godot.png)
