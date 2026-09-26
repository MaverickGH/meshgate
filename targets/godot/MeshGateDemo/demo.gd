extends Node3D
## MeshGate — Godot demo scene: light, environment, floor, orbit camera and every sample from samples/.
## Assets are loaded at runtime via MeshGateAsset (GLTFDocument); Godot handles editor import of .glb
## itself — the same files in res://samples/ show up as scenes in the editor.

const SAMPLES := "res://samples/"
const LAYOUT := [
	# file, position, autoplay
	["meshgate_demo.glb", Vector3(0, 0, 0)],
	["meshgate_hero.glb", Vector3(0, 0, 1.6)],
	["meshgate_lantern.glb", Vector3(-1.4, 1.0, -1.2)],
	["meshgate_barrel.glb", Vector3(0, 0, -1.3)],
	["meshgate_drone.glb", Vector3(1.4, 0, -1.2)],
]

var assets: Array[MeshGateAsset] = []


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.043, 0.055, 0.09)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.55, 0.6, 0.75)
	e.ambient_light_energy = 0.6
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.environment = e
	add_child(env)

	var sun := DirectionalLight3D.new()
	sun.light_energy = 1.6
	sun.shadow_enabled = true
	sun.rotation_degrees = Vector3(-50, -30, 0)
	add_child(sun)

	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(8, 8)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.12, 0.13, 0.2)
	plane.material = gm
	ground.mesh = plane
	ground.create_trimesh_collision()
	add_child(ground)

	var cam := MeshGateOrbitCamera.new()
	cam.name = "OrbitCamera"
	add_child(cam)
	cam.make_current()

	for item in LAYOUT:
		var file: String = item[0]
		if not FileAccess.file_exists(SAMPLES + file):
			continue
		var a := MeshGateAsset.new()
		a.name = file.get_basename()
		a.source = SAMPLES + file
		a.position = item[1]
		if file.contains("hero"):
			a.rotation_degrees.y = 180.0
		a.colliders = MeshGateAsset.Colliders.CONVEX
		add_child(a)
		var inter := MeshGateInteraction.new()
		inter.asset = a
		a.add_child(inter)
		assets.append(a)
		if assets.size() == 1:
			var hud := MeshGateHud.new()
			hud.asset = a
			hud.interaction = inter
			add_child(hud)

	await get_tree().process_frame
	var all := AABB()
	var first := true
	for a in assets:
		if a.is_loaded():
			all = a.bounds if first else all.merge(a.bounds)
			first = false
	if not first:
		cam.frame(all)
