**English** · [Русский](getting-started.ru.md)

# Getting started

MeshGate takes a 3D asset — made in Blender, generated from a description or a picture, or downloaded — and delivers
it to the web, Unity, Godot and Unreal as checked files, one per quality tier. This page gets you from a fresh clone to
an asset in your engine.

## 1. What you need

| For | Needs | Notes |
|---|---|---|
| Everything | **Python 3.9+** | Standard library only; nothing to `pip install` |
| Export, generation, checks | **Blender 3.5+** | Tested on 3.5, 4.2 LTS and 5.2 LTS. Found automatically, or set `MESHGATE_BLENDER` |
| Text → 3D | One **AI command-line tool** | Claude Code, Codex, Gemini or Ollama, signed in once — see step 4 |
| Picture → 3D | **TripoSR** (local) or a cloud key | `meshgate.py gen --setup triposr` installs TripoSR into `~/.cache/meshgate` (~3 GB, MIT) |
| Optional, later | **Hunyuan3D-2** (picture → 3D, ~10 GB) and **Kimodo** (text → character animation, ~20 GB) | Installed separately from Studio → **Status & AI** → Optional components, or `meshgate.py gen --setup hunyuan3d` / `kimodo`. Both want an NVIDIA GPU; Kimodo also needs access to Meta Llama 3 on Hugging Face |
| Web | A modern browser | WebGL 2; Three.js comes from the viewer |
| Unity | **Unity 6000.0+** | glTFast 6.20 requires Unity 6 |
| Godot | **Godot 4.4+** | Tested on 4.7.2 (Forward+) |
| Unreal | **UE 5.4–5.6** | Checked against the Python API; the first live run is still ahead |

## 2. Install and check

```bash
git clone https://github.com/MaverickGH/meshgate.git
cd meshgate
python3 meshgate.py doctor
```

`doctor` lists what it found — Blender, the add-on, the engines, the AI tools with their sign-in state, the mesh
generators and your keys — and ends with the next steps for whatever is missing.

## 3. Three ways to work

- **In Blender, no terminal.** `python3 meshgate.py install-blender` (close Blender first), then **N → MeshGate**: tick
  the engines and quality tiers, press **Check**, **Fix all**, **Export**. See [sources/blender/README.md](../sources/blender/README.md).
- **MeshGate Studio.** A desktop app for macOS and Windows, or `python3 meshgate.py studio` in any browser: describe a
  model or drop a picture, press **Generate**, see every tier in 3D. See [apps/studio/README.md](../apps/studio/README.md).
- **Command line.** `meshgate.py export`, `validate`, `gen` and `check` do the same things headless and in CI.

## 4. Connect an AI

In Studio press **Status & AI**. It shows Blender, Unity, Godot and Unreal with their versions and MeshGate plugins,
and each AI tool's state; it installs the Blender add-on and AI tools, runs their sign-in and stores cloud keys. In a
terminal:

