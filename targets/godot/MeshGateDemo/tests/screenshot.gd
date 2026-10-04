extends SceneTree
## MeshGate — capture the demo scene to PNG (needs a window, not headless):
##   godot --path targets/godot/MeshGateDemo -s tests/screenshot.gd  →  TestResults/meshgate_godot.png

func _init() -> void:
	var scene_path := OS.get_environment("MESHGATE_SCENE")
	change_scene_to_file(scene_path if scene_path != "" else "res://demo.tscn")
	await process_frame
	await process_frame
	var demo := current_scene
	# let assets load and settle into a pose
	for i in 20:
		await process_frame
	for a in demo.get_children():
		if a is MeshGateAsset and a.is_loaded():
			if "wave" in a.animation_names:
				a.animation_player.play("wave"); a.animation_player.seek(1.0, true)
			elif "lid_open" in a.animation_names:
				a.animation_player.play("lid_open"); a.animation_player.seek(1.5, true)
	var cam: MeshGateOrbitCamera = demo.get_node("OrbitCamera")
	if OS.get_environment("MESHGATE_SCENE") == "":
		cam.yaw = 25.0; cam.pitch = 22.0
	await process_frame
	await process_frame
	var img := root.get_viewport().get_texture().get_image()
	var out := OS.get_environment("MESHGATE_SHOT")
	if out == "":
		out = ProjectSettings.globalize_path("res://TestResults/meshgate_godot.png")
	DirAccess.make_dir_recursive_absolute(out.get_base_dir())
	var err := img.save_png(out)
	print("MeshGate: screenshot %s → %s (%dx%d)" % ["ok" if err == OK else "error %d" % err, out, img.get_width(), img.get_height()])
	quit(0 if err == OK else 1)
