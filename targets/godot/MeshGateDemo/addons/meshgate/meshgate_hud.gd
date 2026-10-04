class_name MeshGateHud
extends CanvasLayer
## MeshGate — demo scene HUD: asset passport, names under the cursor, clips.

@export var asset: MeshGateAsset
@export var interaction: MeshGateInteraction

var _label: Label
var _hover := ""
var _clicked := ""


func _ready() -> void:
	_label = Label.new()
	_label.position = Vector2(12, 12)
	_label.add_theme_font_size_override("font_size", 14)
	var panel := PanelContainer.new()
	panel.position = Vector2(8, 8)
	panel.add_child(_label)
	add_child(panel)
	if interaction:
		interaction.hover_entered.connect(func(n: Node3D) -> void: _hover = n.name)
		interaction.hover_exited.connect(func(_n: Node3D) -> void: _hover = "")
		interaction.clicked.connect(func(n: Node3D) -> void: _clicked = n.name)


func _process(_dt: float) -> void:
	if asset == null or not asset.is_loaded():
		_label.text = "MeshGate · Godot\nloading…"
		return
	var s := asset.bounds.size
	_label.text = "MeshGate · Godot 4 (GLTFDocument)\n%s · %.0f ms\nbounds %.2f × %.2f × %.2f m\n%d meshes · %d tris · %d materials%s\nanimations: %s%s\nhover: %s\nclick: %s\nLMB — orbit · RMB — pan · wheel — zoom · F — frame · Space — pause · 1..9 — clip" % [
		(asset.loaded_file if asset.loaded_file != "" else asset.source.get_file()) + ("  [%s]" % MeshGateQuality.current), asset.load_ms, s.x, s.y, s.z,
		asset.mesh_count, asset.triangle_count, asset.material_count,
		(" · %d bones" % asset.bone_count) if asset.bone_count > 0 else "",
		", ".join(asset.animation_names) if asset.animation_names.size() > 0 else "none",
		(" (playing: %s)" % asset.animation_player.current_animation) if asset.is_playing() else "",
		_hover, _clicked]


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or asset == null:
		return
	var k := (event as InputEventKey).keycode
	if k == KEY_SPACE:
		if asset.is_playing(): asset.stop()
		else: asset.play()
	elif k >= KEY_1 and k <= KEY_9:
		var i := k - KEY_1
		if i < asset.animation_names.size():
			asset.solo(asset.animation_names[i])
