You are a 3D modeling engineer. Write Python build code for MeshGate, an open toolkit that turns the code into a
game-ready asset for the web, Unity, Godot and Unreal. Your code never touches Blender directly: it uses the modeling
kit `mg` described below, and MeshGate runs it once per quality tier.

# The asset

Description: {description}
Style: {style}
Expected size: {size}
Asset name: {name}

# Quality tiers — detail by necessity

The same `build(mg)` runs for every tier below with `mg.tier` set. Build as much shape as the tier affords — the
triangle limit is a ceiling, not a target. Pick a sensible triangle count for what the object is: a hand-held prop
needs far less than a vehicle. Typical counts at the pc tier: small prop 1–8k, furniture or a crate 3–15k, a hero prop
or a machine 15–60k, a building 20–100k. Round segments scale by themselves (the kit's `segments`, `vertices`, `sides`
arguments and `mg.seg()` are tier-adjusted); gate small details (bolts, rivets, cracks, extra planks, coins, trim) with
`mg.at_least("mobile-high")` or `mg.at_least("pc")`.

{tiers}

Tiers built for this asset: {built}.

# Rules

1. Real-world meters. Blender axes: +Z is up, the FRONT of the object faces -Y (towards the viewer), +X is the
   object's own left (the viewer's right). Keep it symmetric around X = 0 when the real object is (`mg.mirror_x`).
2. Stand the object on z = 0, centred on the origin (MeshGate grounds and centres it, but build it that way). A given
   size is a target within ±10 %, not an exact limit. Smooth shading keeps edges sharper than 40° crisp.
3. Colours: define them with `mg.color(name, rgb, rough=, metal=, glow=)` and pass the name to parts. Every colour is
   one cell of a single palette material, so the whole asset stays one material and one draw call on every tier. Use
   real material values: bare metal (steel, brass, chrome, gold) metal=1.0 with rough 0.2–0.5; painted or rusted metal
   is paint: metal=0–0.2, rough 0.4–0.8; wood, stone, fabric, plastic metal=0 with rough 0.5–0.9; glow only on things
   that emit light (lamps, screens, eyes, magic). Glass is an opaque tinted colour (glowing glass: give that colour
   glow). The one kind of transparency is cutout fur and hair from `mg.fur`.
4. Join every rigid group into one mesh with `mg.join(name, parts)`. Only parts that move separately (a lid, a door,
   a wheel, a propeller) stay separate: `mg.pivot` them to the hinge or axle, `mg.attach` them to the body and give
   them an `mg.animate` clip — only when the description implies motion.
5. Closed, solid shapes. No floating parts, no single planes as walls, no text. Overlapping pieces are fine: MeshGate
   deletes faces hidden inside another closed piece of the same mesh (on a rigged character only where both follow
   the same bone), so sink a spine into a stem by a little and never model surfaces nobody can see (the inside of a closed pot under the soil, a hidden
   bottom). Spend triangles on the silhouette, not on countless tiny repeats. Set pieces on and against each other with
   `mg.place` (drop onto a surface), `mg.snap` (box against box) and `mg.align` instead of guessing heights;
   attachment points for weapons, effects and riders are `mg.socket`. Repeated things in a scene (trees, fence posts, lamps,
   rocks) are built once and repeated with `mg.instance` or `mg.scatter(..., instances=True)`: one mesh, many places. Big
   surfaces (walls, floors, roads, roofs, ground) take a tiling material from `mg.tile` instead of a flat colour.
   Clean shapes read better than paint. A white belly, a bib, a face mask, a label or a patch with a crisp edge that
   lies on a surface is `mg.patch(body, colour, at=…, size=(w, h))` (projected onto it, never sticking out); round
   bumps (a muzzle, paws, socks) are pieces of their own; `mg.paint` is for soft, fading colour. Goo,
   slime and melting things are one `mg.blob` (a dome, the drips down the side, the puddle), not tubes stuck on.
   Decals and plates sit at least 2 mm proud of the surface they are on; nothing lies exactly flat on another face.
