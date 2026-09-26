// MeshGate — demo page: UI wrapper around meshgate-viewer.js.
// All 3D logic lives in the library; this file only handles the DOM, URL parameters and hotkeys.
import { createViewer } from "./meshgate-viewer.js";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const glbUrl = params.get("glb") || "/samples/meshgate_demo.glb";
const hdrUrl = params.get("hdr");
const envParam = params.get("env");

const viewer = createViewer($("app"), {
  quality: params.get("quality") || "auto",
  environment: hdrUrl || envParam || "room",
  autoplay: params.get("autoplay") !== "0",
  dropTarget: document.body,
});
window.meshgate = viewer; // for debugging from the console

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
const fmt = (v, d = 2) => Number(v).toFixed(d);
const dims = (d) => d ? `${fmt(d[0])} × ${fmt(d[1])} × ${fmt(d[2])} m` : "—";
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let toastTimer;
function toast(msg, isErr = false, ms = 4000) {
  const t = $("toast");
  t.textContent = msg; t.className = isErr ? "err" : ""; t.style.display = "block";
  clearTimeout(toastTimer);
  if (ms) toastTimer = setTimeout(() => (t.style.display = "none"), ms);
}
function dl(rows) {
  return rows.map(([k, v, cls]) => `<dt>${esc(k)}</dt><dd${cls ? ` class="${cls}"` : ""}>${v}</dd>`).join("");
}

// ---------------------------------------------------------------------------
// Asset
// ---------------------------------------------------------------------------
viewer.on("loadstart", ({ name }) => {
  $("asset-name").textContent = `loading ${name}…`;   // the status row is gone after the first load — use the header
  $("progress").style.width = "10%";
});
viewer.on("progress", ({ loaded, total }) => { if (total) $("progress").style.width = `${Math.round((loaded / total) * 100)}%`; });
viewer.on("error", ({ name, error }) => {
  if (name === "environment") { toast(`HDRI failed to load (${error?.message || error}) — switched to the studio environment`, true, 6000); $("env").value = "room"; $("hdr-row").style.display = "none"; return; }
  $("progress").style.width = "0";
  $("asset-info").innerHTML = dl([["status", `not loaded`, "warn"]]);
  toast(`Failed to load ${name}: ${error?.message || error}. Export the asset: blender -b samples/meshgate_demo.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_demo.glb`, true, 0);
});
viewer.on("load", (info) => {
  $("progress").style.width = "100%";
  setTimeout(() => ($("progress").style.width = "0"), 400);
  $("asset-name").textContent = info.name;
  const badPbr = info.materialsList.filter((m) => !m.pbr).length;
  $("asset-info").innerHTML = dl([
    ["dimensions", dims(info.dims)],
    ["meshes", `${info.meshes} · ${info.triangles.toLocaleString("en")} tris · ${info.vertices.toLocaleString("en")} verts`],
    ["materials", `${info.materials}${badPbr ? ` (${badPbr} non-PBR)` : " · all PBR"}`, badPbr ? "warn" : "ok"],
    ["file", `${esc(info.file)}${info.variant !== "canonical" ? ` <span class="chip">${esc(info.variant)} variant</span>` : ""}`],
    ["textures", String(info.textures)],
    ["UV", info.noUv ? `missing on ${info.noUv} of ${info.meshes} meshes` : "present on all meshes", info.noUv ? "warn" : "ok"],
    ["skeleton", info.bones ? `${info.bones} bones · ${info.skinned} skinned` : "none"],
    ["animations", info.animations.length ? info.animations.map((a) => `${esc(a.name)} ${fmt(a.duration, 1)}s`).join(", ") : "none"],
    ["Draco", info.draco ? "yes" : "no"],
    ["load time", `${info.loadMs} ms`],
    ["generator", esc(info.generator || "—")],
  ]);
  $("asset-ext").innerHTML = info.extensions.length ? info.extensions.map((e) => `<span class="chip">${esc(e)}</span>`).join("") : `<span class="chip dim">no extensions</span>`;
  buildTree(info.nodes);
  buildClips(info.animations);
  document.title = `MeshGate — ${info.name}`;
  toast(`Loaded: ${info.name} · ${info.triangles.toLocaleString("en")} tris · ${info.loadMs} ms`);
});

