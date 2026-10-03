**English** · [Русский](reference-modeling.ru.md)

# Building a character after a reference with the kit

The current example is a procedural approximation, not a recovered original model. A drawn turnaround can contradict
itself between views, and its hidden geometry is not given. To match a picture, measure the result and correct it —
more polygons alone do not get you there.

## What the kit supports

- `mg.mesh(vertices, faces, color, face_colors=...)`: a surface laid out by hand — cheeks, ears, clothing panels.
- `mg.loft(rings, outline, color, subdiv=0, support=0, bands=None)`: a closed profile. A section is
  `(cx, cy, z, half_width, half_depth)`, the XY outline runs counter-clockwise, heights increase. `subdiv=1..2`
  rounds the same profile; `support` keeps the edges of clothes.
- `mg.skin(..., subdiv=...)`: connected branches for fingers and paws.
- `mg.union(parts, fillet=.007, relax=True, surface="voxel")`: organic pieces stitched together and the surface evened
  out while keeping its volume. The pieces must overlap first. Clothes stay a layer of their own.
- `mg.shade(obj, 'smooth')`: smooth normals without the hard-surface finishing; `flat` keeps facets, `weighted` suits
  bevelled hard shapes. Apply after the final join when the whole object should use that mode.
- `mg.paint` with `--pbr --texture 2k`: painting and baking. Stripes, spots and scars need no raised plates. After a
  union, paint the base colour again first.
- `mg.surface_point(obj, origin, direction)`: the point and normal where a ray first meets a piece — eyes and
  accessories sit on the real surface.

## Order of fitting

1. Bring the views to one height and floor line. Fix the top of the head without the ears, the chin, shoulders, waist
   and knees. Do not measure perspective 3/4 views as if they were orthographic.
2. From the front view set the width of the head and body at every height; from the side, the depth of the head, how
   far the muzzle sticks out and where the backpack sits. Put those sizes into the loft.
3. Check one-colour views from the front, side and back. Fix the silhouette before any texture. Compare the negative
   space too: between the legs, between an arm and the body, between the ears.
4. Build the eye sockets as recesses in the head. Check where the eyes sit, the plane of the muzzle and the jaw. A
   dark texture alone does not make a socket deep.
5. Build the outlines of torn ears, sleeves, jacket and shorts with `mg.mesh`; give the clothes thickness. Fingers
   share their roots with the palm, the neck runs into both head and chest.
6. Paint: the centre stripe, the pink inside of the ears, scars, bandages, cloth stains, the skull on the backpack.
   Keep geometry for the details that change the silhouette.
7. Compare every view with the same camera, scale and light; check a grey material and the wireframe separately. Only
   then export and check the budget.

## What is left for an exact cat

The smooth example uses a widened cheek profile, cut rectangular sockets and bites out of the ears. The jaw, the torn
edges of the clothes, paws and tail, where the accessories sit and the colours still need fitting to the reference.
Outlines compared over every view of a sheet and a part-by-part fit (`mg.section`) come with
`gen --image … --views …`; an outline does not judge the face or the topology.

Examples: `sources/generate/examples/zombie_cat_scout.py` and `zombie_cat_scout_smooth.py`. The generator's recipe:
`sources/generate/prompts/recipes/cat_scout.md`. The API check in Blender: `tests/generate/loft_character.py`.

For local fitting over MCP: `blender_mesh` → `blender_edit` with the current revision. Move, scale, smooth, inset,
extrude, bridge, subdivide and symmetrize are there; `blender_edit_undo` takes the last edit back. Subdivide adds
control points without rounding, symmetrize copies the chosen side across the world X plane. These changes stay in the
live scene and the export; for a build you can repeat, carry the final shape into the source recipe.

After the head was checked on its own, its joins were carried over to the body: shoulders, forearms, hands, hips,
shins, feet and tail make one connected anatomical mesh. Clothes stay a separate layer. Check the overall views and
large orthographic views of the head from the front and the side. In `render_views.py` a close-up takes `ortho:true`,
`at`, `from` and `size` in metres, to check the profile and the eyes without perspective. The head outline uses even
angular samples; the bites out of the ears are part of the closed mesh's own outline. Before fitting other parts, keep
the accepted head silhouette and check it in every overall render.

## Repeatable fitting, not "training any model"

General rules for comparison and placing details are in `sources/generate/prompts/model.md`; the cat's specifics are in
its recipe. These are instructions for the generator and a procedural model, not new weights for a neural network. A new
object needs its own measurements and control views.

The smooth example has `ear_yaw` (0–65°), `cheek_width` (0.88–1.12) and `head_depth` (0.85–1.15):
`--params '{"ear_yaw":60,"cheek_width":1.0,"head_depth":1.0}'`. A new head size needs the ears and eyes checked again:
the parameters do not promise to refit everything attached.

