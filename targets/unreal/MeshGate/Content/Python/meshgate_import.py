"""MeshGate — import canonical assets into Unreal Engine 5 and build the demo level.

From the editor (Python console or Tools → MeshGate):
    import meshgate_import
    meshgate_import.import_samples("/absolute/path/to/meshgate/samples")
    meshgate_import.build_demo_level()

Headless (the pythonscript commandlet does not load levels, so use -ExecutePythonScript):
    UnrealEditor-Cmd Project.uproject -ExecutePythonScript="<plugin>/Content/Python/meshgate_import.py --samples /path/to/samples --level"

What it does:
  • GLB → Interchange with a MeshGate pipeline (UE 5.3+): static and skeletal meshes, PBR materials, animations;
  • FBX → Interchange when UE routes FBX through it (default since 5.5), otherwise the legacy FBX importer;
    `<name>.unreal.fbx` (UCX_ collision from the Blender add-on) is preferred over `<name>.fbx`;
  • characters are Skeletal Meshes; bones follow Unity Humanoid names, so an IK Rig / IK Retargeter to
    the UE5 Mannequin maps by name (see meshgate_retarget.md);
  • every source file goes through the MeshGate validator first, using the editor's own Python;
  • builds /Game/MeshGate/MeshGateDemo with a sun, sky light and every sample in the web/Unity/Godot layout.

Checked against the generated Unreal Python API of UE 5.4, 5.5 and 5.6 (tests/unreal/check_api.py).
Not yet run inside a live editor.
"""

from __future__ import annotations

import os
import subprocess
import sys

import unreal

DEST = "/Game/MeshGate"
SAMPLES = ["meshgate_demo", "meshgate_hero", "meshgate_lantern", "meshgate_barrel", "meshgate_drone"]
SKELETAL = {"meshgate_hero"}
LAYOUT = {  # name → (x, y, z) in UE centimeters (Z-up, left-handed); same layout as the other targets
    "meshgate_demo": (0, 0, 0),
    "meshgate_hero": (0, 160, 0),
    "meshgate_lantern": (-140, -120, 100),
    "meshgate_barrel": (0, -130, 0),
    "meshgate_drone": (140, -120, 0),
}
_PIPELINE_TMP = f"{DEST}/_TmpPipeline"

# Quality tiers — mirrors the "render" part of core/profiles.json (tests/check_profiles.py keeps them in sync).
QUALITY = {
    "mobile-low": {"render_scale": 0.75, "msaa": 0, "shadows": "off", "shadow_distance": 0, "ao": False, "bloom": False},
    "mobile-mid": {"render_scale": 0.9, "msaa": 2, "shadows": "hard", "shadow_distance": 15, "ao": False, "bloom": False},
    "mobile-high": {"render_scale": 1.0, "msaa": 4, "shadows": "soft", "shadow_distance": 30, "ao": False, "bloom": True},
    "pc": {"render_scale": 1.0, "msaa": 4, "shadows": "soft", "shadow_distance": 80, "ao": True, "bloom": True},
}
# Unreal scalability levels per tier (0 Low … 3 Epic); mobile devices additionally use Device Profiles.
_SCALABILITY = {"mobile-low": 0, "mobile-mid": 1, "mobile-high": 2, "pc": 3}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _message(text: str) -> None:
    unreal.log_error(f"MeshGate: {text}")
    try:
        unreal.EditorDialog.show_message(unreal.Text("MeshGate"), unreal.Text(text), unreal.AppMsgType.OK)
    except Exception:  # noqa: BLE001 — no UI in commandlets
        pass


def engine_version() -> tuple[int, int]:
    raw = unreal.SystemLibrary.get_engine_version()  # "5.5.4-12345+++UE5+Release-5.5"
    try:
        major, minor = raw.split("-")[0].split(".")[:2]
        return int(major), int(minor)
    except ValueError:
        return (5, 0)


def find_repo_root(start: str) -> str | None:
    d = os.path.abspath(start)
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "core", "validate_glb.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def samples_dir(explicit: str | None = None) -> str | None:
    """explicit path → $MESHGATE_SAMPLES → <repo>/samples when the plugin lives inside a MeshGate checkout."""
    candidates = [explicit, os.environ.get("MESHGATE_SAMPLES")]
    root = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
    if root:
        candidates.append(os.path.join(root, "samples"))
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    _message("samples folder not found — pass it: import_samples('/path/to/meshgate/samples') or set MESHGATE_SAMPLES")
    return None


def _python() -> str:
    """The editor's embedded interpreter (sys.executable inside Unreal is the editor binary)."""
    if hasattr(unreal, "get_interpreter_executable_path"):
        return unreal.get_interpreter_executable_path()
    return "python3"


