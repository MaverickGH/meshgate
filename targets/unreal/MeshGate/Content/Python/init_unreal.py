# MeshGate — run by Unreal when the plugin loads (PythonScriptPlugin looks for init_unreal.py in Content/Python).
# Registers the Tools → MeshGate menu entries.
import unreal

import meshgate_import


def _register_menu() -> None:
    menus = unreal.ToolMenus.get()
    if menus is None:  # commandlets / -ExecutePythonScript without a UI
        return
    main = menus.find_menu("LevelEditor.MainMenu.Tools")
    if main is None:
        return
    section = "MeshGate"
    main.add_section(section, unreal.Text("MeshGate"))
    for label, fn in (("MeshGate: Import samples/ into /Game/MeshGate", "import_samples"),
                      ("MeshGate: Build demo level", "build_demo_level"),
                      ("MeshGate: Validate selected GLB against contract", "validate_selected")):
        entry = unreal.ToolMenuEntry(name=fn, type=unreal.MultiBlockType.MENU_ENTRY)
        entry.set_label(unreal.Text(label))
        entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "", f"import meshgate_import; meshgate_import.{fn}()")
        entry.set_tool_tip(unreal.Text("MeshGate — see targets/unreal/README.md"))
        main.add_menu_entry(section, entry)
    menus.refresh_all_widgets()


try:
    _register_menu()
    unreal.log("MeshGate: Tools → MeshGate menu registered")
except Exception as exc:  # noqa: BLE001 — never break editor startup
    unreal.log_warning(f"MeshGate: menu not registered: {exc}")
