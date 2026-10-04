// MeshGate — web runtime for the canonical GLB (our code on top of Three.js, MIT).
//
// UI-less library: creates the scene, loads GLB (Draco / KTX2 / meshopt),
// sets up the environment (RoomEnvironment or HDRI), lights and shadows, an orbit camera,
// interaction (hover / click / double-click → focus), animations and drag-and-drop.
// The demo page (app.js) is just a thin wrapper around this API.
//
//   import { createViewer } from "./meshgate-viewer.js";
//   const v = createViewer(document.getElementById("app"));
//   await v.load("/samples/meshgate_demo.glb");
//   v.on("select", ({ object }) => console.log(object?.name));
//
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

const THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/libs/";

// Quality tiers — mirrors the "render" part of core/profiles.json (tests/check_profiles.py keeps them in sync).
export const QUALITY = {
  "mobile-low": { label: "Mobile · low", pixel_ratio: 1.0, render_scale: 0.75, msaa: 0, shadows: "off", shadow_map: 0, ao: false, bloom: false },
  "mobile-mid": { label: "Mobile · mid", pixel_ratio: 1.5, render_scale: 0.9, msaa: 2, shadows: "hard", shadow_map: 1024, ao: false, bloom: false },
  "mobile-high": { label: "Mobile · high", pixel_ratio: 2.0, render_scale: 1.0, msaa: 4, shadows: "soft", shadow_map: 2048, ao: false, bloom: true },
  "pc": { label: "PC · high quality", pixel_ratio: 2.0, render_scale: 1.0, msaa: 4, shadows: "soft", shadow_map: 4096, ao: true, bloom: true },
};

/** Best guess of the device tier: desktop → "pc"; phones/tablets by memory, cores and GPU name. */
export function detectQuality() {
  const ua = navigator.userAgent || "";
  const iPadOS = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
  const mobile = /Android|iPhone|iPad|iPod|Mobile/i.test(ua) || iPadOS;
  if (!mobile) return "pc";
  const mem = navigator.deviceMemory || 4;          // Chrome/Android only; Safari → 4
  const cores = navigator.hardwareConcurrency || 4;
  let gpu = "";
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
    gpu = ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : "";
  } catch (_) { /* no WebGL info */ }
  if (/iPhone|iPad/.test(ua) || iPadOS || /Apple/.test(gpu)) {
    return screen.width * devicePixelRatio >= 2400 || iPadOS ? "mobile-high" : "mobile-mid";
  }
  if (mem <= 3 || cores <= 4 || /Mali-G(3|5)\d|Adreno \(TM\) (3|4|5)\d\d|Adreno \(TM\) 6[01]\d/.test(gpu)) return "mobile-low";
  if (mem >= 8 && cores >= 8 && /Adreno \(TM\) (7[3-9]|8)\d+|Immortalis|Xclipse|Mali-G7[1-9]/.test(gpu)) return "mobile-high";
  return "mobile-mid";
}

const DEFAULTS = {
  background: 0x0b0e17,
  accent: 0xa78bfa,
  gridMajor: 0x3a4470,
  gridMinor: 0x1d2444,
  grid: true,
  shadows: true,
  environment: "room",      // "room" | "none" | URL of an .hdr
  showEnvironment: false,   // draw the HDRI as the background
  exposure: 1.0,
  autoplay: true,
  dracoPath: THREE_CDN + "draco/gltf/",
  ktx2Path: THREE_CDN + "basis/",
  pixelRatioCap: 2,
  quality: "auto",          // "auto" | "mobile-low" | "mobile-mid" | "mobile-high" | "pc"
  variants: true,           // load <name>.<tier>.glb next to <name>.glb when it exists
};