def validate(path: str, strict: bool = False) -> bool:
    root = find_repo_root(os.path.dirname(path)) or find_repo_root(os.path.dirname(os.path.abspath(__file__)))
    if not root:
        unreal.log_warning("MeshGate: MeshGate repository not found next to the file — skipping validation")
        return True
    script = "validate_fbx.py" if path.lower().endswith(".fbx") else "validate_glb.py"
    cmd = [_python(), os.path.join(root, "core", script), path] + (["--strict"] if strict else [])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:  # noqa: BLE001
        unreal.log_warning(f"MeshGate: validator failed to start: {exc}")
        return True
    unreal.log(p.stdout)
    if p.returncode != 0:
        unreal.log_error(f"MeshGate: {os.path.basename(path)} does not satisfy the contract (code {p.returncode})")
    return p.returncode == 0


def interchange_handles_fbx() -> bool:
    try:
        return unreal.SystemLibrary.get_console_variable_bool_value("Interchange.FeatureFlags.Import.FBX")
    except Exception:  # noqa: BLE001
        return engine_version() >= (5, 5)


def _assets_in(path: str) -> list[str]:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        return []
    return list(unreal.EditorAssetLibrary.list_assets(path, recursive=True, include_folder=False))


# ----------------------------------------------------------------------------
# Interchange (UE 5.3+)
# ----------------------------------------------------------------------------

def _set(obj, name: str, value, *alternatives: str) -> bool:
    """Set the first property that exists in this engine version (names move between releases)."""
    for n in (name, *alternatives):
        if hasattr(obj, n):
            setattr(obj, n, value)
            return True
    return False


def _meshgate_pipeline(gltf: bool, skeletal: bool, collision: bool):
    """Duplicate Epic's default assets pipeline and apply the MeshGate contract."""
    source = "/Interchange/Pipelines/DefaultGLTFAssetsPipeline" if gltf else "/Interchange/Pipelines/DefaultAssetsPipeline"
    target = f"{_PIPELINE_TMP}/MeshGatePipeline"
    if unreal.EditorAssetLibrary.does_asset_exist(target):
        unreal.EditorAssetLibrary.delete_asset(target)
    pipeline = unreal.EditorAssetLibrary.duplicate_asset(source, target)
    if pipeline is None:
        raise RuntimeError(f"cannot duplicate {source} — is the Interchange plugin enabled?")

    force = unreal.InterchangeForceMeshType
    common = pipeline.common_meshes_properties
    _set(common, "force_all_mesh_as_type", force.IFMT_SKELETAL_MESH if skeletal else force.IFMT_NONE)
    _set(common, "auto_detect_mesh_type", not skeletal)       # animated props (drone rotors) → rigid skeletal
    _set(common, "import_lods", True)

    mesh = pipeline.mesh_pipeline
    _set(mesh, "combine_static_meshes", False)                # keep crate_lid, rotor_0 … as separate meshes
    _set(mesh, "import_collision_according_to_mesh_name", True)   # UCX_/UBX_/UCP_/USP_ from the Blender add-on
    _set(mesh, "collision", collision, "import_collision")    # 5.5+: collision; 5.3/5.4: import_collision

    skel = pipeline.common_skeletal_meshes_and_animations_properties
    _set(skel, "use_t0_as_ref_pose", False)                   # contract: rest pose is the bind (T-) pose

    _set(pipeline.animation_pipeline, "import_animations", True)
    _set(pipeline.material_pipeline, "import_materials", True)
    _set(pipeline.material_pipeline.texture_pipeline, "import_textures", True)
    return pipeline


def import_interchange(src: str, dest: str, skeletal: bool = False, collision: bool = True) -> list[str]:
    gltf = src.lower().endswith((".glb", ".gltf"))
    pipeline = _meshgate_pipeline(gltf, skeletal, collision)
    params = unreal.ImportAssetParameters()
    params.is_automated = True
    params.replace_existing = True
    params.override_pipelines.append(unreal.SoftObjectPath(pipeline.get_path_name()))
    if gltf:
        params.override_pipelines.append(unreal.SoftObjectPath("/Interchange/Pipelines/DefaultGLTFPipeline"))
    manager = unreal.InterchangeManager.get_interchange_manager_scripted()
    result = manager.import_asset(dest, unreal.InterchangeManager.create_source_data(src), params)
    try:
        unreal.EditorAssetLibrary.delete_directory(_PIPELINE_TMP)
    except Exception:  # noqa: BLE001
        pass
    if result is False or result is None:   # bool on 5.3/5.4, list of objects (or None) on 5.5+
        unreal.log_warning(f"MeshGate: Interchange reported no result for {os.path.basename(src)}")
    return _assets_in(dest)