| Tool | Install | Sign in once |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` | `claude auth login`, or set `ANTHROPIC_API_KEY` |
| [Codex CLI](https://github.com/openai/codex) | `npm install -g @openai/codex` | `codex login`, or set `OPENAI_API_KEY` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm install -g @google/gemini-cli` | run `gemini` and pick a login, or set `GEMINI_API_KEY` |
| [Ollama](https://ollama.com/download), offline | the app from ollama.com | `ollama pull qwen2.5-coder:14b` |

With Codex signed in to ChatGPT you also get pictures from text for free: `--concept sheet` has gpt-image-2 draw a
turnaround sheet first and the AI models from it. Cloud mesh generators need a key: `MESHY_API_KEY`, `TRIPO_API_KEY` or `FAL_KEY`. `OPENAI_API_KEY` or `FAL_KEY` also
draws a reference picture when an image-only generator gets text. Put keys in the environment, or save them in Studio.
Studio writes them to `~/.meshgate/keys.json`, a file readable by you only, which the command line reads too. Then:

```bash
python3 meshgate.py gen --list-ai                          # what is ready
python3 meshgate.py gen "a wooden treasure chest" --size 0.8
python3 meshgate.py gen --image photo.jpg --size 0.8
```

Need far fewer triangles, or no textures at all? `--tris 500` sets your own limit (`low=150,pc=2000` per tier),
and `--colors vertex` stores the colours in the vertices. Both are in Studio too. More in [docs/generation.md](generation.md).

## 5. Every file MeshGate writes

| File | Where it goes |
|---|---|
| `<name>.glb` | The canonical asset (PC tier): web, Unity, Godot, Unreal Interchange |
| `<name>.mobile-low.glb`, `.mobile-mid.glb`, `.mobile-high.glb` | The same asset for each phone tier, within that tier's budget |
| `<name>.fbx` | Unity and Unreal editors, Humanoid characters |
| `<name>.unreal.fbx` | Unreal static meshes with `UCX_` collision |
| `<name>.godot.glb` | Godot editor import with `-convcolonly` collision |
| `<name>.unity.fbx` | Unity with `_LOD0…_LODn` meshes for an LOD Group |

Budgets per tier are in [docs/quality-tiers.md](quality-tiers.md); the rules every file follows are in
[docs/asset-contract.md](asset-contract.md).

## 6. Recommendations per target

### Web (Three.js)

- **Use the viewer library.** [`targets/web/meshgate-viewer.js`](../targets/web/meshgate-viewer.js) runs on Three.js
  r169 through an import map. `createViewer(container, { quality: "auto" })` picks a tier from the device. With
  `variants: true` it loads `<name>.<tier>.glb` next to the canonical file when one exists. See
  [targets/web/README.md](../targets/web/README.md).
- **Serve the tier files next to each other.** Keep `<name>.glb` and its `.mobile-*.glb` files in one folder. Serve
  them as `model/gltf-binary` with long cache headers; the viewer asks for them only when the tier needs them.
- **Choose files by audience.** Phones should get `mobile-low` or `mobile-mid`. Use `.draco.glb` only when you ship the
  Draco decoder, which the viewer takes from the Three.js CDN. For offline use, copy three.js locally with
  `python3 scripts/vendor_three.py`.
- **Bloom is selective.** Only emissive materials glow on high tiers, so bright but unlit surfaces stay as they are.

### Unity

- **Install two packages.** Get **glTFast** (`com.unity.cloud.gltfast`) from the Unity registry. Then add MeshGate
  through Package Manager → Add package from git URL:
  `https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity`.
- **Runtime loading.** Add a **MeshGateAsset** component and set `source`. Relative paths resolve from
  `StreamingAssets`. It loads the canonical GLB and plays its clips by name, and a scene-wide **MeshGateQuality**
  makes it pick `<name>.<tier>.glb` for mobile tiers.
- **Editor assets.** Characters use the `.fbx` with a Humanoid avatar: select it and run **MeshGate → Set Up Humanoid
  (Selected FBX)**. Static
  props can use either file; `.unity.fbx` carries `_LOD` meshes ready for an LOD Group.
- **Check your project the way we do.** `MeshGateTierShowcase` in the sample scene `GeneratedTiers.unity` shows every
  asset of a pack at every tier with its triangle count; press Play. `python3 meshgate.py check unity` runs all the
  PlayMode tests headless.
- **Draco, KTX2 and meshopt** files need their Unity packages; without them, ship the plain `.glb`.
- **On Android**, StreamingAssets live inside the APK, so the tier variant check falls back to the canonical file.
  Ship the tier you need as `source`.

See [targets/unity/README.md](../targets/unity/README.md).

### Godot

- **Install the add-on.** Copy `targets/godot/MeshGateDemo/addons/meshgate/` to `res://addons/` and enable it in
  Project → Plugins.
- **Runtime loading.** Add a **MeshGateAsset** node with `source` (`res://`, `user://` or an absolute path). It loads
  through `GLTFDocument`. `MeshGateQuality.apply("mobile-low", get_viewport())` switches both the render settings and
  the tier files.
- **Editor import** for collision. Only the editor importer turns `-convcolonly` nodes into `StaticBody3D`, so drop the
  `.godot.glb` into the project for static props that need collision.
- **Draco** has no decoder in Godot 4; ship the plain `.glb`. glTF is preferable to FBX in Godot.

See [targets/godot/README.md](../targets/godot/README.md).

### Unreal Engine

- **Install the plugin.** Copy `targets/unreal/MeshGate` to `<Project>/Plugins/MeshGate`. Enable **Python Editor Script
  Plugin** and **Interchange**, then restart; **Tools → MeshGate** appears.
- **Import.** `.glb` goes through Interchange with MeshGate's pipeline settings. Static props with collision come from
  `.unreal.fbx`, whose `UCX_` meshes become collision. Characters come from `.fbx` as a Skeletal Mesh.
  `meshgate_import.import_pack(folder, profile="mobile-mid")` brings in a whole pack at one tier.
- **Quality.** `meshgate_import.apply_quality("mobile-mid")` maps a MeshGate tier to Unreal scalability settings.
- **Runtime loading** of a GLB in a packaged game uses the third-party
  [glTFRuntime](https://github.com/rdeioris/glTFRuntime) plugin (MIT).
- **Status.** Every Unreal API name the plugin uses is checked against UE 5.4–5.6, and the pack importer's file choice
  is tested. A live editor run is the next step, so report anything that behaves differently.

See [targets/unreal/README.md](../targets/unreal/README.md).

## 7. When something goes wrong

| Symptom | Fix |
|---|---|
| "Blender not found" | Install Blender 3.5+ or set `MESHGATE_BLENDER=/path/to/blender` |
| "claude is not signed in" | Studio → **Status & AI** → **Sign in**, or run `claude auth login` once |
| An AI answers without code | The CLI printed a message instead of code, often about sign-in or quota. The message is in `out/gen/<name>/attempt_1.answer.md` |
| Picture → 3D says no generator is ready | `python3 meshgate.py gen --setup triposr`, or set a cloud key |
| A generated mesh leans or faces away | `--turn 90` rotates the front; `--no-upright` keeps the original tilt |
| Colours look washed out from a generator | Pass `--vertex-srgb` for files whose vertex colours are picture values; TripoSR files are detected automatically |
| macOS says the app is from an unidentified developer | Right-click **MeshGate Studio** → **Open** the first time (builds are not signed yet) |
| Windows SmartScreen blocks the installer | **More info → Run anyway** |
| Anything else | `python3 meshgate.py doctor` and `python3 meshgate.py check all`; Studio → **Status & AI** shows what was found; the app writes its log to `~/Library/Logs/dev.meshgate.studio/` or `%LOCALAPPDATA%\dev.meshgate.studio\logs\` |