export function createViewer(container, options = {}) {
  const opts = { ...DEFAULTS, ...options };
  const listeners = new Map();
  const emit = (name, payload) => (listeners.get(name) || []).forEach((cb) => cb(payload));

  // --- renderer / scene ------------------------------------------------------
  const detectedTier = detectQuality();
  let tier = QUALITY[opts.quality] ? opts.quality : detectedTier;
  const renderer = new THREE.WebGLRenderer({ antialias: QUALITY[tier].msaa > 0, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, opts.pixelRatioCap));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = opts.exposure;
  renderer.shadowMap.enabled = opts.shadows;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.touchAction = "none";

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(opts.background);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.position.set(2.5, 1.8, 3);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = true;

  // Lights: soft sky + directional key light with shadows. The environment (PMREM) provides reflections.
  const hemi = new THREE.HemisphereLight(0xdfe8ff, 0x1c2036, 0.6);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(3, 6, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  scene.add(key, key.target);

  const grid = new THREE.GridHelper(10, 20, opts.gridMajor, opts.gridMinor);
  grid.material.transparent = true;
  grid.material.opacity = 0.6;
  grid.visible = opts.grid;
  scene.add(grid);

  // Shadow catcher — an invisible plane under the asset.
  const shadowCatcher = new THREE.Mesh(
    new THREE.PlaneGeometry(1, 1),
    new THREE.ShadowMaterial({ opacity: 0.35, color: 0x000000 })
  );
  shadowCatcher.rotation.x = -Math.PI / 2;
  shadowCatcher.receiveShadow = true;
  shadowCatcher.visible = opts.shadows;
  scene.add(shadowCatcher);

  // Hover / selection highlight — box helpers; the asset's materials are left untouched.
  const hoverBox = new THREE.Box3Helper(new THREE.Box3(), new THREE.Color(opts.accent));
  hoverBox.material.transparent = true;
  hoverBox.material.opacity = 0.45;
  hoverBox.visible = false;
  const selectBox = new THREE.Box3Helper(new THREE.Box3(), new THREE.Color(opts.accent));
  selectBox.visible = false;
  scene.add(hoverBox, selectBox);

  // --- environment ----------------------------------------------------------
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  let envTexture = null;
  let hdrTexture = null;
  let envMode = "none";

  async function setEnvironment(mode) {
    if (envTexture) { envTexture.dispose(); envTexture = null; }
    if (hdrTexture) { hdrTexture.dispose(); hdrTexture = null; }
    if (!mode || mode === "none") {
      scene.environment = null;
      envMode = "none";
      applyBackground();
      return;
    }
    if (mode === "room") {
      envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environment = envTexture;
      envMode = "room";
      applyBackground();
      return;
    }
    // URL / File of an .hdr (equirect)
    const url = mode instanceof File ? URL.createObjectURL(mode) : mode;
    const tex = await new RGBELoader().loadAsync(url);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    hdrTexture = tex;
    envTexture = pmrem.fromEquirectangular(tex).texture;
    scene.environment = envTexture;
    envMode = "hdr";
    applyBackground();
    if (mode instanceof File) URL.revokeObjectURL(url);
  }

  function applyBackground() {
    scene.background = opts.showEnvironment && hdrTexture ? hdrTexture : new THREE.Color(opts.background);
  }

  // --- loader ---------------------------------------------------------------
  const draco = new DRACOLoader().setDecoderPath(opts.dracoPath);
  const ktx2 = new KTX2Loader().setTranscoderPath(opts.ktx2Path).detectSupport(renderer);
  const loader = new GLTFLoader().setDRACOLoader(draco).setKTX2Loader(ktx2).setMeshoptDecoder(MeshoptDecoder);

  let asset = null;        // { root, gltf, info, url }
  let mixer = null;
  let actions = [];
  let animState = { playing: opts.autoplay, speed: 1, loop: true, duration: 0 };

  async function variantFor(source) {
    if (!opts.variants || typeof source !== "string" || tier === "pc" || /\.(mobile-low|mobile-mid|mobile-high)\.glb/i.test(source)) return source;
    const candidate = source.replace(/\.glb(\?.*)?$/i, `.${tier}.glb$1`);
    if (candidate === source) return source;
    try {
      const res = await fetch(candidate, { method: "HEAD", cache: "no-store" });
      return res.ok ? candidate : source;
    } catch (_) { return source; }
  }

  async function load(source, { name } = {}) {
    const requested = source;
    if (typeof source === "string") source = await variantFor(source);
    const url = source instanceof File ? URL.createObjectURL(source) : source;
    const displayName = name || (source instanceof File ? source.name : String(source).split("?")[0].split("/").pop());
    const t0 = performance.now();
    emit("loadstart", { name: displayName });
    let gltf;
    try {
      gltf = await loader.loadAsync(url, (ev) => emit("progress", { loaded: ev.loaded, total: ev.total }));
    } catch (e) {
      emit("error", { name: displayName, error: e });
      throw e;
    } finally {
      if (source instanceof File) URL.revokeObjectURL(url);
    }
    unload();
    const root = gltf.scene;
    root.traverse((o) => {
      if (o.isMesh) {
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        o.castShadow = !mats.some((m) => m.transparent); // glass doesn't cast a solid shadow
        o.receiveShadow = true;
      }
    });
    scene.add(root);
    asset = { root, gltf, url: displayName, source: requested, info: describe(gltf, root, performance.now() - t0, displayName) };
    asset.info.file = typeof source === "string" ? source.split("?")[0].split("/").pop() : displayName;
    asset.info.tier = tier;
    asset.info.variant = typeof source === "string" && source !== requested ? tier : "canonical";
    setupAnimations(gltf);
    fitGround(root);
    frame(root);
    setWireframe(state.wireframe);
    setSkeleton(state.skeleton);
    setUvChecker(state.uvChecker);
    hasGlow = detectGlow(asset.root);
    emit("load", asset.info);
    return asset.info;
  }

  function unload() {
    if (!asset) return;
    gizmo?.detach();
    hasGlow = false;
    scene.remove(asset.root);
    asset.root.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      mats.forEach((m) => { const g = glowMaterials.get(m); if (g && g !== GLOW_BLACK) g.dispose(); });
      mats.forEach((m) => { Object.values(m).forEach((v) => v?.isTexture && v.dispose()); m.dispose(); });
    });
    if (mixer) mixer.stopAllAction();
    if (skeletonHelper) { scene.remove(skeletonHelper); skeletonHelper.dispose(); skeletonHelper = null; }
    mixer = null; actions = [];
    select(null); hover(null);
    asset = null;
  }

  function describe(gltf, root, loadMs, name) {
    const box = new THREE.Box3().setFromObject(root, true);
    const size = box.getSize(new THREE.Vector3());
    let triangles = 0, meshes = 0, vertices = 0, bones = 0, skinned = 0, noUv = 0;
    const materials = new Set(), textures = new Set(), nodes = [];
    root.traverse((o) => {
      if (o.name) nodes.push({ name: o.name, type: o.isMesh ? "mesh" : o.isBone ? "bone" : "node", object: o });
      if (o.isBone) bones++;
      if (o.isSkinnedMesh) skinned++;
      if (o.isMesh) {
        meshes++;
        if (!o.geometry.attributes.uv) noUv++;
        const g = o.geometry;
        const count = g.index ? g.index.count : g.attributes.position?.count || 0;
        triangles += Math.floor(count / 3);
        vertices += g.attributes.position?.count || 0;
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => {
          materials.add(m);
          Object.values(m).forEach((v) => v?.isTexture && textures.add(v));
        });
      }
    });
    const json = gltf.parser.json;
    return {
      name, loadMs: Math.round(loadMs),
      dims: [size.x, size.y, size.z], boundsMin: [box.min.x, box.min.y, box.min.z],
      meshes, triangles, vertices, bones, skinned, noUv, materials: materials.size, textures: textures.size,
      animations: gltf.animations.map((c) => ({ name: c.name, duration: c.duration })),
      extensions: json.extensionsUsed || [],
      draco: (json.extensionsUsed || []).includes("KHR_draco_mesh_compression"),
      generator: json.asset?.generator || "", nodes,
      materialsList: [...materials].map((m) => ({
        name: m.name, type: m.type,
        pbr: !!(m.isMeshStandardMaterial || m.isMeshPhysicalMaterial),
        transparent: m.transparent, emissive: !!(m.emissive && (m.emissive.r || m.emissive.g || m.emissive.b)),
      })),
    };
  }

  // --- animations -------------------------------------------------------------
  function setupAnimations(gltf) {
    if (!gltf.animations.length) { animState.duration = 0; return; }
    mixer = new THREE.AnimationMixer(gltf.scene);
    actions = gltf.animations.map((clip) => {
      const a = mixer.clipAction(clip);
      a.setLoop(animState.loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
      a.clampWhenFinished = true;
      a.enabled = true;
      a.play();
      a.paused = !animState.playing;
      return a;
    });
    animState.duration = Math.max(...gltf.animations.map((c) => c.duration));
    mixer.timeScale = animState.speed;
  }

  const animations = {
    get clips() { return asset ? asset.gltf.animations : []; },
    get state() { const a = actions.find((x) => x.enabled); return { ...animState, time: a ? a.time % (a.getClip().duration || 1) : 0 }; },
    play(name) {
      animState.playing = true;
      actions.forEach((a) => {
        if (name == null || a.getClip().name === name) { a.enabled = true; a.paused = false; if (!a.isRunning()) a.play(); }
      });
      emit("animation", animations.state);
    },
    pause() { animState.playing = false; actions.forEach((a) => (a.paused = true)); emit("animation", animations.state); },
    toggle() { animState.playing ? animations.pause() : animations.play(); },
    stop() { animState.playing = false; actions.forEach((a) => { a.reset(); a.paused = true; }); mixer?.setTime(0); emit("animation", animations.state); },
    solo(name) {
      actions.forEach((a) => { const on = name == null || a.getClip().name === name; a.enabled = on; if (on) { a.reset(); a.play(); a.paused = !animState.playing; } });
      emit("animation", animations.state);
    },
    setTime(t) {
      if (!mixer) return;
      actions.forEach((a) => { if (a.enabled) a.time = t % (a.getClip().duration || 1); });
      mixer.update(0);
      emit("animation", animations.state);
    },
    setSpeed(v) { animState.speed = v; if (mixer) mixer.timeScale = v; },
    setLoop(on) { animState.loop = on; actions.forEach((a) => a.setLoop(on ? THREE.LoopRepeat : THREE.LoopOnce, Infinity)); },
  };

  // --- framing / ground -------------------------------------------------------
  function fitGround(root) {
    const box = new THREE.Box3().setFromObject(root, true);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const span = Math.max(size.x, size.z, 0.5) * 6;
    shadowCatcher.position.set(center.x, box.min.y - 0.0005, center.z);
    shadowCatcher.scale.set(span, span, 1);
    grid.position.set(0, box.min.y - 0.001, 0);
    const gridSize = Math.max(2, Math.ceil(Math.max(size.x, size.z) * 2.5));
    grid.scale.setScalar(gridSize / 10);
    // shadows: fit the light's ortho camera to the asset size
    const r = Math.max(size.x, size.y, size.z);
    key.position.copy(center).add(new THREE.Vector3(r * 1.5, r * 3, r * 2));
    key.target.position.copy(center);
    const cam = key.shadow.camera;
    cam.left = cam.bottom = -r * 1.2; cam.right = cam.top = r * 1.2;
    cam.near = 0.01; cam.far = r * 10;
    cam.updateProjectionMatrix();
  }

  function frame(object = asset?.root, { animate = true } = {}) {
    if (!object) return;
    const box = new THREE.Box3().setFromObject(object, true);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const radius = Math.max(size.length() * 0.5, 0.05);
    const dist = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov) * 0.5) * 1.15;
    const dir = camera.position.clone().sub(controls.target).normalize();
    if (!Number.isFinite(dir.x) || dir.lengthSq() < 1e-6) dir.set(0.7, 0.5, 0.8).normalize();
    const target = center;
    const position = center.clone().add(dir.multiplyScalar(dist));
    camera.near = Math.max(radius / 200, 0.001);
    camera.far = Math.max(radius * 200, 50);
    camera.updateProjectionMatrix();
    controls.minDistance = radius * 0.05;
    controls.maxDistance = radius * 40;
    if (animate) tween(camera.position, position, controls.target, target, 350);
    else { camera.position.copy(position); controls.target.copy(target); }
    emit("frame", { object });
  }

  let tweenState = null;
  function tween(posFrom, posTo, tgtFrom, tgtTo, ms) {
    tweenState = { p0: posFrom.clone(), p1: posTo.clone(), t0: tgtFrom.clone(), t1: tgtTo.clone(), start: performance.now(), ms };
  }

  function resetView() {
    camera.position.set(2.5, 1.8, 3);
    controls.target.set(0, 0, 0);
    frame();
  }

  // --- interaction ----------------------------------------------------------
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let hovered = null, selected = null;
  let pointerDown = null;

  function pick(clientX, clientY) {
    if (!asset) return null;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObject(asset.root, true).find((h) => h.object.visible);
    return hit ? { object: hit.object, point: hit.point, distance: hit.distance } : null;
  }

  function hover(object, extra = {}) {
    if (object === hovered) { if (object) emit("hover", { object, ...extra }); return; }
    hovered = object;
    if (object) { hoverBox.box.setFromObject(object, true); hoverBox.visible = object !== selected; }
    else hoverBox.visible = false;
    emit("hover", { object, ...extra });
  }

  function select(object) {
    selected = object || null;
    if (selected) { selectBox.box.setFromObject(selected, true); selectBox.visible = true; hoverBox.visible = false; }
    else selectBox.visible = false;
    emit("select", { object: selected });
  }

  function describeObject(o) {
    if (!o) return null;
    const box = new THREE.Box3().setFromObject(o, true);
    const size = box.getSize(new THREE.Vector3());
    const mats = o.isMesh ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    const g = o.geometry;
    const tris = g ? Math.floor((g.index ? g.index.count : g.attributes.position?.count || 0) / 3) : 0;
    const path = [];
    for (let p = o; p && p !== asset?.root; p = p.parent) path.unshift(p.name || p.type);
    return {
      name: o.name, type: o.isMesh ? "mesh" : o.isBone ? "bone" : "node", path: path.join(" / "),
      dims: [size.x, size.y, size.z], triangles: tris, materials: mats.map((m) => m.name || m.type),
      position: o.position.toArray(), uv: !!g?.attributes.uv, normals: !!g?.attributes.normal,
      children: o.children.length,
    };
  }

  const el = renderer.domElement;
  el.addEventListener("pointermove", (e) => {
    const hit = pick(e.clientX, e.clientY);
    hover(hit?.object || null, { x: e.clientX, y: e.clientY });
  });
  el.addEventListener("pointerleave", () => hover(null));
  el.addEventListener("pointerdown", (e) => { pointerDown = { x: e.clientX, y: e.clientY, t: performance.now() }; });
  el.addEventListener("pointerup", (e) => {
    if (!pointerDown || e.button !== 0) return;
    if (gizmo && (gizmo.dragging || gizmo.axis)) { pointerDown = null; return; }   // a gizmo handle, not a pick
    const moved = Math.hypot(e.clientX - pointerDown.x, e.clientY - pointerDown.y);
    pointerDown = null;
    if (moved > 6) return; // it was an orbit drag, not a click
    const hit = pick(e.clientX, e.clientY);
    select(hit?.object || null);
  });
  // --- gizmo: move, turn (round the vertical) or scale (evenly) one object by hand — Studio's part editor ---------
  let gizmo = null, gizmoScale = 1;
  function setGizmo(object, mode = "translate") {
    if (!object) { gizmo?.detach(); return; }
    if (!gizmo) {
      gizmo = new TransformControls(camera, renderer.domElement);
      gizmo.addEventListener("dragging-changed", (e) => {
        controls.enabled = !e.value;
        if (e.value) { gizmoScale = gizmo.object?.scale.x || 1; emit("transform-start", { object: gizmo.object }); }
        else emit("transform-end", { object: gizmo.object });
      });
      gizmo.addEventListener("objectChange", () => {
        const o = gizmo.object;
        if (gizmo.mode === "scale") {   // even scale: the axis pulled the most sets all three
          const k = [o.scale.x, o.scale.y, o.scale.z].reduce((a, b) => (Math.abs(b - gizmoScale) > Math.abs(a - gizmoScale) ? b : a));
          o.scale.setScalar(Math.max(0.05, k));
        }
        if (selected) selectBox.box.setFromObject(selected, true);
        emit("transform", { object: o });
      });
      scene.add(gizmo.getHelper ? gizmo.getHelper() : gizmo);
    }
    gizmo.setMode(mode);
    gizmo.setSpace(mode === "scale" ? "local" : "world");
    gizmo.showX = gizmo.showZ = mode !== "rotate";
    gizmo.showY = true;
    gizmo.attach(object);
  }

  el.addEventListener("dblclick", (e) => {
    const hit = pick(e.clientX, e.clientY);
    frame(hit?.object || asset?.root);
    if (hit) select(hit.object);
  });

  // drag-and-drop: .glb/.gltf → asset, .hdr → environment
  const dropTarget = opts.dropTarget || container;
  ["dragenter", "dragover"].forEach((t) => dropTarget.addEventListener(t, (e) => { e.preventDefault(); emit("drag", { over: true }); }));
  dropTarget.addEventListener("dragleave", () => emit("drag", { over: false }));
  dropTarget.addEventListener("drop", async (e) => {
    e.preventDefault();
    emit("drag", { over: false });
    const files = [...(e.dataTransfer?.files || [])];
    const model = files.find((f) => /\.(glb|gltf)$/i.test(f.name));
    const hdr = files.find((f) => /\.hdr$/i.test(f.name));
    try {
      if (hdr) await setEnvironment(hdr);
      if (model) await load(model);
    } catch (err) { /* already reported via emit("error") */ }
  });

  // --- skeleton and UV checker ------------------------------------------------
  let skeletonHelper = null;
  function setSkeleton(on) {
    state.skeleton = on;
    if (skeletonHelper) { scene.remove(skeletonHelper); skeletonHelper.dispose(); skeletonHelper = null; }
    if (on && asset) {
      let hasBones = false;
      asset.root.traverse((o) => { if (o.isBone) hasBones = true; });
      if (!hasBones) return;
      skeletonHelper = new THREE.SkeletonHelper(asset.root);
      skeletonHelper.material.linewidth = 2;
      skeletonHelper.material.depthTest = false;
      skeletonHelper.material.transparent = true;
      skeletonHelper.material.opacity = 0.9;
      skeletonHelper.renderOrder = 10;
      scene.add(skeletonHelper);
    }
  }

  let checkerMaterial = null;
  function makeChecker() {
    const size = 512, c = document.createElement("canvas"); c.width = c.height = size;
    const g = c.getContext("2d"), n = 16, cell = size / n;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      g.fillStyle = (x + y) % 2 ? "#2b2f4a" : "#c9cfff"; g.fillRect(x * cell, y * cell, cell, cell);
    }
    g.strokeStyle = "#a78bfa"; g.lineWidth = 3; g.strokeRect(1, 1, size - 2, size - 2);
    g.fillStyle = "#fb7e8f"; g.font = "bold 40px monospace"; g.fillText("UV", 12, 46); g.fillText("→u", size - 70, size - 14);
    g.save(); g.translate(14, size - 14); g.rotate(-Math.PI / 2); g.fillText("→v", 0, 0); g.restore();
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace; tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.anisotropy = 8;
    return new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8, metalness: 0 });
  }
  function setUvChecker(on) {
    state.uvChecker = on;
    if (!asset) return;
    if (on && !checkerMaterial) checkerMaterial = makeChecker();
    asset.root.traverse((o) => {
      if (!o.isMesh) return;
      if (on) { if (!o.userData.mgMaterial) o.userData.mgMaterial = o.material; o.material = checkerMaterial; }
      else if (o.userData.mgMaterial) { o.material = o.userData.mgMaterial; delete o.userData.mgMaterial; }
    });
  }

  // --- view state -------------------------------------------------------------
  const state = { wireframe: false, skeleton: false, uvChecker: false };
  function setWireframe(on) {
    state.wireframe = on;
    asset?.root.traverse((o) => {
      if (!o.isMesh) return;
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => (m.wireframe = on));
    });
  }
  function setGrid(on) { grid.visible = on; }
  function setShadows(on) { shadowsWanted = on; applyQuality(tier); }
  function setExposure(v) { renderer.toneMappingExposure = v; }
  function setBackgroundColor(hex) { opts.background = hex; applyBackground(); }
  function setShowEnvironment(on) { opts.showEnvironment = on; applyBackground(); }
  function screenshot(type = "image/png") {
    if (glowComposer && hasGlow) renderGlow();
    if (composer) composer.render(0); else renderer.render(scene, camera);
    return renderer.domElement.toDataURL(type);
  }

  // --- quality tiers ---------------------------------------------------------
  let composer = null, bloomPass = null, aoPass = null;
  // Selective bloom: a second composer renders only emissive light (every other surface black) and blurs it; the
  // result is added before tone mapping. Bright but unlit surfaces (white sails, walls) no longer glow, and the extra
  // pass is skipped entirely for assets without emissive materials.
  let glowComposer = null, glowMix = null, hasGlow = false;
  const GLOW_BLACK = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const GLOW_BG = new THREE.Color(0x000000);
  const glowMaterials = new WeakMap();
  const isLit = (m) => m && m.emissive && (m.emissiveIntensity ?? 1) > 0 && m.emissive.r + m.emissive.g + m.emissive.b > 0;
  function detectGlow(root) {
    let found = false;
    root?.traverse((o) => { if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { if (isLit(m)) found = true; }); });
    return found;
  }
  function glowMaterial(m) {
    let g = glowMaterials.get(m);
    if (!g) {
      // the halo comes from the light's colour at most at full strength: a very bright glow (goo at 2×) would
      // otherwise bloom over the whole object and wash out the colours next to it
      g = isLit(m) ? new THREE.MeshBasicMaterial({ color: m.emissive.clone().multiplyScalar(Math.min(m.emissiveIntensity ?? 1, 1)),
        map: m.emissiveMap || null, side: m.side, toneMapped: false }) : GLOW_BLACK;
      glowMaterials.set(m, g);
    }
    return g;
  }
  function renderGlow() {
    const swapped = [], hidden = [];
    (function walk(o) {
      if (!o.visible) return;
      if (o.isMesh) { swapped.push([o, o.material]); o.material = Array.isArray(o.material) ? o.material.map(glowMaterial) : glowMaterial(o.material); }
      else if (o.isLine || o.isPoints || o.isSprite) { hidden.push(o); o.visible = false; return; }
      o.children.forEach(walk);
    })(scene);
    const bg = scene.background;
    scene.background = GLOW_BG;
    glowComposer.render();
    scene.background = bg;
    swapped.forEach(([o, m]) => { o.material = m; });
    hidden.forEach((o) => { o.visible = true; });
  }
  renderer.info.autoReset = false;   // post-processing passes would otherwise leave only the last full-screen quad in the counters
  let shadowsWanted = opts.shadows;

  function buildComposer(q) {
    if (composer) { composer.dispose(); composer = null; }
    if (glowComposer) { glowComposer.dispose(); glowComposer = null; glowMix = null; bloomPass = null; }
    if (!(q.bloom || q.ao)) return;
    const w = container.clientWidth || innerWidth, h = container.clientHeight || innerHeight;
    const target = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: q.msaa });
    composer = new EffectComposer(renderer, target);
    composer.setPixelRatio(renderer.getPixelRatio());
    composer.setSize(w, h);
    composer.addPass(new RenderPass(scene, camera));
    aoPass = q.ao ? new GTAOPass(scene, camera, w, h) : null;
    if (aoPass) { aoPass.blendIntensity = 0.8; composer.addPass(aoPass); }
    if (q.bloom) {
      glowComposer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType }));
      glowComposer.renderToScreen = false;
      glowComposer.setPixelRatio(renderer.getPixelRatio());
      glowComposer.setSize(w, h);
      glowComposer.addPass(new RenderPass(scene, camera));
      bloomPass = new UnrealBloomPass(new THREE.Vector2(w, h), 0.35, 0.25, 0.0);   // input is emissive light only: a soft halo
      glowComposer.addPass(bloomPass);
      glowMix = new ShaderPass(new THREE.ShaderMaterial({
        uniforms: { tDiffuse: { value: null }, glow: { value: glowComposer.renderTarget2.texture } },
        vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
        fragmentShader: "uniform sampler2D tDiffuse; uniform sampler2D glow; varying vec2 vUv;"
          + " void main() { gl_FragColor = texture2D(tDiffuse, vUv) + vec4(texture2D(glow, vUv).rgb, 0.0); }",
      }), "tDiffuse");
      glowMix.enabled = hasGlow;
      composer.addPass(glowMix);
    }
    composer.addPass(new OutputPass());   // tone mapping + sRGB at the end
  }

  function applyQuality(next) {
    tier = QUALITY[next] ? next : detectedTier;
    const q = QUALITY[tier];
    renderer.setPixelRatio(Math.min(devicePixelRatio, q.pixel_ratio, opts.pixelRatioCap) * q.render_scale);
    const shadows = shadowsWanted && q.shadows !== "off";
    renderer.shadowMap.enabled = shadows;
    renderer.shadowMap.type = q.shadows === "soft" ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
    shadowCatcher.visible = shadows;
    if (q.shadow_map) {
      key.shadow.mapSize.set(q.shadow_map, q.shadow_map);
      if (key.shadow.map) { key.shadow.map.dispose(); key.shadow.map = null; }
    }
    scene.traverse((o) => { if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => (m.needsUpdate = true)); });
    buildComposer(q);
    resize();
    emit("quality", { tier, detected: detectedTier, ...q });
  }

  async function setQuality(next) {
    const before = tier;
    applyQuality(next === "auto" ? detectedTier : next);
    if (asset && typeof asset.source === "string" && tier !== before && opts.variants) {
      await load(asset.source);   // pick this tier's asset variant (if any)
    }
  }

  // --- loop ------------------------------------------------------------------
  const clock = new THREE.Clock();
  let stats = { fps: 0, calls: 0, triangles: 0 };
  let fpsAcc = 0, fpsN = 0, fpsLast = performance.now();
  function resize() {
    const w = container.clientWidth || innerWidth, h = container.clientHeight || innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); }
    if (glowComposer) { glowComposer.setPixelRatio(renderer.getPixelRatio()); glowComposer.setSize(w, h); }
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
  }
  new ResizeObserver(resize).observe(container);
  resize();

  let running = true;
  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    const dt = clock.getDelta();
    if (tweenState) {
      const k = Math.min(1, (performance.now() - tweenState.start) / tweenState.ms);
      const e = 1 - Math.pow(1 - k, 3);
      camera.position.lerpVectors(tweenState.p0, tweenState.p1, e);
      controls.target.lerpVectors(tweenState.t0, tweenState.t1, e);
      if (k >= 1) tweenState = null;
    }
    controls.update();
    if (mixer && animState.playing) { mixer.update(dt); emit("tick", animations.state); }
    if (selected && mixer) selectBox.box.setFromObject(selected, true);
    if (hovered && mixer && hoverBox.visible) hoverBox.box.setFromObject(hovered, true);
    if (glowMix) glowMix.enabled = hasGlow;
    if (glowComposer && hasGlow) renderGlow();   // before the reset: stats count the main pass only
    renderer.info.reset();
    if (composer) composer.render(dt); else renderer.render(scene, camera);
    fpsN++; fpsAcc += dt;
    if (performance.now() - fpsLast > 500) {
      stats = { fps: Math.round(fpsN / fpsAcc), calls: renderer.info.render.calls, triangles: renderer.info.render.triangles };
      fpsN = 0; fpsAcc = 0; fpsLast = performance.now();
      emit("stats", stats);
    }
  }
  applyQuality(tier);
  loop();
  setEnvironment(opts.environment).catch((error) => { emit("error", { name: "environment", error }); setEnvironment("room"); });

  return {
    THREE, renderer, scene, camera, controls,
    load, unload, frame, resetView, select, hover, describeObject, setGizmo, get model() { return asset?.root || null; },
    get asset() { return asset; }, get selected() { return selected; }, get hovered() { return hovered; }, get stats() { return stats; },
    animations, setEnvironment, setShowEnvironment, setBackgroundColor, setWireframe, setGrid, setShadows, setExposure, screenshot,
    setSkeleton, setUvChecker, get viewState() { return { ...state }; },
    setQuality, get quality() { return tier; }, get detectedQuality() { return detectedTier; }, QUALITY,
    get environmentMode() { return envMode; },
    on(name, cb) { listeners.set(name, [...(listeners.get(name) || []), cb]); return () => this.off(name, cb); },
    off(name, cb) { listeners.set(name, (listeners.get(name) || []).filter((f) => f !== cb)); },
    dispose() { running = false; unload(); controls.dispose(); pmrem.dispose(); draco.dispose(); ktx2.dispose(); renderer.dispose(); renderer.domElement.remove(); },
  };
}