To stitch surfaces that are already fitted there is `mg.union(parts, surface="boolean")`: an exact union without a new
voxel pass. It keeps the outlines of the ears and the head; `fillet` and `relax` do not apply. The ear roots are evened
out locally, with a limited shift of vertices. Stripes and the inside of the ears are painted after the final union. A
connectivity check confirms the geometry joins; it does not replace looking at the silhouette and the clothes.

## New tools for fitting and checking

`mg.loft_path(sections, color, axis=(1,0,0), sides=12)` builds a volume along a path in space. A section is
`(x, y, z, half_width, half_depth)`; width and depth change independently — a forearm with a thin wrist, a wide oval
sleeve, one continuous profile. `outline` sets a custom contour, `smooth=False` keeps flat planes, `subdiv` rounds the
volume. The cat example uses it.

`blender_mesh` returns `quality` for the whole base mesh of the object, whatever page of vertices was asked for: the
number of components, the size, boundaries, non-manifold edges, loose vertices and edges, degenerate faces. The IDs it
returns let `blender_edit` pick the problem spot. The border of open clothing counts as non-manifold; separate eyes,
claws and accessories do not mean the anatomy is torn. Read this together with the renders.

Checks: `tests/blender/test_loft_path.py` and `tests/blender/test_live_quality.py`, run through Blender with
`--python-exit-code 1`; `tests/blender/inspect_model_quality.py` checks a saved build.

`mg.preserve_surface(body)` is called after the last union of the skin and before the `join` with the clothes. It keeps
the body's faces under the clothes from being removed — a whole anatomy matters for a rig later. The marker lives on
the faces and survives unions and copies; accessories are still cleaned up. It raises the mesh budget, so pick the
density that keeps the silhouette rather than removing connecting surfaces. The check that reproduces the tear and its
fix: `tests/blender/test_preserve_surface.py`.

For concave outlines use `mg.triangulate_polygon(vertices)` and pass the indices it returns to `mg.mesh`. A fan from an
arbitrary centre can cover the notches even when every edge has two faces; on the ears that caused self-intersections
after a Boolean union. The check: `tests/blender/test_triangulate_polygon.py`. A closed mesh before the union does not
prove it has no self-intersections.

## Checking the volume from the side

The back shell of an ear has its own smooth convex profile; do not copy the front notches through the whole thick back.
Regular nested rings give a steadier profile than moving the centres of narrow triangles. A hand is a palm with
fingers spreading out: their bases overlap, their tips stay apart. A foot has a flat sole, a heel and an instep. The
back of the jacket wraps the sides in one shell over the anatomy. The current cat follows all of these; after a change,
check the full Boolean and the saved export, not only the separate shells.

Finishing removes only faces of exactly zero area, with no visible surface, and keeps UVs, paint and the anatomy's
protection. Small non-zero triangles are not removed automatically. This repairs damaged faces but does not close the
open edges of accessories; the check is `tests/blender/test_zero_area_cleanup.py`.

The front of the jacket is now a closed curved shell stitched to its sides. Straps are placed by rays on the finished
cloth, buckles turn to its normal. Each trouser hem has a solid outline all round. For open cloth surfaces,
`mg.modify(panel, "solidify", thickness=.006, offset=1)` keeps the inner surface and grows the thickness outwards (the
check: `tests/blender/test_cloth_shell.py`). Thickness alone does not make a flat panel fit: design its curve first.

### A saved base and an editor for its proportions

`mg.load_base(path, ratio=.07)` loads a static finished `.blend` with its UVs, materials and packed images. The path
can be relative to the MeshGate folder. Reduction runs after the source model is baked and before new `mg.morph`s are
made. A rebuild starts from the Basis, so changes do not pile up. Rigs and animation are not supported by this loader
yet.

`sources/generate/examples/cat_character_base.py` uses `samples/bases/cat_scout_v15.blend`. Studio's Appearance has six
sliders: head width and depth, body width, leg length, paw and hand size. They change the finished mesh without a new
generation; Save the look rebuilds the export from the same base. The GLB carries two-sided morphs. This parametrises
a saved character; it is not a trained network or a generator of any character. The base's likeness to the reference
still needs an artist's work.

### Comparing and saving live edits

`blender_view(reference={"image": "/absolute/reference.png", "views": ["front", "3/4front", "left", "back", "right",
"3/4back"], "fixed_views": true})` uses the outline comparison with four fixed orthographic cameras. It helps judge
proportions; an outline IoU does not judge the face or the topology. Without it the cameras stay in perspective.

