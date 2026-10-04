**English** · [Русский](quality-tiers.ru.md)

# Quality tiers: mobile low / mid / high and PC

One asset pipeline, four device tiers. [`core/profiles.json`](../core/profiles.json) is the single source of truth; the validator, the Blender add-on, the web viewer, Unity, Godot and Unreal all read or mirror it, and `python3 tests/check_profiles.py` fails if any copy drifts.

![The same zombie cat at every tier: the wireframe thins from 52,026 triangles on PC to 1,288 on mobile low](img/quality-tiers.gif)

| Tier | Devices | Asset budget (per file) | Scene budget | Rendering |
|---|---|---|---|---|
| `mobile-low` | budget/old phones, ≤ 3 GB RAM | 8k tris, 512 px, 4 MB textures, 2 materials, 50 bones, 2 influences, 2 MB | 60k tris, 60 draw calls | 0.75× resolution, no shadows, no MSAA, no post |
| `mobile-mid` | mainstream phones, 4–6 GB | 25k tris, 1024 px, 12 MB, 4 materials, 75 bones, 4 influences, 6 MB | 150k, 150 | 0.9×, hard shadows 1024, MSAA 2× |
| `mobile-high` | flagships, tablets, ≥ 8 GB | 60k tris, 2048 px, 32 MB, 8 materials, 150 bones, 12 MB | 300k, 300 | full res, soft shadows 2048, MSAA 4×, bloom |
| `pc` | desktops and laptops | 250k tris, 4096 px, 128 MB, 16 materials, 256 bones, 25 MB | 2M, 2000 | full res, soft shadows 4096, MSAA 4×, AO, bloom, HDR |

## Budgets are targets, not only ceilings

- **Build to the tier.** A generator should spend the budget: the Zombie Cats pack builds the same props with fewer segments for `mobile-low` and with more segments, smoothing and bevels for `pc` (`make_pack_zombie_cats.py --detail/--tiers`) — the zombie cat is 1k tris on mobile-low and 52k on PC, the whole street 7k and 172k. This keeps shapes clean instead of decimating one model.
- **Or reduce automatically.** The Blender add-on (**Quality tiers: Low / Mid / High**) and `export_meshgate.py --profiles mobile-low,mobile-mid,mobile-high` write `<name>.<tier>.glb` from any scene: DECIMATE until the triangle budget holds (before the armature, so skins still work), textures downscaled, influences limited, JPEG where there is no alpha. The source scene is never modified.
- **The canonical `<name>.glb` is the PC version** — full quality, the contract's reference.
- **Check.** `python3 core/validate_glb.py asset.glb --profile all` prints every budget line and the tiers the file `fits`; `--scene` uses the scene budget. Exceeding a budget is a warning (`--strict` makes it fail).
- **Future generation (text/image → 3D)** gets the tier as its target polycount and texture size, then the same check.

## At runtime

| Target | Tier selection | What it changes | Variant files |
|---|---|---|---|
| Web (`meshgate-viewer.js`) | `quality: "auto"` (desktop → pc; phones by memory, cores, GPU name) or `?quality=mobile-low`; `setQuality()` | pixel ratio × render scale, shadows type/size, MSAA; PC adds GTAO + HDR bloom (threshold 1.0: only emissive parts glow) | `load("x.glb")` fetches `x.<tier>.glb` when it exists |
| Unity (`MeshGateQuality`) | component or `MeshGateQuality.Apply(tier)`; `Auto` detects handheld vs desktop | QualitySettings (MSAA, shadows, distance, LOD bias, mip limit, anisotropy, 2/4 bone skinning); URP render scale/MSAA/HDR on a runtime copy of the pipeline asset | `MeshGateAsset.useQualityVariant` → `LoadedFile` |
| Godot (`MeshGateQuality`) | node or `MeshGateQuality.apply(tier, viewport)` | MSAA, 3D scaling, mesh LOD threshold, shadow atlas + soft filter, lights, SSAO, glow | `MeshGateAsset.use_quality_variant` → `loaded_file` |
| Unreal | `meshgate_import.apply_quality(tier)` | `sg.*` scalability 0–3, screen percentage, shadow, AO, bloom, MSAA console variables | `import_pack(folder, profile=tier)` |

The test projects ship **three scenes of the same street** — `ZombieCats_Low/_Mid/_PC.unity` in Unity and `demo_pack_low/_mid/_pc.tscn` in Godot — each with its tier's files and settings. The Unity and Godot tests check that `mobile-low` picks the variant within budget and that PC loads the detailed canonical file.

![Godot: Zombie Cats street at mobile-low (left) and PC (right)](img/tiers-godot-low-pc.png)
