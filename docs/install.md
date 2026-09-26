**English** · [Русский](install.ru.md)

# Installation

Everything MeshGate needs, step by step, for macOS, Windows and Linux. Only steps 1–3 are required; the rest adds what
you want to do. At the end, [check it all](#8-check-that-everything-works) in one place.

| You want to… | You need | Step |
|---|---|---|
| Open MeshGate Studio | The app (or the portable archive) and **Python 3.9+** | [1](#1-meshgate-studio), [2](#2-python) |
| Build, check and export models | **Blender 3.5+** with the MeshGate add-on | [3](#3-blender-and-the-meshgate-add-on) |
| Make a model from a description | One **AI command-line tool**, signed in once | [4](#4-an-ai-tool-for-text--3d) |
| Make a model from a picture | **TripoSR** (local, free) or a cloud key | [5](#5-picture--3d) |
| Put the files into an engine | The MeshGate plugin for Unity, Godot or Unreal | [6](#6-engine-plugins) |
| Better picture → 3D, character animation | Optional components (NVIDIA GPU) | [7](#7-optional-components) |

## How it works

You describe a model or drop a picture into MeshGate Studio. An AI tool writes a short program that builds the model
from simple parts (the *kit engine*), or a neural network turns the picture into a mesh (the *mesh engine*). Blender,
running in the background, builds the model once for each quality tier — PC, mobile high, mobile mid, mobile low —
checks every file against the tier's budget and the engines' rules, and sends any problem back to the AI to fix. You
get one checked `.glb` per tier plus `.fbx` and engine variants, shown in 3D in Studio and saved to your library.

![text → code → Blender per tier → validated files](img/generation-flow.svg)

MeshGate runs on your computer. Studio is a small local server with a window; nothing is uploaded except what an AI
tool or a cloud generator you chose needs.

## 1. MeshGate Studio

Download from the [Releases](https://github.com/MaverickGH/meshgate/releases) page:

| System | File | Install |
|---|---|---|
| macOS (Apple Silicon) | `MeshGate.Studio_<version>_aarch64.dmg` | Open it and drag **MeshGate Studio** into Applications |
| Windows 10/11 (64-bit) | `MeshGate.Studio_<version>_x64-setup.exe` or `_x64_en-US.msi` | Run it; either one installs the same app |
| Linux, or any system without installing | `MeshGate-<version>-portable.zip` | Unpack it anywhere |

The builds are not signed yet, so the first launch needs one extra click:

- **macOS:** right-click **MeshGate Studio** → **Open** → **Open**. On macOS 15 and newer, if it still refuses: System
  Settings → Privacy & Security → **Open Anyway**.
- **Windows:** SmartScreen → **More info** → **Run anyway**.

Start the portable version from its folder (`START.txt` inside says the same):

```bash
python3 meshgate.py studio
```

It opens Studio in your browser. It runs on this computer only; no one else can reach it.

**From the source code** (for development): `git clone https://github.com/MaverickGH/meshgate.git`, then
`python3 meshgate.py studio` in that folder.

## 2. Python

MeshGate Studio — the app and the portable version — runs on **Python 3.9 or newer**. Only the standard library is
used: nothing to `pip install`.

- **macOS:** usually present. If not, install it from [python.org](https://www.python.org/downloads/) or run
  `xcode-select --install` in Terminal.
- **Windows:** install from [python.org](https://www.python.org/downloads/) and tick **Add python.exe to PATH**, or
  from the Microsoft Store.
- **Linux:** preinstalled on most distributions (`python3 --version`).

If the app says Python was not found, install it and open the app again. `MESHGATE_PYTHON` points it at a particular
Python.

## 3. Blender and the MeshGate add-on

1. Install **Blender 3.5 or newer** from [blender.org](https://www.blender.org/download/). MeshGate is tested on 3.5,
   4.2 LTS and 5.2 LTS.
2. MeshGate finds Blender in the usual places: Applications on macOS, Program Files or Steam on Windows, `/usr/bin`,
   `/snap/bin`, `/opt` or an archive unpacked in your home folder on Linux. Anywhere else, set `MESHGATE_BLENDER` to the
   Blender executable.
3. Install the add-on, with Blender closed — any one way:
   - Studio → **Status & AI** → Blender → **Install add-on**;
   - `python3 meshgate.py install-blender`;
   - by hand: `python3 meshgate.py addon` writes `dist/meshgate-blender-<version>.zip`. Blender 4.2+: drag the zip
     into the Blender window. Blender 3.5–4.1: Preferences → Add-ons → Install.
4. In Blender press **N** → **MeshGate** tab: **Check**, **Fix all**, **Export**. See
   [sources/blender/README.md](../sources/blender/README.md).

Studio needs Blender for every build, but not the add-on: the add-on is for working in Blender yourself.

## 4. An AI tool for text → 3D

Text → 3D needs one AI command-line tool. Studio → **Status & AI** shows each one's state, installs it in a terminal
window and starts its sign-in. The same by hand:

| Tool | Install | Sign in once |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` | `claude auth login`, or set `ANTHROPIC_API_KEY` |
| [Codex CLI](https://github.com/openai/codex) | `npm install -g @openai/codex` | `codex login`, or set `OPENAI_API_KEY` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm install -g @google/gemini-cli` | run `gemini` and pick a login, or set `GEMINI_API_KEY` |
| [Ollama](https://ollama.com/download), offline | the app from ollama.com | `ollama pull qwen2.5-coder:14b` |

`npm` comes with [Node.js](https://nodejs.org) 18 or newer. A subscription sign-in (Claude, ChatGPT for Codex, Google
for Gemini) is enough; an API key is the alternative. Codex signed in to ChatGPT also draws concept pictures for free
(`--concept sheet`, the Studio checkbox "Draw a concept picture first").

## 5. Picture → 3D

Pick one:

- **TripoSR — local and free** (MIT, ~3 GB, CPU or Apple GPU). Studio → **Status & AI** → Optional components →
  TripoSR → **Install** (also under **AI and advanced**), or `python3 meshgate.py gen --setup triposr`. It needs `git` and either [uv](https://docs.astral.sh/uv/) or Python
  3.10–3.12.
- **A cloud generator:** a key for [Meshy](https://www.meshy.ai/api) (`MESHY_API_KEY`), [Tripo](https://platform.tripo3d.ai)
  (`TRIPO_API_KEY`) or [fal.ai](https://fal.ai/dashboard/keys) (`FAL_KEY`: TRELLIS, Hunyuan3D, TripoSR). Paste it in
  Studio → **Status & AI** → API keys, or set it in the environment.

Keys are stored in `~/.meshgate/keys.json`, readable by you only; Studio shows only their last four characters.

## 6. Engine plugins

Studio → **Status & AI** shows which engines are installed and opens each plugin's folder (**Plugin files**).

- **Web (Three.js):** nothing to install. Serve the `.glb` files and use
  [`targets/web/meshgate-viewer.js`](../targets/web/README.md), or `python3 meshgate.py serve --glb file.glb`.
- **Unity 6000.0+:** install **glTFast** (`com.unity.cloud.gltfast`) from the Unity registry. Then Package Manager →
  **Add package from disk** → the `package.json` in the plugin folder (`targets/unity/com.meshgate.unity`), or **Add
  package from git URL** → `https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity`.
  See [targets/unity/README.md](../targets/unity/README.md).
- **Godot 4.4+:** copy `targets/godot/MeshGateDemo/addons/meshgate/` into your project's `res://addons/` and enable it
  in Project → Plugins. See [targets/godot/README.md](../targets/godot/README.md).
- **Unreal Engine 5.4–5.6:** copy `targets/unreal/MeshGate` into `<Project>/Plugins/`, enable **Python Editor Script
  Plugin** and **Interchange**, restart; **Tools → MeshGate** appears. See [targets/unreal/README.md](../targets/unreal/README.md).

Which file goes where, and the recommendations per engine: [Getting started §5–6](getting-started.md#5-every-file-meshgate-writes).

## 7. Optional components

Big local models, installed only when you want them — Studio → **Status & AI** → Optional components, or the command.
Each one gets its own folder and Python environment under `~/.cache/meshgate`; they need `git` and
[uv](https://docs.astral.sh/uv/).

| Component | What for | Install | Needs | License |
|---|---|---|---|---|
| Hunyuan3D-2 | Picture → 3D with finer shapes | `meshgate.py gen --setup hunyuan3d` (~10 GB) | NVIDIA GPU, 6 GB+ (16 GB+ with textures) | Tencent Hunyuan 3D Community License — not in the EU, UK or South Korea |
| Kimodo | Text → animation for Humanoid characters | `meshgate.py gen --setup kimodo` (~20 GB) | NVIDIA GPU; access to Meta Llama 3 8B on Hugging Face, then `hf auth login` | Apache-2.0 code, NVIDIA Open Model License; Llama 3 Community License |

Both install now; generation starts using them once a run on a supported GPU has been checked
([roadmap](roadmap.md)).

## 8. Check that everything works

- **In Studio:** the header buttons show what was found; **Status & AI** lists Blender with its add-on, Unity, Godot,
  Unreal, the AI tools with their sign-in, the picture generators, the optional components and your keys, each with
  what to do next.
- **In a terminal:** `python3 meshgate.py doctor` prints the same and ends with the next steps.
- **A first model:** type "a wooden crate with metal corners", press **Generate**. A build takes one to three minutes;
  every tier appears in 3D with its triangle count.

## Where MeshGate keeps things

| What | Where |
|---|---|
| Your models (Studio library) | `~/Documents/MeshGate Assets` (from a source checkout: `out/gen`); **Show files** opens a model's folder |
| API keys | `~/.meshgate/keys.json` |
| TripoSR, Hunyuan3D, Kimodo | `~/.cache/meshgate/<name>` |
| App log | macOS `~/Library/Logs/dev.meshgate.studio/`, Windows `%LOCALAPPDATA%\dev.meshgate.studio\logs\` |

**Update:** install the new release over the old one; your library, keys and components stay. **Uninstall:** remove
the app (or the portable folder), then delete the folders above if you want them gone too.

Something not working? [Getting started → When something goes wrong](getting-started.md#7-when-something-goes-wrong).
