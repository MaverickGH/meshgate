extends Node3D
## MeshGate — Zombie Cats pack in Godot: the diorama (runtime load, "shamble" playing), the collision variant of
## the fence (editor import with -convcolonly → StaticBody3D), moonlight, orbit camera, HUD.

const PACK := "res://samples/packs/zombie_cats/"
## Quality tier of this scene: the diorama loads zc_diorama.<tier>.glb and MeshGateQuality sets MSAA, shadows, SSAO, glow.
@export_enum("mobile-low", "mobile-mid", "mobile-high", "pc") var tier: String = "pc"


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.07, 0.06, 0.11)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.5, 0.5, 0.7)
	e.ambient_light_energy = 0.7
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.glow_enabled = true
	env.environment = e
	add_child(env)

	var moon := DirectionalLight3D.new()
	moon.light_energy = 1.3
	moon.light_color = Color(0.85, 0.9, 1.0)
	moon.shadow_enabled = true
	moon.rotation_degrees = Vector3(-45, 150, 0)
	add_child(moon)

	MeshGateQuality.current = tier   # before any MeshGateAsset loads, so it picks this tier's files

	var cam := MeshGateOrbitCamera.new()
	cam.name = "OrbitCamera"
	cam.fov = 40
	add_child(cam)
	cam.make_current()

	var dio := MeshGateAsset.new()
	dio.name = "diorama"
	dio.source = PACK + "zc_diorama.glb"
	dio.play_on_load = "shamble"
	add_child(dio)

	if ResourceLoader.exists(PACK + "zc_fence_broken.godot.glb"):
		var fence: Node3D = load(PACK + "zc_fence_broken.godot.glb").instantiate()
		fence.name = "fence_with_collision"
		fence.position = Vector3(-3, 0, 5.4)   # glTF +Z (Blender -Y) is the front of the diorama
		add_child(fence)

	var hud := MeshGateHud.new()
	hud.asset = dio
	add_child(hud)

	MeshGateQuality.apply(tier, get_viewport())   # lights and environment exist now
	await get_tree().process_frame
	cam.yaw = 35.0
	cam.pitch = 30.0
	cam.pivot = Vector3(0, 0.6, 0.8)
	cam.distance = 12.5
	cam._apply()
