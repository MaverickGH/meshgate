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

## v0.6.6 — Ready to publish (done)
- [x] README for newcomers and a full installation guide (docs/install.md) for macOS, Windows and Linux.
- [x] Portable archive for Linux (Studio in the browser without installing) in every release.
- [x] Optional components: Hunyuan3D-2 and Kimodo installable from Studio; doctor lists them.
- [x] Animations on request for kit models; a clean public history; new splash with the app icon; live tools light up green.

## v0.6.7 — Artist-level kit, live Blender for AI, big scenes, characters (done)
- [x] Artist kit: 2K–8K textures and full PBR, quad topology, sculpting (blob, skin, cut, bend, twist, sculpt brushes, paint), high → low bakes, splines, scatter, modifiers, a Humanoid rig with clips, fur cards, a free model library (CC0 / CC-BY), artist recipes in the prompt, a Kit panel in the add-on.
- [x] Realistic finish like a texturing artist: a hero high model with relief per material, curvature wear, mg.eye; clay pipeline (metaballs → smoothed grid → QuadriFlow).
- [x] Measured facts for the AI by code line (floating parts, triangles per line, asymmetry, UV use), mg.focus, joint loops, weighted normals, mg.sweep, mg.inset, UV tidy; visual review with AI-chosen close-ups, keep-best versions, a critic checklist and a library of good builds.
- [x] Studio: a progress bar with time left, refine by words or sliders (mg.param), versions with restore.
- [x] Relations: mg.place, mg.snap, mg.align, mg.socket.
- [x] Live Blender for AI clients: `meshgate.py mcp` (build, view, facts, measure, export) and Kit → Connect AI.
- [x] Big scenes: instances (one mesh, many placements, kept through tiers and bakes), seamless tiling materials (mg.tile), modular kits on a grid (mg.module, one GLB per module).
- [x] Fixed on the way: the realistic colour bake was black on models without paint; bmesh subdivide crashes in 3.5/4.2; duplicate faces broke glTF export in 3.5; per-vertex normal recomputation made realistic bakes take 20 minutes.
- [x] Zombie Cats rebuilt after the concept art in three styles; the review compares the outline with the reference, and `--fit` fits the proportions to it (vertices and skeleton together).
- [x] Characters of soft blocks: mg.union with rounded seams (one skin that bends as one), mg.patch markings that lie on the body, mg.cast, mg.symmetrize; clean low-poly facets.
- [x] Rigs that hold together: pieces on a moving body take the weights of the surface under them, weights are smoothed across the skin, faces under a moving arm are kept, spine rings on low-poly bodies; A-Pose / T-Pose rest pose (`--pose`, Studio).
- [x] Toon ink line (inverted hull, `--outline`), a softer glow halo in the viewer.

## v0.6.8 — Parts, your own models, a DCC bridge, dressed characters (done)
- [x] `--split`: every separate thing its own object under one root, named by its colour, its origin at its base (kit and your own meshes); a part editor in Studio (move, turn, scale, repaint, remove) kept as `edits.json` and reapplied on every rebuild.
- [x] Your own GLB, FBX, OBJ, PLY or STL into the Studio library; Send to Unity, Godot, Unreal or Blender (`meshgate.py send`).
- [x] A dock under the model in Studio: texture, remesh to a target polycount in quads or triangles, the UV grid, parts, send, download; the notes on the settings in an ⓘ.
- [x] Dressing and detail tools for the kit: mg.garment, mg.strap, mg.buckle, mg.pouch, mg.fringe, mg.wrap, mg.stitch, mg.bounds; colours fitted to the reference; comparison with every view of a character sheet and depth fitted from the sides.

## v0.6.9 — A character creator, part-by-part fitting, live mesh editing (done)
- [x] `mg.morph`: character-creator sliders kept as morph targets (glTF, Unity/Godot blend shapes, Unreal); Studio's Appearance tab with live sliders, palette colours, Random and Save the look (`look.json`); LODs keep the morphs; light tiers keep what fits their file budget.
- [x] `mg.section`: a model built part by part; every part compared with every view of a sheet (`parts.png`), fitted one at a time, and named in the AI review; the sheet's outline without holes.
- [x] Parts that hold up in Unity: the same names on every tier, quads per piece, copies, repaint of baked textures, undo; Unity menu Parts of Selected Model.
- [x] Live mesh editing over MCP (`blender_mesh`, `blender_edit`: move, scale, smooth, extrude, inset, bridge, subdivide, symmetrize; undo), saved bases (`blender_save_base`, `mg.load_base`), Studio → Parts → Blender base; kit `mg.mesh`, `mg.loft_path`, `mg.preserve_surface`, `mg.triangulate_polygon`, fabric and leather tiles.
- [x] The cat scout, v15: a finished character base with six sliders (`cat_character.py`); the low-poly finish keeps markings safely.

## v0.6.10 — Character bases on every tier, Windows with its own Python (done)
- [x] A saved base (`mg.load_base`) fits every tier by itself: reduced where the triangle budget is smaller, textures scaled to the tier, and where there are too many materials the whole model baked into one atlas (colour and normal) from its own materials — the cat scout v15 on PC, mobile-high, mobile-mid and mobile-low within budget.
- [x] Windows: installers and a Windows portable archive with private Python and uv (no Python, Git or Build Tools needed), fixed command paths and packaging, TripoSR on NVIDIA CUDA chosen automatically, a reproducible model setup without Git; checked on a Windows PC with Blender 4.5 LTS.

## Later — characters and PBR
- [ ] Zombie Cats, realistic: the zombie cat and fish bones through a picture → 3D generator (with a cloud key or Hunyuan3D-2).
- [ ] Character animation from text with Kimodo (installable now): SOMA BVH → retarget onto the MeshGate Humanoid in Blender → clips in GLB/FBX; needs an NVIDIA GPU.
- [ ] Hunyuan3D-2 as a local picture → 3D generator next to TripoSR (installable now).
- [ ] Characters from text or a picture: a rigged Humanoid base + kit parts, or a generated mesh auto-rigged onto the MeshGate skeleton.
- [ ] Transfer PBR maps (roughness, metallic) from cloud generators through the bake; multi-view input.
- [ ] Live runs of the Codex, Gemini, Ollama, Meshy, Tripo and fal adapters; Studio on a Windows machine; signed installers.

## v0.7 — Maya (second source)
- [ ] Maya → GLB export per the contract (plugin or FBX/USD → conversion).

## v0.8 — DX and site
- [x] A unified CLI `meshgate.py` (doctor/export/character/validate/serve/samples/check) and an agent skill `SKILL.md` with an installer. CI check of the samples. `gen` and `studio` arrived with v0.6.
- [ ] Publishing: make the repository public, onboarding program + a card on the website.
- [x] English docs with Russian translations (`*.ru.md`).