// ---------------------------------------------------------------------------
// Object tree and selection
// ---------------------------------------------------------------------------
const treeEl = $("tree");
let treeRows = new Map();
function buildTree(nodes) {
  treeEl.innerHTML = "";
  treeRows = new Map();
  $("tree-count").textContent = nodes.length;
  const root = viewer.asset.root;
  const depthOf = (o) => { let d = 0; for (let p = o.parent; p && p !== root; p = p.parent) d++; return d; };
  for (const n of nodes) {
    const row = document.createElement("div");
    row.className = "node";
    row.style.paddingLeft = `${6 + depthOf(n.object) * 12}px`;
    const tris = n.object.geometry ? Math.floor((n.object.geometry.index?.count || n.object.geometry.attributes.position?.count || 0) / 3) : "";
    row.innerHTML = `<span class="t">${n.type}</span><span>${esc(n.name)}</span><span class="tri">${tris}</span>`;
    row.addEventListener("click", () => viewer.select(n.object));
    row.addEventListener("dblclick", () => viewer.frame(n.object));
    row.addEventListener("mouseenter", () => viewer.hover(n.object));
    row.addEventListener("mouseleave", () => viewer.hover(null));
    treeEl.appendChild(row);
    treeRows.set(n.object, row);
  }
}

viewer.on("select", ({ object }) => {
  treeRows.forEach((row, o) => row.classList.toggle("selected", o === object));
  if (!object) {
    $("sel-name").textContent = "nothing";
    $("sel-info").innerHTML = dl([["", `<span style="color:var(--muted)">hover and click an object · double-click to focus</span>`]]);
    return;
  }
  const d = viewer.describeObject(object);
  $("sel-name").textContent = d.name || d.type;
  $("sel-info").innerHTML = dl([
    ["path", esc(d.path)],
    ["type", `${d.type}${d.children ? ` · ${d.children} children` : ""}`],
    ["dimensions", dims(d.dims)],
    ...(d.type === "mesh" ? [
      ["tris", d.triangles.toLocaleString("en")],
      ["material", d.materials.map(esc).join(", ") || "—"],
      ["UV / normals", `${d.uv ? "yes" : "no"} / ${d.normals ? "yes" : "no"}`, d.uv && d.normals ? "ok" : "warn"],
    ] : []),
    ["position", d.position.map((v) => fmt(v, 3)).join(", ")],
  ]);
  treeRows.get(object)?.scrollIntoView({ block: "nearest" });
});

