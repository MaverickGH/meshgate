class_name MeshGateOrbitCamera
extends Camera3D
## MeshGate — orbit camera: LMB — orbit, RMB — pan, wheel — zoom, F — frame the asset.

@export var target: MeshGateAsset
@export var pivot: Vector3 = Vector3.ZERO
@export var distance: float = 3.0
@export var yaw: float = 35.0
@export var pitch: float = 20.0
@export var rotate_speed: float = 0.25
@export var zoom_speed: float = 0.12
@export var pan_speed: float = 0.002


func _ready() -> void:
	if target:
		target.loaded.connect(func(a: MeshGateAsset) -> void: frame(a.bounds))
	_apply()


func frame(aabb: AABB) -> void:
	pivot = aabb.get_center()
	var radius := maxf(aabb.size.length() * 0.5, 0.05)
	distance = radius / sin(deg_to_rad(fov) * 0.5) * 1.15
	near = maxf(radius / 200.0, 0.001)
	far = maxf(radius * 200.0, 50.0)
	_apply()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var m := event as InputEventMouseMotion
		if m.button_mask & MOUSE_BUTTON_MASK_LEFT:
			yaw -= m.relative.x * rotate_speed
			pitch = clampf(pitch + m.relative.y * rotate_speed, -85.0, 85.0)
			_apply()
		elif m.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			pivot -= (global_transform.basis.x * m.relative.x - global_transform.basis.y * m.relative.y) * (pan_speed * distance)
			_apply()
	elif event is InputEventMouseButton and event.pressed:
		var b := event as InputEventMouseButton
		if b.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(0.01, distance * (1.0 - zoom_speed)); _apply()
		elif b.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = distance * (1.0 + zoom_speed); _apply()
	elif event is InputEventKey and event.pressed and (event as InputEventKey).keycode == KEY_F and target and target.is_loaded():
		frame(target.bounds)


func _apply() -> void:
	var basis := Basis.from_euler(Vector3(deg_to_rad(-pitch), deg_to_rad(yaw), 0.0))
	global_transform = Transform3D(basis, pivot + basis * Vector3(0, 0, distance))
