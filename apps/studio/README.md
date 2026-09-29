**English** · [Русский](README.ru.md)

# MeshGate Studio

A desktop app for macOS and Windows that turns a description or a picture into a game-ready asset. Type what you want
or drop a picture, pick a style and the quality tiers, press **Generate**. Studio either has your AI command-line tool
write kit code or runs a neural mesh generator. It builds the model in Blender once per tier, checks it against the
asset contract and shows the result in a 3D viewer, one tab per tier.

![MeshGate Studio](../../docs/img/studio.png)

It is a window around [`meshgate.py gen`](../../docs/generation.md). Everything it makes is plain files you can take
into the web, Unity, Godot or Unreal.

## What you need

- **Blender 3.5 or newer.** Studio finds it in the usual places, or set `MESHGATE_BLENDER`.
- **Python 3.9 or newer.** macOS with Homebrew or the Xcode tools already has it. On Windows, install it from
  [python.org](https://www.python.org/downloads/) with "Add to PATH" ticked. Set `MESHGATE_PYTHON` for an unusual path.
- **One AI command-line tool, signed in once:** Claude Code (`claude`, then `/login`), Codex CLI (`codex login`),
  Gemini CLI (`gemini`) or Ollama for offline use. Any other CLI works through **AI and advanced → Custom command**.
- **For pictures, a mesh generator:** press **Install TripoSR** under **AI and advanced**. It runs locally, is MIT
  licensed and takes about 3 GB. Or set `MESHY_API_KEY`, `TRIPO_API_KEY` or `FAL_KEY` before starting Studio.

The header shows what Studio found: a green dot for Blender and for every AI CLI on your PATH. **Status & AI** opens one
window for all of it: Blender, Unity, Godot and Unreal with their versions, the Blender add-on with an **Install
add-on** button, each engine's MeshGate plugin with **Plugin files** (the folder to copy into your project), each AI tool with an **Install** button (in a terminal window) and a **Sign in** button, TripoSR's
install, and fields for cloud keys. Keys are saved to `~/.meshgate/keys.json`, readable by you only, and are shown back
as the last four characters.

## Install

- **From a release:** download `MeshGate Studio_<version>_aarch64.dmg` (macOS) or the `.msi` / `-setup.exe`
  (Windows) from the [Releases](https://github.com/MaverickGH/meshgate/releases) page. The builds are not signed yet. On macOS, right-click the app and choose **Open**
  the first time. On Windows, choose **More info → Run anyway** in SmartScreen.
- **Linux, or without installing anything:** download `MeshGate-<version>-portable.zip` from the same release, unpack it
  and run `python3 meshgate.py studio`. It opens the same UI in your browser on any OS; only Python 3.9+ and Blender are
  needed. From a clone of the repository the same command works too.

Generated assets go to `~/Documents/MeshGate Assets`; with `meshgate.py studio` inside the repository they go to
`out/gen`. Each asset has its own folder, and **Show files** opens it.

## Using it

1. Describe the model in any language, drop a picture, or both. The chips under the box are examples.
2. Tick **Draw a concept picture first** to have Codex, OpenAI or fal draw the object before it is built: a
   front/side/back/top sheet for kit code, one 3/4 view for a neural mesh. Then choose **How to build**. **Kit code** has the AI write clean, editable code, best for stylized props; it looks at the
   picture if there is one. **Neural mesh** runs TripoSR or a cloud generator, best for photos of real objects.
   **Auto** picks the neural mesh when there is a picture and a generator is ready.
3. Pick a style: Stylized, Low-poly, Realistic or Toon, and the colours: **Textures** or **Vertex colours** (no textures
   at all). Optionally give a name and the size in meters.
4. Set the triangle count with the one slider: the ticks are the tier budgets, every tier up to the one you land in
   is built, and the top one gets your number as its limit. Tick the engines you want variants for.
5. Press **Generate**. A progress bar shows the step, the percentage and about how long is left (it learns how long
   each step takes on your computer). **Progress** shows each attempt: what the AI answered, how each tier came out
   and which problems went back to the AI. **Code** shows the final `build(mg)` function.
6. Switch tiers under the viewer to see what phones get and what PC gets; play a character's clips (idle, walk,
   attack) with the buttons next to **Wireframe**. **Library** keeps every model you made.
7. **Refine** takes a kit model further, the way an artist iterates:
   - **Change in words** — "bigger ears, longer fur on the chest": the AI gets the code and the model from four
     sides (next to the picture) and changes only that.
   - **Parameters** — sliders the build code declared with `mg.param` (ear size, fur length, arm reach…); **Rebuild**
     builds again without the AI, in seconds for stylized models.
   - **Versions** — every change keeps the previous state (code, sliders, preview); **Restore** brings one back.
8. **Your own model.** Drop a GLB, FBX, OBJ, PLY or STL where the picture goes and press **Generate**: it goes into
   the library, cleaned, re-topologised and baked for every tier and checked like a generated one.
9. **Parts.** Tick **Split into parts** (Output settings) before Generate, or press **Split this model into parts** on
   the **Parts** tab: every separate thing becomes its own object — a pile of crates gives one object per crate, named
   by its colour, its origin at its base. On **Parts** click a piece in the view or the list and drag the handles
   (**Move**, **Turn** round the vertical, **Scale**), pick another palette **Colour** (kit models) or **Remove** it;
   **Save and rebuild** builds every tier with the changes. They are kept as `edits.json` next to the model and come
   back on every rebuild; **Back to as built** drops them.
10. **The dock under the model** works on the model in view: **Texture** (size, textures or vertex colours, full
    PBR), **Remesh** (one target polycount — Default, 3K, 10K, 30K, 100K — and quads or triangles), **Unwrap UV** (the
    UV grid on the model, or unwrap and bake again), **Parts**, the plug to send it to an engine, and **Download**
    (every GLB, the FBX and the .blend). Each change rebuilds every tier and keeps the previous state as a version.
    The notes on the settings live in the ⓘ next to their names.
11. **Send to…** Unity, Godot, Unreal or Blender (the plug in the dock): the files go into your project —
    `Assets/MeshGate/<model>/` (the GLB of every tier and the FBX), `res://meshgate/<model>/`, or
    `Content/MeshGate/<model>/` (the FBX) — and are replaced in place the next time, so the engine re-imports them.
    Blender opens the model's `.blend`. The project folder is asked once and remembered (`~/.meshgate/bridge.json`).
    From the command line: `python3 meshgate.py send <model folder> --to unity --project <folder>`.

## How it is built

| Part | What it does |
|---|---|
| [`server.py`](server.py) | Local server on 127.0.0.1: the UI, a JSON API, jobs that run `meshgate.py gen --events`; pure stdlib |
| [`ui/`](ui) | The page: form, progress, library, and the MeshGate web viewer for the 3D view |
| [`desktop/`](desktop) | Tauri 2 shell (Rust, about 6 MB): starts the server, opens its page in a native window |

**Security.** The server listens on the loopback address only. Every API call needs the session token, and the Host
header must be the loopback address, so web pages and other machines cannot drive your AI CLI or Blender. The desktop
shell passes the token through an environment variable, so it does not show in process lists. Generated code goes
through the [guard rails](../../docs/generation.md#kit-engine-code-written-by-an-ai) before it runs.

**Offline viewer.** `scripts/vendor_three.py` copies the three.js modules the viewer uses into `ui/vendor`; the desktop
build runs it. Without the copy, the server redirects those requests to the CDN.

**Logs.** The desktop app writes the server output to `~/Library/Logs/dev.meshgate.studio/studio.log` on macOS and to
`%LOCALAPPDATA%\dev.meshgate.studio\logs\studio.log` on Windows.

## Build the desktop app

```bash
cd apps/studio/desktop
npm ci
npx tauri build --bundles app,dmg      # macOS; on Windows: npx tauri build --bundles nsis,msi
```

You need Node 20+ and Rust. The first build takes a few minutes. The
[`studio-desktop`](../../.github/workflows/studio.yml) workflow builds the macOS and Windows installers on a version
tag or on demand. `npx tauri dev` runs the shell against the repository without bundling.

## Checked

- `tests/studio/test_server.py` covers the routes, the token, the Host check, path traversal and the three.js route.
  It runs in CI and in `meshgate.py check web`.
- A full generation from the UI with a stand-in AI CLI: the first answer fails, the fix builds, the library updates
  and the viewer loads the new model.
- The macOS app was built and started the way Finder starts it. It found Blender and Claude Code through the login
  shell's PATH, loaded the UI in its window and answered the API calls.
- `tests/studio/test_bundle.py` runs the app's own copy of MeshGate: the files are there, the bundled server answers,
  three.js is served offline, and a kit build and a mesh refine work from the bundle. CI runs it after every
  installer build.
- `tests/studio/test_cancel.py` cancels a job whose build never ends and checks that its Blender is gone. Quitting
  the app asks the server to cancel its jobs first, so no Blender is left running.
- Progress arrives line by line while Blender works, not only at the end.
- The Windows build is configured and runs in CI, but it has not been started on a Windows machine yet.