const tip = $("tip");
viewer.on("hover", ({ object, x, y }) => {
  if (!object || x == null) { tip.style.display = "none"; document.body.style.cursor = ""; return; }
  tip.textContent = object.name || object.type;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`; tip.style.display = "block";
  document.body.style.cursor = "pointer";
});
$("btn-frame-sel").addEventListener("click", () => viewer.frame(viewer.selected || undefined));
$("btn-clear-sel").addEventListener("click", () => viewer.select(null));

// ---------------------------------------------------------------------------
// Animations
// ---------------------------------------------------------------------------
const clipsEl = $("clips");
let soloClip = null;
function buildClips(list) {
  clipsEl.innerHTML = "";
  soloClip = null;
  $("anim-count").textContent = list.length;
  $("anim-section").open = list.length > 0;
  if (!list.length) { clipsEl.innerHTML = `<span style="color:var(--muted)">no animations in this asset</span>`; }
  for (const c of list) {
    const row = document.createElement("div");
    row.className = "clip";
    row.innerHTML = `<button title="Solo this animation">${esc(c.name)}</button><small>${fmt(c.duration, 2)} s</small>`;
    row.querySelector("button").addEventListener("click", (e) => {
      soloClip = soloClip === c.name ? null : c.name;
      viewer.animations.solo(soloClip);
      if (!viewer.animations.state.playing) viewer.animations.play();
      [...clipsEl.querySelectorAll("button")].forEach((b) => b.classList.toggle("active", soloClip !== null && b.textContent === soloClip));
    });
    clipsEl.appendChild(row);
  }
  const s = viewer.animations.state;
  $("timeline").max = s.duration || 1;
  updateAnimUI(s);
}
function updateAnimUI(s) {
  $("btn-play").textContent = s.playing ? "⏸ Pause" : "▶ Play";
  if (!scrubbing) $("timeline").value = s.time;
  $("time").textContent = `${fmt(s.time)} / ${fmt(s.duration)} s`;
}
let scrubbing = false;
viewer.on("tick", updateAnimUI);
viewer.on("animation", updateAnimUI);
$("btn-play").addEventListener("click", () => viewer.animations.toggle());
$("btn-stop").addEventListener("click", () => viewer.animations.stop());
$("btn-all").addEventListener("click", () => { soloClip = null; viewer.animations.solo(null); viewer.animations.play(); [...clipsEl.querySelectorAll("button")].forEach((b) => b.classList.remove("active")); });
$("chk-loop").addEventListener("change", (e) => viewer.animations.setLoop(e.target.checked));
$("timeline").addEventListener("pointerdown", () => (scrubbing = true));
$("timeline").addEventListener("input", (e) => { viewer.animations.setTime(parseFloat(e.target.value)); });
addEventListener("pointerup", () => (scrubbing = false));
$("speed").addEventListener("input", (e) => { viewer.animations.setSpeed(parseFloat(e.target.value)); $("speed-val").textContent = `${fmt(e.target.value, 1)}×`; });

// ---------------------------------------------------------------------------
// View
// ---------------------------------------------------------------------------
$("env").value = hdrUrl ? "hdr" : envParam === "none" ? "none" : "room";
$("hdr-row").style.display = hdrUrl ? "flex" : "none";
if (hdrUrl) $("hdr-url").value = hdrUrl;
$("env").addEventListener("change", async (e) => {
  const v = e.target.value;
  $("hdr-row").style.display = v === "hdr" ? "flex" : "none";
  if (v !== "hdr") await viewer.setEnvironment(v);
});
async function loadHdr() {
  const url = $("hdr-url").value.trim();
  if (!url) return;
  try { await viewer.setEnvironment(url); toast("HDRI loaded"); } catch (err) { toast(`HDRI failed to load: ${err.message || err}`, true); }
}
$("btn-hdr").addEventListener("click", loadHdr);
$("hdr-url").addEventListener("keydown", (e) => e.key === "Enter" && loadHdr());
$("chk-envbg").addEventListener("change", (e) => viewer.setShowEnvironment(e.target.checked));
$("chk-grid").addEventListener("change", (e) => viewer.setGrid(e.target.checked));
$("chk-shadows").addEventListener("change", (e) => viewer.setShadows(e.target.checked));
$("chk-wire").addEventListener("change", (e) => viewer.setWireframe(e.target.checked));
$("chk-skel").addEventListener("change", (e) => viewer.setSkeleton(e.target.checked));
$("chk-uv").addEventListener("change", (e) => viewer.setUvChecker(e.target.checked));
$("exposure").addEventListener("input", (e) => { viewer.setExposure(parseFloat(e.target.value)); $("exposure-val").textContent = fmt(e.target.value); });
$("btn-reset").addEventListener("click", () => viewer.resetView());
$("btn-shot").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = viewer.screenshot();
  a.download = `${(viewer.asset?.info.name || "meshgate").replace(/\.(glb|gltf)$/i, "")}.png`;
  a.click();
});

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------
async function loadUrl() {
  const url = $("glb-url").value.trim();
  if (!url) return;
  history.replaceState(null, "", `?glb=${encodeURIComponent(url)}`);
  try { await viewer.load(url); } catch (_) { /* toast already shown */ }
}
$("btn-load").addEventListener("click", loadUrl);
$("glb-url").addEventListener("keydown", (e) => e.key === "Enter" && loadUrl());
$("file").addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  try { if (/\.hdr$/i.test(f.name)) await viewer.setEnvironment(f); else await viewer.load(f); } catch (_) {}
  e.target.value = "";
});
viewer.on("drag", ({ over }) => $("drop").classList.toggle("over", over));

// ---------------------------------------------------------------------------
// Stats, panel, hotkeys
// ---------------------------------------------------------------------------
function showQuality() {
  const sel = $("quality");
  if (!sel) return;
  const auto = params.get("quality") ? false : true;
  sel.value = auto && viewer.quality === viewer.detectedQuality ? "auto" : viewer.quality;
  sel.options[0].textContent = `Auto (${viewer.QUALITY[viewer.detectedQuality].label})`;
  $("st-tier").textContent = viewer.QUALITY[viewer.quality].label;
}
viewer.on("quality", showQuality);
$("quality").addEventListener("change", async (e) => { params.set("quality", e.target.value); await viewer.setQuality(e.target.value); showQuality(); });
showQuality();

viewer.on("stats", (s) => { $("st-fps").textContent = s.fps; $("st-calls").textContent = s.calls; $("st-tris").textContent = s.triangles.toLocaleString("en"); });

function togglePanel(force) {
  const hidden = $("panel").classList.toggle("hidden", force);
  $("toggle-panel").classList.toggle("show", hidden);
}
$("btn-hide").addEventListener("click", () => togglePanel(true));
$("toggle-panel").addEventListener("click", () => togglePanel(false));

addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea")) return;
  switch (e.key) {
    case " ": e.preventDefault(); viewer.animations.toggle(); break;
    case "f": case "F": viewer.frame(viewer.selected || undefined); break;
    case "g": case "G": $("chk-grid").click(); break;
    case "w": case "W": $("chk-wire").click(); break;
    case "s": case "S": $("chk-skel").click(); break;
    case "u": case "U": $("chk-uv").click(); break;
    case "r": case "R": viewer.resetView(); break;
    case "Escape": viewer.select(null); break;
    case "Tab": e.preventDefault(); togglePanel(); break;
  }
});

// ---------------------------------------------------------------------------
// Samples gallery (samples/index.json)
// ---------------------------------------------------------------------------
async function loadGallery() {
  try {
    const res = await fetch("/samples/index.json", { cache: "no-store" });
    if (!res.ok) return;
    const { assets, packs = [] } = await res.json();
    const addChips = (list, base, label) => {
      if (label) {
        const h = document.createElement("div");
        h.className = "gallery-group";
        h.textContent = label;
        $("gallery").appendChild(h);
      }
      for (const a of list) {
        const file = `${base}${a.file}`;
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = a.title;
        chip.title = (a.tags || [a.tris != null ? `${a.tris} tris` : "", ...(a.clips || [])]).filter(Boolean).join(" · ");
        chip.dataset.file = a.file;
        chip.addEventListener("click", async () => {
          history.replaceState(null, "", `?glb=/samples/${file}`);
          try { await viewer.load(`/samples/${file}`); } catch (_) {}
        });
        $("gallery").appendChild(chip);
      }
    };
    addChips(assets, "", null);
    let total = assets.length;
    for (const pack of packs) {
      try {
        const r = await fetch(`/samples/${pack.path}/index.json`, { cache: "no-store" });
        if (!r.ok) continue;
        const idx = await r.json();
        addChips(idx.assets, `${pack.path}/`, pack.title);
        total += idx.assets.length;
      } catch (_) { /* pack missing — skip */ }
    }
    $("gallery-count").textContent = total;
    markGallery();
  } catch (_) { /* no gallery — fine */ }
}
function markGallery() {
  const name = viewer.asset?.info.name;
  [...$("gallery").children].forEach((c) => c.classList.toggle("active", c.dataset.file === name));
}
viewer.on("load", markGallery);
loadGallery();

// Start
viewer.load(glbUrl).catch(() => {});
