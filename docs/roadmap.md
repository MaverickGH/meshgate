**English** · [Русский](roadmap.ru.md)

# MeshGate roadmap

## v0.1 — skeleton (done)
- [x] Core: asset contract + GLB validator (stdlib).
- [x] Blender source: export to GLB per the contract (headless).
- [x] Web target: Three.js viewer + local server.
- [x] Unity/Godot/Unreal/Maya starters + documentation.

## v0.2 — Web up to the reference level (done)
- [x] A real demo asset: a `.blend` generator (crate with a beacon), export to GLB and Draco-GLB, all in `samples/`.
- [x] Exporter: animations, apply scale, Draco level, texture format, `--validate` right after export.
- [x] Validator: world extents in meters, UVs/normals, unapplied transforms, power-of-two textures, names, per-target extensions, `--strict`/`--json`, CI.
- [x] Viewer library `meshgate-viewer.js`: hover/click/focus, animations with a timeline, RoomEnvironment/HDRI, shadows, Draco/KTX2/meshopt, drag-and-drop.
- [x] Demo page as a reference for the method: asset passport, object tree, animations, view, loading your own files.
- [ ] Deferred: a local copy of Three.js for offline use; a "before/after" Draco comparison in the UI.

## v0.3 — Unity (done)
- [x] UPM package `com.meshgate.unity` on top of Unity glTFast 6.20: `MeshGateAsset` (runtime loading, names, animations, colliders), `MeshGateInteraction`, `MeshGateOrbitCamera`, validation menu.
- [x] Sample project (Unity 6000.0): demo scene "editor import + runtime", HUD, headless `BuildAll` build.
- [x] PlayMode tests as the contract specification in Unity: hierarchy/names, scale 1, meters/Y-up, origin, clips, lid opening, render to PNG.
- [x] FBX as a fallback path: `--fbx` in the exporter (Unity/Unreal settings, take per strip, embedded textures), `core/validate_fbx.py`, the `MeshGateFbxMaterials` material postprocessor, FBX in the demo scene and FBX↔GLB cross-check in `BuildAll`.
- [x] Characters: demo humanoid `meshgate_hero` (Unity Humanoid skeleton, weights, UVs, `idle`/`wave`), `animate_humanoid.py` for third-party rigs (Mixamo/Rigify/UE), skin/weights/Humanoid validator, skeleton and UV checker in the viewer, Humanoid avatar and Mecanim retargeting in Unity, support for the new Input System, demo scene build as a package menu.
- [ ] Deferred: Draco/KTX2 via `com.unity.cloud.draco`/`ktx`; Unity CI (requires a license in GitHub Actions); roughness map for FBX (bake into the alpha of the metallic map).

## v0.4 — Godot and props (done)
- [x] Props: lantern (transmission/ior/emission, `swing`/`flicker`), barrel (normal and roughness maps), drone (hierarchy, `hover`/`rotors`); sample gallery in the viewer, props in the Unity scene and tests.
- [x] Godot 4: the `meshgate` addon (MeshGateAsset / OrbitCamera / Interaction / Hud), demo project, `tests/test_meshgate.gd` (headless, all 5 assets), `screenshot.gd`; screenshot `docs/img/godot-demo.png`.
- [x] LOD levels and collision proxies from the exporter (`_LODn` for Unity, `UCX_` for Unreal, `-convcolonly` for Godot) — in the v0.5 Blender add-on.
- [ ] Deferred: Draco in Godot via GDExtension.

## v0.4.1 — Unreal
- [x] Plugin rewritten for Interchange (MeshGate pipeline, UCX collision, bind pose, animations) with a legacy-FBX fallback; re-runnable demo level with lights; validator via the editor's Python.
- [x] `tests/unreal/check_api.py` — every Unreal name the plugin uses checked against the UE 5.4/5.5/5.6 Python API stubs, in CI.
- [ ] First live run in UE 5.5/5.6; C++ `MeshGateAsset` on glTFRuntime.

