**English** · [Русский](README.ru.md)

# Example pack: Generated

Eight assets made by [`meshgate.py gen`](../../../docs/generation.md). They go through the same engine checks as the
hand-built samples, so every change to generation is tested in the web viewer, Unity, Godot and Unreal.

| Asset | Made with | Triangles, mobile-low → PC |
|---|---|---|
| `gen_windmill` | Kit code an AI wrote from a Russian description, looping `spin` clip | 1,444 → 21,620 |
| `gen_street_lamp` | Kit code an AI wrote from an English description | 1,394 → 31,214 |
| `gen_fire_hydrant` | Hand-written kit example, convex collision | 470 → 2,358 |
| `gen_treasure_chest` | Hand-written kit example, opening lid, box collision | 196 → 1,324 |
| `gen_toxic_can` | Kit code an AI wrote looking at a picture of the Zombie Cats can | 1,496 → 24,416 |
| `gen_hydrant_photo` | TripoSR mesh from a picture, refined per tier | 4,000 → 62,500 |
| `gen_toxic_can_vertex` | The toxic can's kit code with `--colors vertex`: no textures | 1,496 → 24,416 |
| `gen_hydrant_lowpoly` | The TripoSR hydrant with `--tris low=300,mid=800,high=1500,pc=3000 --colors vertex` | 300 → 3,000 |

Each asset has `<name>.glb` (PC) and `<name>.mobile-low/mid/high.glb`; assets with collision also have
`.godot.glb` and, for kit code, `.unreal.fbx`. `index.json` lists them in the same shape as the Zombie Cats pack.

![Every generated asset at every tier in Unity](../../../docs/img/unity-generated-tiers.png)

## What is checked

- **Web:** the viewer's gallery lists the pack from `samples/index.json`.
- **Unity:** `GeneratedPackLoadsEveryTier` loads every canonical file with its clips, height and ground contact, and
  every tier file within its triangle budget.
- **Godot:** `tests/test_meshgate.gd` runs the pack check on every synced pack, tier files included.
- **Unreal:** `tests/unreal/test_pack_import.py` checks that the importer picks an existing file for every asset and
  tier.

## Rebuild

```bash
python3 sources/generate/make_generated_pack.py                  # from the committed code and TripoSR output
python3 sources/generate/make_generated_pack.py --live-triposr   # regenerate the TripoSR mesh first
```

The inputs live in [`sources/generate/examples`](../../../sources/generate/examples): the build code, the two
pictures and the raw TripoSR output, so the pack rebuilds on a machine without TripoSR.
