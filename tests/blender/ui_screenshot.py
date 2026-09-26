"""Open Blender with a window, show the MeshGate sidebar tab, run Check + Export, screenshot, quit.

    blender --factory-startup -P tests/blender/ui_screenshot.py -- --zip dist/meshgate-blender-X.zip --blend samples/meshgate_demo.blend --out /tmp/shot

Catches what the headless test cannot: exceptions inside Panel.draw() and a broken layout.
Run it in a throwaway profile (BLENDER_USER_* env vars) like `meshgate.py check blender` does.
"""

import os
import sys
import traceback

import addon_utils
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
ZIP = os.path.abspath(argv[argv.index("--zip") + 1])
BLEND = os.path.abspath(argv[argv.index("--blend") + 1])
OUT = os.path.abspath(argv[argv.index("--out") + 1])
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui.log"), "w")


def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n"); LOG.flush()


def module_name():
    return "bl_ext.user_default.meshgate" if bpy.app.version >= (4, 2, 0) else "meshgate"


def install():
    mod = module_name()
    if bpy.app.version >= (4, 2, 0):
        bpy.ops.extensions.package_install_files(filepath=ZIP, repo="user_default", enable_on_install=True)
    else:
        bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
    addon_utils.enable(mod, default_set=True)


def view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                return window, area
    return None, None


def stage1():
    try:
        bpy.ops.wm.open_mainfile(filepath=BLEND)
        addon_utils.enable(module_name(), default_set=True)
    except Exception:  # noqa: BLE001
        log("ERROR open: " + traceback.format_exc())
    bpy.app.timers.register(stage2, first_interval=1.0)
    return None


def stage2():
    try:
        window, area = view3d()
        area.spaces.active.show_region_ui = True
        # the sidebar tab cannot be switched from Python: show our panels on the default "Item" tab, on top
        for name in ("MESHGATE_PT_main", "MESHGATE_PT_engine"):
            cls = getattr(bpy.types, name)
            bpy.utils.unregister_class(cls)
            cls.bl_category = "Item"
            cls.bl_order = -10
        for name in ("MESHGATE_PT_main", "MESHGATE_PT_engine"):
            bpy.utils.register_class(sys.modules[module_name() + ".ui"].__dict__[name])
        s = bpy.context.scene.meshgate
        s.target_web = s.target_unity = s.target_godot = s.target_unreal = True
        s.out_dir = OUT + os.sep
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.meshgate.check()
            bpy.ops.meshgate.export()
        # make the 3D view large so the sidebar has room
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.screen_full_area()
    except Exception:  # noqa: BLE001
        log("ERROR stage2: " + traceback.format_exc())
    bpy.app.timers.register(stage3, first_interval=1.5)
    return None


def stage3():
    try:
        window, area = view3d()
        path = os.path.join(OUT, f"meshgate_panel_{bpy.app.version_string.split()[0]}.png")
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.screenshot_area(filepath=path)
        log(f"SHOT {path}")
    except Exception:  # noqa: BLE001
        log("ERROR shot: " + traceback.format_exc())
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
    return None


try:
    install()
    log(f"installed in Blender {bpy.app.version_string}")
except Exception:  # noqa: BLE001
    log("ERROR install: " + traceback.format_exc())
bpy.app.timers.register(stage1, first_interval=1.0)