## v0.5 — Blender add-on for everyone (done)
- [x] Add-on (legacy 3.5–4.1 and extension 4.2+ from one zip): panel with targets, Check with a Fix per issue, Fix all, Export with the validator report, browser preview, collision proxies, LODs, Russian UI.
- [x] In-Blender contract rules with fixes: units, size, scale, names (transliteration), UVs, materials, textures (pack, power of two), ground, Humanoid bone renaming (Mixamo/UE/Rigify), weights, NLA.
- [x] One code path for panel and CLI (`export_meshgate.py --check --fix --targets`); `compat.py` for Blender 3.5 → 5.x API changes; demo generators run on 3.5, 4.2 LTS, 5.2 LTS.
- [x] `meshgate.py check blender`: plants every problem in a scene, checks Check/Fix/Export and the engine variants on every Blender found, regenerates the demo assets; CI runs it on Blender 4.2 LTS.

## v0.5.1 — Example pack "Zombie Cats" (done)
- [x] 11 stylized assets + diorama from one script: palette atlas material, collision variants, Humanoid zombie cat (idle/shamble), linked-duplicate diorama; identical output on Blender 3.5, 4.2 LTS and 5.2 LTS.
- [x] Checked end to end: add-on contract check + export, validator, web gallery group, Unity pack scene (+ Humanoid retarget of the cat's clip onto the hero), Godot pack test (incl. editor-imported `-convcolonly` collision), Unreal `import_pack` against the API stubs.
- [x] Found and fixed on the way: Blender resets `matrix_parent_inverse` when `.parent` is assigned (diorama children jumped); Godot variant missed proxies in selection exports; emission too strong after tone mapping.

## v0.5.2 — Quality tiers (done)
- [x] `core/profiles.json`: mobile-low / mobile-mid / mobile-high / pc — asset and scene budgets, render settings; `tests/check_profiles.py` keeps web/Unity/Godot/Unreal copies identical (CI).
- [x] Validator: draw calls, texture memory, bones per skin, influences per vertex; `--profile`, `--scene`, `fits`.
- [x] Blender: tier variants within budget (decimate before the armature, texture downscale, influences, JPEG), panel toggles, `--profiles`; pack generator builds each tier at its own detail (`--detail/--tiers`), canonical = PC.
- [x] Runtime: web auto-detection + `setQuality` + variant loading + PC post (GTAO, HDR bloom); Unity and Godot `MeshGateQuality` + variant pick; Unreal `apply_quality` + `import_pack(profile=)`.
- [x] Three scenes of the Zombie Cats street (Low / Mid / PC) in the Unity and Godot test projects, rendered in tests.

## v0.6 — Generation from text and MeshGate Studio (done)
- [x] `meshgate.py gen`: description → `build(mg)` code through any AI CLI (Claude Code, Codex, Gemini, Ollama, a custom command), guard rails, one Blender build per quality tier ("detail by necessity"), validation, a feedback loop — `docs/generation.md`.
- [x] Modeling kit `meshgate_blender/modeling.py`: primitives, lathe, tube, extrude, mirror, join, pivot, animate; one palette material (base colour + roughness/metallic + emission) per asset = one draw call on every tier.
- [x] MeshGate Studio: local server + UI (`meshgate.py studio`) and a Tauri desktop shell for macOS and Windows, installers built in CI — `apps/studio/README.md`.
- [x] Web viewer: selective bloom (only emissive light glows).
- [x] Checked: the prompt alone produced a street lamp and a windmill that built on the first attempt; a stand-in AI CLI runs the fix loop on every Blender in `check blender` and in CI.

## v0.6.1 — Picture → 3D and neural text → 3D (done)
- [x] Mesh engine: TripoSR locally (MIT, one-command setup, Apple MPS / CUDA / CPU) and Meshy, Tripo, fal (TRELLIS, Hunyuan3D, TripoSR) in the cloud, or any command; text → picture through OpenAI or FLUX for image-only generators.
- [x] `refine.py`: any generated or downloaded mesh → contract per tier — normalise, stand upright (largest flat base), clean, decimate to the tier share, unwrap, bake colour and normals (Cycles), export and validate; `gen --mesh`.
- [x] Pictures for the kit engine: the AI CLI sees the picture (Claude Read tool only, Codex -i, Gemini @file).
- [x] Studio: picture drop, engine and generator choice, one-click TripoSR install.
- [x] Checked: TripoSR live on M4 Pro; a tilted stand-in mesh through refine on Blender 3.5/4.2/5.2 and in CI; cloud adapters against a stand-in server.

## v0.6.2 — Everything works together (done)
- [x] Generated pack (`samples/packs/generated`): kit code from text and from a picture plus a TripoSR mesh, loaded in the web viewer, Unity and Godot on every tier; Unreal pack import file choice tested; the Zombie Cats diorama is checked against the scene budget.
- [x] Live progress from Blender in the CLI and Studio; Cancel and app quit stop Blender and TripoSR (process groups), tested with a never-ending job.
- [x] `doctor` shows the add-on, AI CLIs with their sign-in state, mesh generators and keys, and what to do next; gen stops at once when the AI CLI is not signed in.
- [x] Bundle test for the desktop app (its own copy of MeshGate runs gen and refine); no Python caches in or written to the bundle.
- [x] Windows: UTF-8 output in every entry point and Blender script, Windows-safe command parsing, a Windows CI job with portable Blender.
- [x] Baked tiers use JPEG; no .blend1 backups next to results.

## v0.6.3 — Ready for anyone (done)
- [x] Getting started guide (+ru) with recommendations for web, Unity, Godot and Unreal; docs link and translation check in CI.
- [x] Studio: Connect AI window (install, sign in, cloud keys in `~/.meshgate/keys.json`), own triangle limits per tier, texture or vertex colours.
- [x] `--tris` own triangle limits (kit: shown to the AI and enforced; mesh: decimate to the limit) and `--colors vertex` (no textures; Godot add-on turns vertex colours on).
- [x] Unity: MeshGateTierShowcase and GeneratedTiers.unity, every generated asset at every tier; menu Set Up Humanoid.
- [x] CPU bake by default with a GPU option and a crash retry; relative paths in custom commands; pushed to GitHub with Linux and Windows CI green.

## v0.6.4 — Status and releases (done)
- [x] Concept pictures through Codex (gpt-image-2) or OpenAI / fal: a turnaround sheet first, then the kit engine models from it.
- [x] Studio **Status & AI**: Blender (add-on install), Unity, Godot and Unreal with versions and plugin folders, AI tools, keys.
- [x] The app bundles the engine plugins; a version tag builds macOS and Windows installers into a draft GitHub Release.

## v0.6.5 — Leaner models, new look, own license (done)
- [x] Kit models lose faces hidden inside other pieces; the style decides the look; TripoSR survives a teardown crash.
- [x] New Studio look and icon (IBM Plex Sans).
- [x] Proprietary license (all rights reserved; assets you make are yours), THIRD_PARTY_NOTICES.md.

## Later — characters and PBR
- [ ] Characters from text or a picture: a rigged Humanoid base + kit parts, or a generated mesh auto-rigged onto the MeshGate skeleton.
- [ ] Transfer PBR maps (roughness, metallic) from cloud generators through the bake; multi-view input.
- [ ] Live runs of the Codex, Gemini, Ollama, Meshy, Tripo and fal adapters; Studio on a Windows machine; signed installers.

## v0.7 — Maya (second source)
- [ ] Maya → GLB export per the contract (plugin or FBX/USD → conversion).

## v0.8 — DX and site
- [x] A unified CLI `meshgate.py` (doctor/export/character/validate/serve/samples/check) and an agent skill `SKILL.md` with an installer. CI check of the samples. `gen` and `studio` arrived with v0.6.
- [ ] Publishing: make the repository public, onboarding program + a card on the website.
- [x] English docs with Russian translations (`*.ru.md`).
