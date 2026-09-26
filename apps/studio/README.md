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
4. Tick the quality tiers you need; the richest one becomes the canonical `<name>.glb`. The number field next to a
   tier is your own triangle limit for it, for when far fewer triangles are enough. Tick the engines you want
   variants for.
5. Press **Generate**. **Progress** shows each attempt: what the AI answered, how each tier came out and which problems
   went back to the AI. **Code** shows the final `build(mg)` function.
6. Switch tiers under the viewer to see what phones get and what PC gets. **Library** keeps every model you made.

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
