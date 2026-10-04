#!/usr/bin/env python3
"""Quality tiers must mean the same everywhere: core/profiles.json is the source, five places mirror it.

    python3 tests/check_profiles.py

Checks the tier tables in the web viewer (JS), Unity (C#), Godot (GDScript) and Unreal (Python) against
core/profiles.json → render, and that the Blender add-on bundles the validator that reads the file itself.
Regenerate a table from the JSON when this fails — never edit numbers in one place only.
"""

import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PROFILES = json.loads((ROOT / "core" / "profiles.json").read_text())
ORDER = PROFILES["order"]

MIRRORS = {
    # file → (fields to compare, regex that finds one tier's row; group 1 = tier id, group 2 = the row text)
    "targets/web/meshgate-viewer.js": (["pixel_ratio", "render_scale", "msaa", "shadows", "shadow_map", "ao", "bloom"],
                                       r'"(mobile-low|mobile-mid|mobile-high|pc)":\s*\{([^}]*)\}'),
    "targets/unity/com.meshgate.unity/Runtime/MeshGateQuality.cs": (
        ["pixelRatio", "renderScale", "msaa", "shadows", "shadowMap", "shadowDistance", "ao", "bloom", "hdr", "lodBias", "textureLimit", "anisotropy"],
        r'new Settings \{ id = "(mobile-low|mobile-mid|mobile-high|pc)",([^}]*)\}'),
    "targets/godot/MeshGateDemo/addons/meshgate/meshgate_quality.gd": (
        ["pixel_ratio", "render_scale", "msaa", "shadows", "shadow_map", "shadow_distance", "ao", "bloom", "hdr", "lod_bias", "anisotropy"],
        r'"(mobile-low|mobile-mid|mobile-high|pc)":\s*\{([^}]*)\}'),
    "targets/unreal/MeshGate/Content/Python/meshgate_import.py": (["render_scale", "msaa", "shadows", "shadow_distance", "ao", "bloom"],
                                                                  r'"(mobile-low|mobile-mid|mobile-high|pc)":\s*\{("render_scale"[^}]*)\}'),
}
CAMEL = {"pixelRatio": "pixel_ratio", "renderScale": "render_scale", "shadowMap": "shadow_map", "shadowDistance": "shadow_distance",
         "lodBias": "lod_bias", "textureLimit": "texture_limit"}


def parse_value(raw: str):
    raw = raw.strip().rstrip("f").strip('"')
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        return float(raw)
    except ValueError:
        return raw


def main() -> int:
    problems = []
    for rel, (fields, pattern) in MIRRORS.items():
        text = (ROOT / rel).read_text()
        rows = {m.group(1): m.group(2) for m in re.finditer(pattern, text)}
        missing = [t for t in ORDER if t not in rows]
        if missing:
            problems.append(f"{rel}: tiers missing {missing}")
            continue
        for tier in ORDER:
            want = PROFILES["profiles"][tier]["render"]
            for field in fields:
                key = CAMEL.get(field, field)
                m = re.search(rf'["]?{field}["]?\s*[:=]\s*("[^"]*"|[\w.\-]+)', rows[tier])
                if not m:
                    problems.append(f"{rel}: {tier}.{field} not found")
                    continue
                got, exp = parse_value(m.group(1)), want[key]
                if (float(got) != float(exp)) if isinstance(exp, (int, float)) and not isinstance(exp, bool) else got != exp:
                    problems.append(f"{rel}: {tier}.{field} = {m.group(1)}, profiles.json says {exp}")
        print(f"{'✓' if not any(p.startswith(rel) for p in problems) else '✗'} {rel}")
    build = (ROOT / "scripts" / "build_blender_addon.py").read_text()
    if "profiles.json" not in build:
        problems.append("scripts/build_blender_addon.py does not bundle core/profiles.json with the validator")
    for p in problems:
        print(f"    ✗ {p}")
    print("Result: " + ("quality tiers are identical everywhere." if not problems else f"{len(problems)} mismatches."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
