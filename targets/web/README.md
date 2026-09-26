**English** · [Русский](README.ru.md)

# Target: Web (Three.js)

Web runtime for the canonical GLB. Two layers:

| File | What it is |
|---|---|
| `meshgate-viewer.js` | A UI-less **library**: scene, lights, environment, GLB loading (Draco / KTX2 / meshopt), interaction, animations, drag-and-drop. Embeds into any website. |
| `index.html` + `app.js` | **Demo page** — a reference for the method: a panel with the asset passport, object tree, animations, view settings, loading your own files. |
| `serve.py` | Local static server (stdlib); serves the repository root so that `/samples/*.glb` are reachable. |

There is a single dependency — Three.js (MIT) from a CDN via an import map; the Draco/Basis decoders also come from the Three.js CDN. For offline use, copy `three@0.169.0` locally and adjust the import map in `index.html`.

## Running

```bash
python3 targets/web/serve.py                       # http://localhost:8770/targets/web/ → samples/meshgate_demo.glb
python3 targets/web/serve.py --glb samples/my.glb  # open a different asset
```

URL parameters: `?glb=<url>` — the asset; `&hdr=<url .hdr>` — HDRI environment (for example, `https://raw.githubusercontent.com/mrdoob/three.js/r169/examples/textures/equirectangular/royal_esplanade_1k.hdr`; the server must send CORS headers); `&env=none` — no environment; `&autoplay=0` — do not start animations.

## What the demo page can do

- **Navigation**: LMB — orbit, RMB — pan, wheel — zoom. Inertia and smooth camera fly-to.
- **Interaction**: hover highlights an object and shows its name; click — selection with a passport (hierarchy path, extents, tris, material, presence of UVs/normals); double click — focus the camera on the object. The object tree is synced with the selection.
- **Animations**: list of clips from the GLB, solo mode, pause/stop, a timeline with scrubbing, speed, loop. `Space` — pause.
- **Environment**: studio `RoomEnvironment` (no external files) or HDRI by URL / by dragging in an `.hdr`; the HDRI can be shown as the background. ACES tone mapping, adjustable exposure.
- **Lights and shadows**: sky + a key directional light with soft shadows on an invisible "shadow catcher" under the asset. The grid is placed at the bottom of the asset.
- **Draco** (`KHR_draco_mesh_compression`), **KTX2/Basis** (`KHR_texture_basisu`), **meshopt** (`EXT_meshopt_compression`) — decoded transparently.
- **Loading your own assets**: URL, file picker or drag-and-drop of `.glb`/`.gltf`/`.hdr` onto the page.
- **Rig**: skeleton helper (`S`), **UV checker** (`U`) — replaces materials with a checkered texture to assess the unwrap; the passport shows the bone count and meshes without UVs.
- **Other**: wireframe (`W`), grid (`G`), camera reset (`R`), PNG screenshot, fps / draw calls / triangles counter, the panel hides with `Tab`.

## Embedding the library

```html
<script type="importmap">
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
} }
</script>
<div id="viewer" style="width:100%;height:480px"></div>
<script type="module">
  import { createViewer } from "./meshgate-viewer.js";
  const v = createViewer(document.getElementById("viewer"), { environment: "room", grid: false });
  const info = await v.load("/assets/chest.glb");          // { dims, triangles, materials, animations, extensions, ... }
  v.on("select", ({ object }) => console.log("selected:", object?.name));
  v.animations.solo("lid_open");                            // play only one clip
  v.frame(v.asset.root.getObjectByName("beacon_ring"));     // fly to the object
</script>
```

### API `createViewer(container, options)`

Options: `background` (color), `accent`, `grid`, `shadows`, `environment` (`"room" | "none" | url.hdr`), `showEnvironment`, `exposure`, `autoplay`, `dracoPath`, `ktx2Path`, `dropTarget`.

| Method / field | Purpose |
|---|---|
| `load(urlOrFile)` → `Promise<info>` | Load a GLB, replacing the current one. `info` is the asset passport. |
| `unload()` | Remove the asset and free GPU resources. |
| `frame(object?)`, `resetView()` | Frame an object (the whole asset by default) / reset the camera. |
| `select(object)`, `hover(object)`, `describeObject(object)` | Control the selection from your own UI. |
| `animations.play(name?) / pause() / toggle() / stop() / solo(name) / setTime(s) / setSpeed(k) / setLoop(bool)`, `animations.clips`, `animations.state` | Animations. |
| `setEnvironment(mode)`, `setShowEnvironment(bool)`, `setBackgroundColor(hex)`, `setExposure(v)` | Environment and tone. |
| `setGrid(bool)`, `setShadows(bool)`, `setWireframe(bool)`, `setSkeleton(bool)`, `setUvChecker(bool)` | View. |
| `screenshot(type?)` → dataURL | Snapshot of the current frame. |
| `on(event, cb)` / `off(event, cb)` | Events: `loadstart`, `progress`, `load`, `error`, `select`, `hover`, `frame`, `animation`, `tick`, `stats`, `drag`. |
| `asset`, `selected`, `hovered`, `stats`, `environmentMode`, `scene`, `camera`, `renderer`, `controls`, `THREE` | Access to internals for extension. |
| `dispose()` | Fully stop and remove the viewer. |

## Limitations

- The viewer does not check Y-up and meters (this is not visible from the file) — that is done by the contract on the export side and by `core/validate_glb.py`.
- `KHR_materials_*` extensions render as supported by the given Three.js version.