# ----------------------------------------------------------------------------
# legacy FBX importer (UE 5.0–5.4 default, or Interchange FBX switched off)
# ----------------------------------------------------------------------------

def import_legacy_fbx(src: str, dest: str, skeletal: bool = False, collision: bool = True) -> list[str]:
    ui = unreal.FbxImportUI()
    ui.set_editor_property("automated_import_should_detect_type", False)   # we force the type below
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_materials", True)
    ui.set_editor_property("import_textures", True)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("import_as_skeletal", skeletal)
    ui.set_editor_property("mesh_type_to_import",
                           unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
    if skeletal:
        sk = ui.get_editor_property("skeletal_mesh_import_data")
        sk.set_editor_property("import_morph_targets", True)
        sk.set_editor_property("use_t0_as_ref_pose", False)   # contract: rest pose is the bind (T-) pose
    else:
        sm = ui.get_editor_property("static_mesh_import_data")
        sm.set_editor_property("combine_meshes", False)
        sm.set_editor_property("generate_lightmap_u_vs", True)
        sm.set_editor_property("auto_generate_collision", collision)   # ignored when UCX_ meshes exist
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return list(task.get_editor_property("imported_object_paths") or [])


# ----------------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------------

def import_file(src: str, dest: str, skeletal: bool = False, collision: bool = True, check: bool = True) -> list[str]:
    """Import one GLB/FBX into `dest` (a /Game/... folder). Returns imported asset paths."""
    if check and not validate(src):
        return []
    use_interchange = hasattr(unreal, "InterchangeManager") and (
        src.lower().endswith((".glb", ".gltf")) or interchange_handles_fbx())
    if use_interchange:
        return import_interchange(src, dest, skeletal, collision)
    if src.lower().endswith(".fbx"):
        return import_legacy_fbx(src, dest, skeletal, collision)
    _message(f"{os.path.basename(src)}: glTF import needs UE 5.3+ (Interchange)")
    return []


def import_samples(samples: str | None = None) -> dict:
    """GLB of every sample into /Game/MeshGate/<name>; FBX (prefers <name>.unreal.fbx) into /Game/MeshGate/<name>_fbx."""
    folder = samples_dir(samples)
    if not folder:
        return {}
    result = {}
    for name in SAMPLES:
        skeletal = name in SKELETAL
        glb = os.path.join(folder, name + ".glb")
        if os.path.isfile(glb):
            result[name] = import_file(glb, f"{DEST}/{name}", skeletal)
        for fbx in (os.path.join(folder, name + ".unreal.fbx"), os.path.join(folder, name + ".fbx")):
            if os.path.isfile(fbx):
                result[name + "_fbx"] = import_file(fbx, f"{DEST}/{name}_fbx", skeletal)
                break
    unreal.log(f"MeshGate: imported {sum(len(v) for v in result.values())} assets from {folder}")
    return result


def apply_quality(tier: str) -> None:
    """Set the editor/game scalability for a MeshGate tier: sg.* groups, screen percentage, shadows, AO, bloom, MSAA."""
    if tier not in QUALITY:
        _message(f"unknown quality tier {tier!r}; known: {', '.join(QUALITY)}")
        return
    q, level = QUALITY[tier], _SCALABILITY[tier]
    commands = [f"sg.{g} {level}" for g in ("ViewDistanceQuality", "AntiAliasingQuality", "ShadowQuality", "GlobalIlluminationQuality",
                                            "ReflectionQuality", "PostProcessQuality", "TextureQuality", "EffectsQuality",
                                            "FoliageQuality", "ShadingQuality")]
    commands += [f"r.ScreenPercentage {int(q['render_scale'] * 100)}",
                 f"r.ShadowQuality {0 if q['shadows'] == 'off' else (2 if q['shadows'] == 'hard' else 5)}",
                 f"r.AmbientOcclusionLevels {-1 if q['ao'] else 0}",
                 f"r.BloomQuality {5 if q['bloom'] else 0}",
                 f"r.MSAACount {max(1, q['msaa'])}"]
    for cmd in commands:
        unreal.SystemLibrary.execute_console_command(None, cmd)
    unreal.log(f"MeshGate: quality tier {tier} applied ({len(commands)} console variables)")


def import_pack(folder: str, dest_root: str = f"{DEST}/Packs", profile: str | None = None) -> dict:
    """Import an asset pack exported by the MeshGate Blender add-on (a folder with index.json and <asset>.glb/.fbx).

    Per asset: `<name>.<profile>.glb` when a quality tier is given and the variant exists; otherwise
    `<name>.unreal.fbx` (UCX_ collision) when present, otherwise the canonical `<name>.glb`;
    rigged assets (bones > 0) as Skeletal Meshes. Assets land in /Game/MeshGate/Packs/<pack>/<asset>.
    """
    import json
    index_path = os.path.join(folder, "index.json")
    if not os.path.isfile(index_path):
        _message(f"{folder}: no index.json — is this a MeshGate pack folder?")
        return {}
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    pack = index.get("pack") or os.path.basename(os.path.normpath(folder))
    result = {}
    for entry in index.get("assets", []):
        name = os.path.splitext(entry["file"])[0]
        skeletal = int(entry.get("bones") or 0) > 0
        unreal_fbx = os.path.join(folder, f"{name}.unreal.fbx")
        tier_glb = os.path.join(folder, f"{name}.{profile}.glb") if profile and profile != "pc" else ""
        if tier_glb and os.path.isfile(tier_glb):
            src = tier_glb
        elif os.path.isfile(unreal_fbx) and not skeletal:
            src = unreal_fbx
        else:
            src = os.path.join(folder, entry["file"])
        if not os.path.isfile(src):
            unreal.log_warning(f"MeshGate: {src} is missing — skipped")
            continue
        suffix = f"_{profile}" if profile and profile != "pc" else ""
        result[name] = import_file(src, f"{dest_root}/{pack}{suffix}/{name}", skeletal=skeletal)
    unreal.log(f"MeshGate: pack {pack}: {sum(len(v) for v in result.values())} assets from {len(result)} files")
    return result


def build_demo_level(level_path: str = f"{DEST}/MeshGateDemo") -> bool:
    """Open or create the demo level, add sun + sky light once, place every imported sample, save."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ok = les.load_level(level_path) if unreal.EditorAssetLibrary.does_asset_exist(level_path) else les.new_level(level_path)
    if not ok:
        _message(f"cannot open or create {level_path}")
        return False
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = {a.get_actor_label(): a for a in eas.get_all_level_actors()}
    for label, cls, loc, rot in (("MeshGate Sun", unreal.DirectionalLight, (0, 0, 500), (0, -50, -30)),
                                 ("MeshGate Sky", unreal.SkyLight, (0, 0, 600), (0, 0, 0))):
        if label not in existing:
            actor = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]))
            if actor:
                actor.set_actor_label(label)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    for name, (x, y, z) in LAYOUT.items():
        label = f"MeshGate {name.replace('meshgate_', '')}"
        for old in [a for lbl, a in existing.items() if lbl.startswith(label)]:
            eas.destroy_actor(old)   # re-run: replace, don't duplicate
        spawned = 0
        for data in registry.get_assets_by_path(f"{DEST}/{name}", recursive=True):
            if str(data.asset_class_path.asset_name) not in ("StaticMesh", "SkeletalMesh"):
                continue
            yaw = 180 if name in SKELETAL else 0   # face the camera, like the other targets
            actor = eas.spawn_actor_from_object(data.get_asset(), unreal.Vector(x, y, z), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
            if actor:
                actor.set_actor_label(label if spawned == 0 else f"{label} {spawned}")
                spawned += 1
        unreal.log(f"MeshGate: {name}: {spawned} actors")
    les.save_current_level()
    unreal.log(f"MeshGate: level saved → {level_path}")
    return True


def validate_selected() -> None:
    """Menu: validate the source file of each asset selected in the Content Browser."""
    for asset in unreal.EditorUtilityLibrary.get_selected_assets():
        try:
            data = asset.get_editor_property("asset_import_data")
            src = data.get_first_filename() if data else ""
        except Exception:  # noqa: BLE001 — materials, textures … have no asset_import_data
            src = ""
        if src.lower().endswith((".glb", ".gltf", ".fbx")) and os.path.isfile(src):
            validate(src)
        else:
            unreal.log_warning(f"MeshGate: {asset.get_name()} has no GLB/FBX source file (source: {src or '—'})")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", help="path to meshgate/samples (default: $MESHGATE_SAMPLES or the repo next to the plugin)")
    ap.add_argument("--level", action="store_true", help="also build the demo level")
    ap.add_argument("--pack", help="also import an asset pack folder (with index.json), e.g. samples/packs/zombie_cats")
    ap.add_argument("--quality", choices=["mobile-low", "mobile-mid", "mobile-high", "pc"], help="apply this tier and import its pack variants")
    args = ap.parse_args([a for a in sys.argv[1:] if not a.startswith("-ExecutePythonScript")])
    if import_samples(args.samples) and args.level:
        build_demo_level()
    if args.quality:
        apply_quality(args.quality)
    if args.pack:
        import_pack(args.pack, profile=args.quality)
