class_name MeshGateQuality
extends Node
## MeshGate — quality tiers for Godot: mobile-low / mobile-mid / mobile-high / pc.
## TABLE mirrors the "render" part of core/profiles.json (tests/check_profiles.py keeps them in sync).
## apply() sets the viewport (MSAA, 3D scaling, mesh LOD), the directional shadow atlas and lights, and SSAO/glow on
## every WorldEnvironment. MeshGateAsset picks <name>.<tier>.glb while `current` is a mobile tier and the file exists.

const TABLE := {
	"mobile-low": {"label": "Mobile · low", "pixel_ratio": 1.0, "render_scale": 0.75, "msaa": 0, "shadows": "off", "shadow_map": 0, "shadow_distance": 0, "ao": false, "bloom": false, "hdr": false, "lod_bias": 0.5, "anisotropy": 1},
	"mobile-mid": {"label": "Mobile · mid", "pixel_ratio": 1.5, "render_scale": 0.9, "msaa": 2, "shadows": "hard", "shadow_map": 1024, "shadow_distance": 15, "ao": false, "bloom": false, "hdr": false, "lod_bias": 1.0, "anisotropy": 2},
	"mobile-high": {"label": "Mobile · high", "pixel_ratio": 2.0, "render_scale": 1.0, "msaa": 4, "shadows": "soft", "shadow_map": 2048, "shadow_distance": 30, "ao": false, "bloom": true, "hdr": true, "lod_bias": 1.5, "anisotropy": 4},
	"pc": {"label": "PC · high quality", "pixel_ratio": 2.0, "render_scale": 1.0, "msaa": 4, "shadows": "soft", "shadow_map": 4096, "shadow_distance": 80, "ao": true, "bloom": true, "hdr": true, "lod_bias": 2.0, "anisotropy": 16},
}

static var current: String = "pc"

@export_enum("auto", "mobile-low", "mobile-mid", "mobile-high", "pc") var tier: String = "auto"


func _ready() -> void:
	MeshGateQuality.apply(tier, get_viewport())


## Desktop → pc. Phones/tablets: ≤ 3.5 GB RAM or ≤ 4 cores → low; ≥ 7.5 GB and ≥ 8 cores → high; else mid.
static func detect() -> String:
	if not (OS.has_feature("mobile") or OS.get_name() in ["Android", "iOS"]):
		return "pc"
	var mem_gb: float = float(OS.get_memory_info().get("physical", 4 << 30)) / float(1 << 30)
	var cores := OS.get_processor_count()
	if mem_gb <= 3.5 or cores <= 4:
		return "mobile-low"
	if mem_gb >= 7.5 and cores >= 8:
		return "mobile-high"
	return "mobile-mid"


static func apply(t: String, viewport: Viewport) -> void:
	if t == "auto" or not TABLE.has(t):
		t = detect()
	current = t
	var s: Dictionary = TABLE[t]
	var msaa := {0: Viewport.MSAA_DISABLED, 2: Viewport.MSAA_2X, 4: Viewport.MSAA_4X, 8: Viewport.MSAA_8X}
	viewport.msaa_3d = msaa.get(int(s["msaa"]), Viewport.MSAA_DISABLED)
	viewport.scaling_3d_scale = float(s["render_scale"])
	viewport.mesh_lod_threshold = 1.0 / maxf(float(s["lod_bias"]), 0.1)
	RenderingServer.directional_shadow_atlas_set_size(maxi(int(s["shadow_map"]), 256), true)
	RenderingServer.directional_soft_shadow_filter_set_quality(
		RenderingServer.SHADOW_QUALITY_SOFT_HIGH if s["shadows"] == "soft" else RenderingServer.SHADOW_QUALITY_HARD)
	for light in viewport.find_children("*", "DirectionalLight3D", true, false):
		(light as DirectionalLight3D).shadow_enabled = s["shadows"] != "off"
		(light as DirectionalLight3D).directional_shadow_max_distance = maxf(float(s["shadow_distance"]), 1.0)
	for we in viewport.find_children("*", "WorldEnvironment", true, false):
		var env: Environment = (we as WorldEnvironment).environment
		if env:
			env.ssao_enabled = s["ao"]
			env.glow_enabled = s["bloom"]


## res://path/asset.glb → res://path/asset.<tier>.glb (unchanged for pc)
static func variant_path(source: String, t: String = current) -> String:
	if t == "pc" or not source.ends_with(".glb"):
		return source
	return source.substr(0, source.length() - 4) + "." + t + ".glb"
