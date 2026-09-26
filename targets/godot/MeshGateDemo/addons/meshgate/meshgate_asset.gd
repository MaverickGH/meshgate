@tool
class_name MeshGateAsset
extends Node3D
## MeshGate — runtime loading of a canonical GLB in Godot.
##
## One node: path to a .glb → scene with glTF names, animations by name (AnimationPlayer),
## bounds in meters, colliders, stats. Editor import (.glb in res://) is handled by Godot itself —
## this node is for runtime loading from a path/URL and an API consistent with web/Unity.

signal loaded(asset: MeshGateAsset)
signal failed(message: String)

enum Colliders { NONE, BOX, CONVEX, TRIMESH }

@export_file("*.glb", "*.gltf") var source: String = ""
@export var load_on_ready: bool = true
@export var autoplay: bool = true
## Play only this clip after loading (e.g. "shamble"); empty = the first clip when autoplay is on.
@export var play_on_load: String = ""
@export var loop: bool = true
@export_range(0.1, 3.0, 0.1) var speed: float = 1.0
@export var colliders: Colliders = Colliders.NONE
## Load <name>.<tier>.glb next to the source while MeshGateQuality.current is a mobile tier and the file exists.
@export var use_quality_variant: bool = true

var root: Node3D
var animation_player: AnimationPlayer
var animation_names: PackedStringArray = []
var mesh_count: int = 0
var triangle_count: int = 0
var material_count: int = 0
var bone_count: int = 0
var skinned_mesh_count: int = 0
var bounds: AABB = AABB()
var load_ms: float = 0.0
var loaded_file: String = ""

var _by_name: Dictionary = {}
var _solo: String = ""


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	if load_on_ready and source != "":
		load_asset()


func is_loaded() -> bool:
	return root != null


## Load a GLB (res://, user:// or absolute path), replacing the current one.
func load_asset(override_source: String = "") -> bool:
	if override_source != "":
		source = override_source
	unload()
	var t0 := Time.get_ticks_usec()
	var chosen := source
	if use_quality_variant and MeshGateQuality.current != "pc":
		var variant := MeshGateQuality.variant_path(source)
		if variant != source and FileAccess.file_exists(variant):
			chosen = variant
	loaded_file = chosen.get_file()
	var path := ProjectSettings.globalize_path(chosen) if chosen.begins_with("res://") or chosen.begins_with("user://") else chosen
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		_fail("%s: GLTFDocument returned error %d" % [source, err])
		return false
	var node := doc.generate_scene(state)
	if node == null:
		_fail("%s: failed to generate scene" % source)
		return false
	root = node as Node3D
	root.name = source.get_file().get_basename()
	add_child(root)
	load_ms = (Time.get_ticks_usec() - t0) / 1000.0
	_index()
	_setup_animation()
	_setup_colliders()
	loaded.emit(self)
	return true


func unload() -> void:
	if root != null:
		root.queue_free()
		root = null
	animation_player = null
	animation_names = []
	_by_name.clear()
	mesh_count = 0; triangle_count = 0; material_count = 0; bone_count = 0; skinned_mesh_count = 0


## Node by its glTF name (e.g. "crate_lid").
func find(node_name: String) -> Node3D:
	return _by_name.get(node_name, null)


func node_names() -> Array:
	return _by_name.keys()


# --- animations -------------------------------------------------------------

func play(clip: String = "") -> void:
	if animation_player == null:
		return
	if clip == "":
		clip = _solo if _solo != "" else (animation_names[0] if animation_names.size() > 0 else "")
	if clip == "":
		return
	var anim := animation_player.get_animation(clip)
	if anim:
		anim.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
	animation_player.speed_scale = speed
	animation_player.play(clip)


func solo(clip: String) -> void:
	_solo = clip
	play(clip)


func stop() -> void:
	if animation_player:
		animation_player.stop()


func is_playing() -> bool:
	return animation_player != null and animation_player.is_playing()


func set_speed(value: float) -> void:
	speed = value
	if animation_player:
		animation_player.speed_scale = value


# --- internals --------------------------------------------------------------

func _index() -> void:
	var mats := {}
	var first := true
	for n in root.find_children("*", "", true, false):
		if n is Node3D and not _by_name.has(n.name):
			_by_name[n.name] = n
		if n is MeshInstance3D:
			var mi := n as MeshInstance3D
			mesh_count += 1
			if mi.skeleton != NodePath("") and mi.get_node_or_null(mi.skeleton) is Skeleton3D:
				skinned_mesh_count += 1
			if mi.mesh:
				for s in mi.mesh.get_surface_count():
					var m := mi.get_active_material(s)
					if m:
						mats[m] = true
					var arrays := mi.mesh.surface_get_arrays(s)
					# glTF multiplies the base colour by COLOR_0, but Godot's runtime GLTFDocument leaves vertex colours
					# off: turn them on for untextured materials (MeshGate --colors vertex), linear as glTF stores them.
					var bm := m as BaseMaterial3D
					if bm and arrays[Mesh.ARRAY_COLOR] != null and bm.albedo_texture == null and not bm.vertex_color_use_as_albedo:
						bm.vertex_color_use_as_albedo = true
						bm.vertex_color_is_srgb = false
					var idx = arrays[Mesh.ARRAY_INDEX]
					var verts = arrays[Mesh.ARRAY_VERTEX]
					triangle_count += (idx.size() if idx else verts.size()) / 3
			var aabb: AABB = _world_xform(mi) * mi.get_aabb()
			bounds = aabb if first else bounds.merge(aabb)
			first = false
		if n is Skeleton3D:
			bone_count += (n as Skeleton3D).get_bone_count()
	material_count = mats.size()


## Node transform in world space (or relative to this MeshGateAsset if the tree is not ready yet).
func _world_xform(node: Node3D) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var n: Node = node
	while n != null and n != self:
		if n is Node3D:
			xf = (n as Node3D).transform * xf
		n = n.get_parent()
	return (global_transform if is_inside_tree() else transform) * xf


func _setup_animation() -> void:
	var players := root.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		return
	animation_player = players[0]
	for anim_name in animation_player.get_animation_list():
		animation_names.append(anim_name)
	if play_on_load != "" and play_on_load in animation_names:
		solo(play_on_load)
	elif autoplay and animation_names.size() > 0:
		play(animation_names[0])


func _setup_colliders() -> void:
	if colliders == Colliders.NONE:
		return
	if colliders == Colliders.BOX:
		var body := StaticBody3D.new()
		body.name = "collider"
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = bounds.size
		shape.shape = box
		shape.position = bounds.get_center() - global_position
		body.add_child(shape)
		root.add_child(body)
		return
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		if colliders == Colliders.CONVEX:
			(mi as MeshInstance3D).create_convex_collision()
		else:
			(mi as MeshInstance3D).create_trimesh_collision()


func _fail(message: String) -> void:
	push_error("MeshGate: " + message)
	failed.emit(message)