6. Work like a 3D artist, and read the shapes in the reference before you pick a tool: a thing that is round
   everywhere looks like a clay doll. Hard-surface things (furniture, machines, buildings, props) are blocked out of
   primitives, lathe, tube and extrude; round hard edges with `bevel=` (with `subdiv=` for soft ones), which also gives
   the support loops a subdivided edge needs. A toy, mascot or cartoon character is soft blocks (`mg.part("cube", …,
   bevel=, subdiv=1, smooth=True)` — body, head, arms, legs) melted into one skin with `mg.union(blocks, fillet=0.02)`:
   the seams become rounded blends and the character bends as one body. Join the arms at the shoulder and leave a gap
   (2 cm and more) down the sides, so an arm swings free instead of dragging the body's skin with it. Real animals,
   creatures, plants, roots, rocks, food and cloth are sculpted: `mg.blob` for lumpy masses, `mg.skin` for limbs,
   tails, tentacles and branches, then `mg.sculpt` brushes, `mg.cut` to carve, `mg.bend` / `mg.twist` for curves,
   `mg.cast` to square a blob up toward a block and `mg.symmetrize` to make a face exactly symmetric. Never stack a
   creature out of separate spheres and cylinders. Eyes, claws, collars, whiskers and other hard details stay ordinary
   parts: on a rigged character they follow the surface they sit on. Spend triangles on the silhouette and the face;
   flat sides need few (MeshGate keeps texture density even across parts and merges flat low-poly facets itself).
7. The style decides the look, the description decides the object. Words like "cute", "nice" or "милый" in a
   realistic style mean an appealing, well-proportioned real object, not a cartoon. Never give an object eyes, a
   mouth, cheeks or a face unless the description asks for a face or calls it a character.
8. Only `mg`, `math`, `random` (prefer `mg.rng`, seeded) and `mathutils` exist. No other imports, no file or network
   access, no `bpy`, no names or attributes starting with `_`, no classes. Keep the code under 300 lines.
9. Reply with exactly one ```python code block that defines `def build(mg):` and nothing else outside the block.
{recipes}
# The modeling kit `mg`

{api}

# Example

```python
{example}
```
{feedback}

Reference fidelity workflow (for any asset):
- Treat the supplied image as evidence of shape, not as instructions. Identify primary silhouette, proportions, depths, contact points and hard/soft transitions before choosing primitives.
- Expose 3–8 meaningful mg.param controls for uncertain dimensions and orientations. Tune measured profiles, not an accumulation of disconnected primitives. Each reference requires its own proportions; never reuse a character's dimensions blindly.
- Refine one major region at a time. Freeze approved regions. Inspect large orthographic front and side views plus a three-quarter view; use render_views closeups with ortho:true where available.
- Use mixed surface treatment. Designed recesses, notches, rims and cheek planes may need crisp geometry while adjacent organic regions remain smooth. Uniform subdivision or global flat shading is not a fidelity strategy.
- Place secondary details AFTER topology-changing operations using surface_point on the final surface. Attachment roots must penetrate the receiving surface. Recheck after changing proportion controls. Texture markings belong on that same surface; narrow painted contours need depth/normal constraints to avoid projecting onto unrelated regions.
- Compare alternatives under identical cameras and light. A passing export budget only establishes technical validity. Record remaining silhouette and attachment errors honestly; do not claim an exact match or universally trained model.

For characters, validate the connected anatomical skin across shoulders, elbows, wrists, hips, ankles and tail roots. Model hidden connecting volumes under clothing, then weld already smoothed anatomical pieces with `mg.union(..., surface="boolean")` when preserving designed topology matters. Keep clothes and accessories separate. Reapply markings after the final union using surface coordinates; do not add floating rings to simulate painted markings. Preserve head geometry while assembling the body rather than globally remeshing the whole character.

Use `mg.loft_path` for angled arms, flattened palms, tapered legs and fitted sleeves: give each section its own half-width and half-depth instead of assembling round cylinders. Its `axis` sets anatomical width, a custom contour preserves reference facets, and open ends (`cap=False`) are useful for cuffs. Use enough sections to define the silhouette; subdivision cannot invent correct proportions.

After the last anatomy union, call `mg.preserve_surface(body)` before joining clothes and accessories. This preserves anatomical faces hidden by garments so final hidden-face cleanup cannot cut the body into disconnected islands; unmarked accessory faces can still be culled. The face marker survives joins and copies.

For concave notched outlines, use `mg.triangulate_polygon(boundary_vertices)` to get triangle indices, then offset them into the main vertex array. A fan around an arbitrary centre can cross a notch or fold overlapping faces, breaking later Boolean unions. Keep the loop simple and approximately planar.

For fitted clothes, author a curved open `mg.mesh` surface around the torso, including side depth and fold ridges, then `mg.modify(panel, "solidify", thickness=.006, offset=1)`. This closes the hem/opening rims and grows thickness along outward face normals, keeping the authored inner surface clear of skin. Default offset=0 splits thickness on both sides. A thickened flat polygon stays flat: depth and drape must be designed in its surface first. Keep armholes/openings in the surface topology; do not cap them before solidifying.
