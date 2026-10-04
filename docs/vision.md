**English** · [Русский](vision.ru.md)

# MeshGate vision

The goal is a repeatable, agent-driven pipeline that brings a 3D asset
to an "engine-ready" state and delivers it to any runtime. Like a skill:
provide an input → get a verified asset in the web and in engines, without the manual loop
"exported — wrong scale/no unwrap in the engine — re-exported".

## Inputs: meshes can be made in different ways
1. **From a description (text → 3D).** Draft geometry is generated from a text prompt (open models like TripoSR/InstantMesh or an external API), followed by refinement per the contract.
2. **From an image (image → 3D).** A mesh is reconstructed from a reference image.
3. **An existing model.** An already made asset from Blender/Maya is brought to the contract.

Any input is reduced to one normalized GLB.

## Engine-readiness (what engines need)
The asset goes through refinement to meet engine requirements:
- **UV unwrap** — without it textures will not line up;
- sane **topology** (clean normals, no flipped faces, reasonable polycount);
- **scale/axes** per the contract (meters, Y-up);
- **PBR materials**;
- **LOD** levels for distant views;
- **collisions** (a simplified collision mesh);
- clear object/material **names**.

The validator catches violations before the asset reaches the engine.

## Delivery
One canonical GLB → web (Three.js), Unity (glTFast), Godot (native), Unreal (native/Interchange). An FBX/USD fallback path for rigs/large scenes. Sources: Blender and Maya.

## Why this helps game development so much
The most expensive part of an asset pipeline is not modeling but refinement and transfers between
tools and engines. MeshGate removes this routine: generation or import →
automatic refinement to the contract → predictable loading into any engine and the web.

## Order of work
First we bring **web** up to the reference level, then **Unity**, then **Godot/Unreal**,
then mesh generation (description/image + engine refinement), and finally **Maya**
as the second source.