After editing by hand or with `blender_edit`, call `blender_save_base(path="/absolute/bases/cat_v3.blend",
note="what changed")`. Only MeshGate live is saved, with its geometry and packed textures — no other scene of the
artist's. An existing path is refused. A JSON with SHA-256 and the list of objects is written next to it. The next build
uses that version through `mg.load_base`; earlier versions are kept. It does not write hand edits into the procedural
source. A running live link needs a restart after an update.

`blender_reference(path="/absolute/front.png", view="front", height=1.02)` adds a packed half-transparent plane to the
live scene. Use a separate image for each view, not the whole turnaround. References are hidden from renders. Undo keeps
the last ten edits; a manual change of the mesh still protects against a stale undo.

Studio → Parts → **Blender base**: load the chosen asset into MeshGate live, save a separate base to
`<asset>/bases/revision_*.blend`, undo a live edit, show the last saved comparison. After a successful save Studio
switches the source of the next build to that revision: `base.json` keeps the relative paths of the base and of the
code with `mg.load_base(..., morphs=True)`. The choice survives a restart of Studio. In live the morphs are switched off
while the geometry is edited; their definitions stay in the base and come back at the build. The compare button shows
the existing report and does not render a new one. After a restart of Studio, load the model again before saving.

### Clothes and materials

The kit has `mg.tile(..., "fabric", ...)` and `mg.tile(..., "leather", ...)`: repeating colour, normal and ORM maps with
their scale in metres — 0.065–0.08 m for the cat's cloth, 0.10 m for leather. The maps are packed into the Blender base
and kept when it is loaded and exported to GLB. The helper paint `mg_paint` is removed after the bake so glTF does not
darken the textures through COLOR_0. Texture does not fix the head's silhouette or the body's proportions: judge a
geometry change apart from the materials.

The jacket and shorts are made with `mg.garment`, the straps with `mg.strap`. `regions` picks a union of areas by face
centres; `refine=0/1/2` adds cloth detail before the fit. The jacket's opening is cut by planes and its inner surface
is fitted outside the skin before the thickness is added. In a tight concave area a big gap does not guarantee a good
fit: the shorts use a 3 mm gap and 2 mm thickness. The arm bandage has open ends.

The closed walls of clothes are protected from the hidden-face cleanup; `garment` and `strap` do it themselves.
Reduction marks components that were closed at the source, removes flat leftovers that lost their volume and repairs
small triangular holes, carrying their UVs and materials. Surfaces that are open on purpose are not closed. The check
`tests/blender/test_load_base_closed_shells.py` looks at all four clothing roles before and after finishing and after a
real GLB / FBX export, with UVs, 15 textures and 12 morph targets.

The neutral shape, each of the six sliders at ±1 and the extremes together — 15 states — were checked: no vertex or
face centre of the jacket, shorts, red bandages or straps goes more than 1 mm into the skin (rays through the closed
skin, not the sign of the nearest normal). This samples static morphs; skeletal animation was not checked. The
regressions: `tests/blender/test_garment_regions.py`, `test_garment_concave_fit.py` (also `-- --self-test` for a sphere
and the concave hole of a torus), `test_saved_base_geometry.py`, `test_load_base.py`, `test_cat_base_morphs.py`,
`test_character_materials.py`.

### v15: ears and scarf

The ears are wider and shorter, their outer edge has large stepped tears; the 3 mm scarf has soft folds, an off-centre
knot and tails of different length. Skull, body and feet are as in v14. The character: 16,898 triangles, 8,633
vertices, six two-sided sliders, five materials and 15 textures. After the reduction four places where the upper part of
the right back strap went into the body were fixed by a local smooth lift. All 15 morph states pass the fit check
(vertices and face centres, 1 mm). The clothes are closed, the skin has no topology errors; PBR and the strict GLB / FBX
validation pass. The pattern of the tears is not an exact tracing of the reference, and there is no cloth physics.

### The version in the repository (v0.6.9)

A loaded base fits every tier by itself, the way an artist makes phone LODs of a hero model: where the tier's triangle budget is smaller it is reduced before the morphs; its textures are scaled to the tier's size and memory; and where it has more materials than the tier allows, the whole model is baked into one material — a second, fresh unwrap that bakes from its own materials (their textures pinned to the old UVs), so nothing under the clothes or behind an eye is caught by mistake. The cat v15: PC and mobile-high keep its five materials (textures 96 → 28 MB on mobile-high), mobile-mid gets one 1024 px atlas, mobile-low 7,185 triangles and a 512 px atlas. Light tiers keep the morph sliders that fit their file budget.


The repository holds the latest version, v15: `sources/generate/examples/cat_character.py` (the prepared base
`samples/bases/cat_scout_v15_editable.blend` with six sliders), `cat_character_base.py` (the full base
`cat_scout_v15.blend`, reduced for a game) and its procedural source `zombie_cat_scout_smooth.py`. The working versions
v1–v14 stay on the author's disk and are not in the repository.
