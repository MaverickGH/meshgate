extends SceneTree
## MeshGate — headless check: every GLB in samples/ loads via MeshGateAsset per the contract.
##   godot --headless --path targets/godot/MeshGateDemo -s tests/test_meshgate.gd
## Exit code 0 means all checks passed.

var failures: Array[String] = []


func check(cond: bool, msg: String) -> void:
	if not cond:
		failures.append(msg)
		printerr("  ✗ " + msg)


func load_asset(file: String) -> MeshGateAsset:
	var a := MeshGateAsset.new()
	a.load_on_ready = false
	a.autoplay = false
	a.colliders = MeshGateAsset.Colliders.CONVEX
	root.add_child(a)
	var ok := a.load_asset("res://samples/" + file)
	check(ok, file + ": failed to load")
	return a


func _init() -> void:
	print("— MeshGate Godot check —")
	if not FileAccess.file_exists("res://samples/meshgate_demo.glb"):
		printerr("no res://samples/*.glb — run targets/godot/sync_samples.sh")
		quit(2)
		return

	var d := load_asset("meshgate_demo.glb")
	if d.is_loaded():
		for n in ["meshgate_demo", "crate_body", "crate_lid", "beacon_post", "beacon_ring", "handle_l"]:
			check(d.find(n) != null, "crate: missing node " + n)
		check(d.find("beacon_ring").get_parent().name == "beacon_post", "crate: beacon_ring is not under beacon_post")
		check(d.mesh_count == 17, "crate: meshes %d ≠ 17" % d.mesh_count)
		check(d.material_count == 4, "crate: materials %d ≠ 4" % d.material_count)
		var s := d.bounds.size
		check(absf(s.x - 0.832) < 0.02 and absf(s.y - 0.707) < 0.02 and absf(s.z - 0.524) < 0.02, "crate: bounds %s" % s)
		check(absf(d.bounds.position.y) < 0.02, "crate: origin is not at the base (min y = %f)" % d.bounds.position.y)
		var names := Array(d.animation_names); names.sort()
		check(names == ["beacon_spin", "lid_open"], "crate: animations %s" % [names])
		# the lid opens: after 1.5 s the rotation differs
		var lid := d.find("crate_lid")
		var q0 := lid.quaternion
		d.animation_player.play("lid_open"); d.animation_player.seek(1.5, true)
		check(q0.angle_to(lid.quaternion) > deg_to_rad(60), "crate: lid did not open (%.1f°)" % rad_to_deg(q0.angle_to(lid.quaternion)))
		check(d.root.find_children("*", "StaticBody3D", true, false).size() >= 17, "crate: colliders not created")
		print("  ✓ crate: %d meshes, %s, animations %s, %d ms" % [d.mesh_count, s, names, int(d.load_ms)])

	var h := load_asset("meshgate_hero.glb")
	if h.is_loaded():
		check(h.bone_count == 21, "hero: bones %d ≠ 21" % h.bone_count)
		check(h.skinned_mesh_count >= 1, "hero: no skinned mesh")
		var skel: Skeleton3D = h.root.find_children("*", "Skeleton3D", true, false)[0]
		for b in ["Hips", "Spine", "Chest", "Head", "LeftUpperArm", "RightLowerArm", "LeftFoot", "RightToes"]:
			check(skel.find_bone(b) >= 0, "hero: missing bone " + b)
		check(skel.get_bone_parent(skel.find_bone("RightShoulder")) == skel.find_bone("Chest"), "hero: RightShoulder is not under Chest")
		var hs := h.bounds.size
		check(absf(hs.y - 1.75) < 0.05, "hero: height %.2f ≠ 1.75" % hs.y)
		var hn := Array(h.animation_names); hn.sort()
		check(hn == ["idle", "wave"], "hero: animations %s" % [hn])
		var arm_i := skel.find_bone("RightUpperArm")
		var r0 := skel.get_bone_pose_rotation(arm_i)
		h.animation_player.play("wave"); h.animation_player.seek(1.0, true)
		var r1 := skel.get_bone_pose_rotation(arm_i)
		check(rad_to_deg(r0.angle_to(r1)) > 60.0, "hero: wave did not raise the arm (rotation %.1f°)" % rad_to_deg(r0.angle_to(r1)))
		print("  ✓ hero: %d bones, height %.2f, animations %s" % [h.bone_count, hs.y, hn])

	for item in [["meshgate_lantern.glb", ["flicker", "swing"], "flame"], ["meshgate_barrel.glb", [], "hoop_3"], ["meshgate_drone.glb", ["hover", "rotors"], "rotor_3"]]:
		var a := load_asset(item[0])
		if a.is_loaded():
			var an := Array(a.animation_names); an.sort()
			check(an == item[1], "%s: animations %s" % [item[0], an])
			check(a.find(item[2]) != null, "%s: missing node %s" % [item[0], item[2]])
			print("  ✓ %s: %d meshes, %s, animations %s" % [item[0], a.mesh_count, a.bounds.size, an])

	for pack in DirAccess.get_directories_at("res://samples/packs/"):   # every synced pack, generated ones included
		check_pack("res://samples/packs/%s/" % pack)
	check_quality("res://samples/packs/zombie_cats/")

	if failures.is_empty():
		print("Result: Godot accepts the canonical GLB per the contract.")
		quit(0)
	else:
		printerr("Result: %d failures" % failures.size())
		quit(1)


