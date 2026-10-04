class_name MeshGateInteraction
extends Node
## MeshGate — hover and click on asset nodes (as in the web viewer). Requires colliders: if they
## are disabled on the MeshGateAsset, enables CONVEX.

signal hover_entered(node: Node3D)
signal hover_exited(node: Node3D)
signal clicked(node: Node3D)

@export var asset: MeshGateAsset
@export var camera: Camera3D
@export var highlight: bool = true
@export var highlight_color: Color = Color(0.75, 0.6, 1.0, 0.45)

var hovered: Node3D
var selected: Node3D
var _overlay: StandardMaterial3D
var _down := Vector2.ZERO


func _ready() -> void:
	if asset == null:
		asset = get_parent() as MeshGateAsset
	if asset and asset.colliders == MeshGateAsset.Colliders.NONE:
		asset.colliders = MeshGateAsset.Colliders.CONVEX
	_overlay = StandardMaterial3D.new()
	_overlay.albedo_color = highlight_color
	_overlay.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_overlay.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED


func _process(_dt: float) -> void:
	var cam := camera if camera else get_viewport().get_camera_3d()
	if cam == null or asset == null or not asset.is_loaded():
		return
	var mouse := get_viewport().get_mouse_position()
	var hit := _raycast(cam, mouse)
	_set_hovered(hit)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		var b := event as InputEventMouseButton
		if b.pressed:
			_down = b.position
		elif b.position.distance_to(_down) < 6.0:
			selected = hovered
			if selected:
				clicked.emit(selected)


func _raycast(cam: Camera3D, pos: Vector2) -> Node3D:
	var from := cam.project_ray_origin(pos)
	var to := from + cam.project_ray_normal(pos) * 1000.0
	var space := cam.get_world_3d().direct_space_state
	var res := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, to))
	if res.is_empty():
		return null
	var collider: Node = res["collider"]
	# The StaticBody3D created by create_*_collision sits under its MeshInstance3D
	var mi := collider.get_parent()
	if mi is MeshInstance3D and asset.root.is_ancestor_of(mi):
		return mi
	return null


func _set_hovered(node: Node3D) -> void:
	if node == hovered:
		return
	if hovered:
		_tint(hovered, false)
		hover_exited.emit(hovered)
	hovered = node
	if hovered:
		_tint(hovered, true)
		hover_entered.emit(hovered)


func _tint(node: Node3D, on: bool) -> void:
	if not highlight or not (node is MeshInstance3D):
		return
	(node as MeshInstance3D).material_overlay = _overlay if on else null
