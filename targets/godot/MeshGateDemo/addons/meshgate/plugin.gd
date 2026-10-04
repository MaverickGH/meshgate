@tool
extends EditorPlugin
# MeshGate — registers the addon nodes in the "Add Node" dialog.

func _enter_tree() -> void:
	add_custom_type("MeshGateAsset", "Node3D", preload("meshgate_asset.gd"), null)
	add_custom_type("MeshGateOrbitCamera", "Camera3D", preload("meshgate_orbit_camera.gd"), null)
	add_custom_type("MeshGateInteraction", "Node", preload("meshgate_interaction.gd"), null)
	add_custom_type("MeshGateHud", "CanvasLayer", preload("meshgate_hud.gd"), null)
	add_custom_type("MeshGateQuality", "Node", preload("meshgate_quality.gd"), null)


func _exit_tree() -> void:
	for t in ["MeshGateAsset", "MeshGateOrbitCamera", "MeshGateInteraction", "MeshGateHud", "MeshGateQuality"]:
		remove_custom_type(t)