## Example pack: every asset loads at runtime with the clips, bones and height from the pack's index.json;
## the Godot variant's "-convcolonly" nodes become collision in the editor import.
func check_pack(dir: String) -> void:
	if not FileAccess.file_exists(dir + "index.json"):
		print("  · pack not synced (targets/godot/sync_samples.sh) — skipped")
		return
	var index: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(dir + "index.json"))
	var ok := 0
	var tier_files := 0
	for a in index["assets"]:
		var asset := MeshGateAsset.new()
		asset.load_on_ready = false
		asset.autoplay = false
		root.add_child(asset)
		if not asset.load_asset(dir + a["file"]):
			check(false, "pack %s: did not load" % a["file"])
			continue
		var got := Array(asset.animation_names); got.sort()
		var want: Array = a["clips"].duplicate(); want.sort()
		check(got == want, "pack %s: clips %s, expected %s" % [a["file"], got, want])
		check(asset.bone_count == int(a["bones"]), "pack %s: bones %d, expected %d" % [a["file"], asset.bone_count, int(a["bones"])])
		check(absf(asset.bounds.size.y - float(a["dims_m"][1])) < 0.05, "pack %s: height %.2f, expected %.2f" % [a["file"], asset.bounds.size.y, float(a["dims_m"][1])])
		check(absf(asset.bounds.position.y) < 0.05, "pack %s: not on the ground (min y %.3f)" % [a["file"], asset.bounds.position.y])
		if a.get("colors", "texture") == "vertex":   # COLOR_0 must drive the albedo, with no textures at all
			var mi: MeshInstance3D = asset.find_children("*", "MeshInstance3D", true, false)[0]
			var mat := mi.get_active_material(0) as BaseMaterial3D
			check(mat != null and mat.vertex_color_use_as_albedo and mat.albedo_texture == null,
				"pack %s: vertex colours are not used as albedo" % a["file"])
		ok += 1
		asset.queue_free()
		# every quality-tier file of the asset loads within that tier's triangle budget
		var budgets := [["mobile-low", 60000], ["mobile-mid", 150000], ["mobile-high", 300000]] if a.get("kind", "asset") == "scene" \
			else [["mobile-low", 8000], ["mobile-mid", 25000], ["mobile-high", 60000]]
		for tier in budgets:
			var tf: String = a["file"].get_basename() + "." + tier[0] + ".glb"
			if not FileAccess.file_exists(dir + tf):
				continue
			var t := MeshGateAsset.new()
			t.load_on_ready = false
			t.autoplay = false
			t.use_quality_variant = false
			root.add_child(t)
			check(t.load_asset(dir + tf), "pack %s: did not load" % tf)
			check(t.triangle_count <= int(tier[1]), "pack %s: %d tris over the %s budget" % [tf, t.triangle_count, tier[0]])
			tier_files += 1
			t.queue_free()
	# collision hints: only the editor importer applies them
	var godot_variants := 0
	for f in DirAccess.get_files_at(dir):
		if not f.ends_with(".godot.glb"):
			continue
		var scene: PackedScene = load(dir + f)
		if scene == null:
			check(false, "pack %s: not imported (run godot --headless --import)" % f)
			continue
		var inst := scene.instantiate()
		var bodies := inst.find_children("*", "StaticBody3D", true, false)
		check(bodies.size() > 0, "pack %s: no StaticBody3D from -convcolonly" % f)
		godot_variants += 1
		inst.free()
	print("  ✓ pack %s: %d assets as indexed, %d tier files within budget, %d Godot variants with collision" % [dir.get_base_dir().get_file(), ok, tier_files, godot_variants])


## Quality tiers: mobile-low picks the .mobile-low.glb variant (fewer tris) and sets the viewport; pc loads the canonical file.
func check_quality(dir: String) -> void:
	if not FileAccess.file_exists(dir + "zc_zombie_cat.mobile-low.glb"):
		print("  · tier variants not synced — skipped")
		return
	MeshGateQuality.apply("mobile-low", root)
	check(root.msaa_3d == Viewport.MSAA_DISABLED, "mobile-low: MSAA should be off")
	check(is_equal_approx(root.scaling_3d_scale, 0.75), "mobile-low: 3D scale 0.75, got %f" % root.scaling_3d_scale)
	var low := load_asset("packs/zombie_cats/zc_zombie_cat.glb")
	check(low.loaded_file == "zc_zombie_cat.mobile-low.glb", "mobile-low: variant not picked (%s)" % low.loaded_file)
	check(low.triangle_count <= 8000, "mobile-low: %d tris > 8000" % low.triangle_count)
	MeshGateQuality.apply("pc", root)
	check(root.msaa_3d == Viewport.MSAA_4X, "pc: MSAA 4x")
	var pc := load_asset("packs/zombie_cats/zc_zombie_cat.glb")
	check(pc.loaded_file == "zc_zombie_cat.glb", "pc: canonical expected (%s)" % pc.loaded_file)
	check(pc.triangle_count > low.triangle_count * 5, "pc detail (%d) should be far above mobile-low (%d)" % [pc.triangle_count, low.triangle_count])
	print("  ✓ quality tiers: mobile-low → %s (%d tris), pc → %s (%d tris)" % [low.loaded_file, low.triangle_count, pc.loaded_file, pc.triangle_count])

