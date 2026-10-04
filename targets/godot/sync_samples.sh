#!/usr/bin/env bash
# MeshGate — copies the repository's samples (and example packs) into the Godot demo project (res://samples/).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../../samples"
mkdir -p "$HERE/MeshGateDemo/samples"
cp "$SRC/"meshgate_*.glb "$HERE/MeshGateDemo/samples/"
for pack in "$SRC"/packs/*/; do
  [ -d "$pack" ] || continue
  name="$(basename "$pack")"
  mkdir -p "$HERE/MeshGateDemo/samples/packs/$name"
  cp "$pack"*.glb "$pack"index.json "$HERE/MeshGateDemo/samples/packs/$name/"
done
ls -R "$HERE/MeshGateDemo/samples/" | head -40
