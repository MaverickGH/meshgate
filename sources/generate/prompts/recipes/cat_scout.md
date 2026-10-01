---
title: Cat scout from a turnaround
keywords: cat scout, zombie cat, кот разведчик, кота, кот, кошка, kitten, котик
example: zombie_cat_scout.py
smooth_example: zombie_cat_scout_smooth.py
---
- For a clothed chibi cat use the scout example as a starting point, then measure the supplied reference. Work in named sections: legs, shorts, torso, arms, neck, head, ears, backpack, tail. Finish each silhouette before adding markings; inspect front, both sides and back.
- Keep shorts as TWO flared trouser legs below a shared waist, with a visible gap between them. A single wide shorts cube reads as a skirt. Put ragged hems on each leg separately.
- Build continuous head and body surfaces with `mg.mesh(vertices, faces, color, face_colors=...)`: use measured ring profiles rather than a stack of cubes. The central stripe belongs to the same surface as the fur. Broad, planned facets should follow the cheeks and jaw; lowpoly does not mean rectangular limbs.
- Avoid `mg.patch` for flat fur markings and stains on a faceted character: overlapping raised patches are unioned on join and can produce tiny sliver faces, lumps and noisy seams. Use face colours or a fitted thin surface. Keep polygons simple with vertices ordered around the boundary; crossing edges create black or missing triangles.
- Place eyes using `mg.bounds(head)`: the front of the eyeball must clear the socket. One lime iris with a dark vertical pupil, one milky eye. Modest emission preserves the pupil and lime colour.
- Match angular striped tails using `mg.tube(points, radius, ..., sides=4, smooth=False)` with decreasing radii. `mg.skin(..., subdiv=0)` also keeps a square chain; the default skin smooths the bends. Make cream bands along the path rather than assuming height always follows path distance.
- Layer a torn olive jacket over cream chest fur, a red triangular bandana, shoulder straps and brass buckles. Back view needs a boxy leather backpack with two straps and a round skull badge. Keep claws short and chunky.
- A successful build is not a visual match. Render it and compare the head/body ratio, ear silhouette, eye placement, clothing separation and tail bend against the sheet before reporting the result.

- Treat the scout example as a static visual study. Do not claim it is rigged or has morph sliders unless you actually add and verify those. Small details come after an acceptable multi-view silhouette.

- For a smooth stylized version use the smooth example and finish=none, not faceted. Subdivision on a loft needs support rings near the caps so shorts and sleeves keep their width. Measure the new surface before placing accessories; old faceted coordinates may now float.
- Build fingers and toes as branches of ONE mg.skin surface with explicit edges, or start every finger inside the palm along its local direction. Verify the skin is a connected mesh before joining it into the character. Ear bases must overlap the head; inner ears sit in the outer ear surface, not in front with a gap.

- A smooth head must have a neck that overlaps BOTH head and chest after subdivision. Weld those skin surfaces, and forearm/hand and ankle/foot surfaces, then check mesh connectivity. Bounding boxes alone can miss a wrist gap. Keep garments as separate layers over connected skin.
- Weld skin before painting the final coat: transferred palette UVs on boolean seams may contain mixed cells. Repaint a welded part uniformly first with mg.paint(part, base_colour), then paint its markings. For texture markings use a clean PBR bake (--pbr --texture 2k); avoid raised plates for dark eye sockets, scars, fur bands or faded clothing patches.

- Use mg.loft(rings, outline, colour, subdiv=0) for measured faceted silhouettes; rings are (cx,cy,z,half_width,half_depth), outline is counterclockwise XY. The same profile with smooth=True, subdiv=2 and optional support=.006 makes a smooth variant. Do not substitute spheres for the measured cheek/jaw profile.
- For organic joins use mg.union(parts, fillet=.007, relax=True); inspect overlap before welding. relax preserves volume while smoothing voxel steps. Keep hard garments out of that union.
- Match front width/height first, then side depth and muzzle projection, then back silhouette. Compare equal-scale renders in every supplied view before adding details. A texture cannot repair a wrong silhouette.

- Preserve local shading through the final join: smooth skin and eyeballs, deliberate planes on claws and torn rims. Global smooth shading can erase these designed edges.

- For smooth organic characters whose quad remeshing produces ribs or lumps, use mg.union(..., surface="voxel", relax=True) and smooth shading. Do not subdivide the dense voxel surface again. Keep the measured silhouette and inspect before painting.

- Seat eyes using mg.surface_point(head, (eye_x,-1,eye_z), (0,1,0)), then sculpt recessed sockets and raycast again for the final eye position. Bounds give overall depth, not the surface at the eye.

- Preserve the scout's broad jaw, recessed rectangular sockets and torn ear outline. Smooth shading must not replace these forms with a spherical head or painted circular eye patches. Cut sockets into the head with mg.cut, then raycast the rear wall to seat the eyes. Place the pupil beyond the eyeball's front surface.

- When matching quality remains poor, freeze the body and refine the head alone. Render large orthographic front and side closeups (`render_views.py` closeups with `ortho:true`) before accepting changes. Use evenly spaced cross-section samples to avoid loft ribs; build ear notches directly in a closed tapered mesh rather than cutting horizontal grooves through the ear. Keep an explicit shallow muzzle and check its connection in the side view. Compare the reference, never call a successful export a completed match.

- Seat whisker roots, fangs, nose and mouth AFTER welding the skin, using `mg.surface_point` on the final surface. Roots and tooth bases penetrate the skin. A nose spanning a curved muzzle needs a forward face that clears the intervening surface and a rear face embedded inside it. Paint inner ears on the welded skin with both an XZ contour and a distance-to-ear-plane test, so colour cannot leak onto the forehead. Crown tufts are welded into the head.

- Preserve mixed shading: organic head smooth, ear rim/tear faces crisp. Ears are closed shells with outer contour, inset recessed pink surface and rear thickness; their bases overlap the head. For a continuous anatomical join, smooth the root first, then weld the shell using surface="boolean" so the upper silhouette is preserved. Preserve local face shading through joining; source labels can be lost after Boolean/remeshing.

- The reference may combine smooth eyeballs with angular sockets and cheek planes. Match each independently: irregular polygonal recesses, slightly oval eyes, ears yawed outward rather than facing straight forward. Keep cheek-plane displacement subtle; large offsets produce side protrusions. Inspect the complete head in three-quarter and side views after every change.

- Visual acceptance requires an independent reference comparison, followed by correction and re-rendering. A successful build is only a technical check. For the scout head, widen ear shells before increasing yaw; use a convex rear shell, not parallel front/back polygons. Keep the broad muzzle upper ring and taper the lower jaw from the cheek corners; reducing eyes alone cannot fix a pinched muzzle.

- Embed tapered ear roots into the cranium rather than resting a broad bottom cap on the forehead. Contract the rear root separately from the upper ear contour. Pupil placement must match the actual eyeball depth; raycast or use its front surface rather than a fixed gap.

- Give ears a recessed bowl and convex rear surface, plus a modest root welded into the cranium. Keep the root below the visible inner bowl; an oversized sphere hides the bowl and looks like a separate bump. Preserve the lip and tears while blending the root. A muzzle can use two mirrored sloped front planes with a small transition at the centre instead of a rounded shelf.

- A head/ear overlap is not a finished anatomical connection. Verify one connected skin and inspect the root from the rear and side. Global ear smoothing melts tips and makes scalloped edges; blend the root only and preserve the upper hull with an exact boolean union. Use spatial inner-bowl masks after topology changes rather than source labels that remeshing can lose.

- Use `mg.union([smoothed_head, ear_shells...], surface="boolean")` to create a connected skin while preserving exact upper-ear topology. This mode skips remeshing, fillet and relaxation. Relax a narrow root band separately with bounded vertex displacement; do not smooth or project the whole upper shell.

- Check front surface Y at eye height and upper forehead in the side view. Moving upper ring centres backward while reducing depth compounds the slope and makes the whole face lean backward. Keep upper ring centres near the eye-height centre and reduce depth only near the crown. Keep the ear bottom lip shallow and inset its lower edge minimally; a thick inset produces a diagonal shelf across the forehead.

- Transfer the head assembly method to the body: a hidden hip/core volume and shoulder/thigh connections link the existing continuous paws and forearms. Weld these and the tail to the head/torso skin using exact union, check one connected component, and reapply limb/tail markings afterward. Preserve the approved head and ear vertices; garments keep their own crisp hems and thickness.

Руки и лапы: предплечье задавать несколькими овальными сечениями с расширением мышечной части и сужением запястья. Ладонь шире запястья, пальцы расходятся от общих корней и имеют разную длину. Голень сужается к щиколотке, стопа имеет подъём и три объёмных пальца; избегать одинакового цилиндрического профиля по всей конечности. Проверять силуэт спереди и сбоку после сшивки.

Для угловых конечностей и рукавов использовать `mg.loft_path` с независимой шириной/глубиной сечений. Контролировать толщину одежды над телом после расширения торса. Передняя, внутренняя и задняя стенки уха должны изменяться согласованно. Когти строить клиньями, погружая корни внутрь пальцев. Рваные края и заплаты задавать немногими крупными деталями, избегая мелкого шума.

Боковой ракурс: уши с цельным выпуклым задником на регулярных кольцах; передние вырезы остаются локальными. Пальцы кистей расходятся от общей ладони, кончики не сливаются в варежку. Окраска кончиков — тёмно-коричневая. Стопы с плоской подошвой и подъёмом, куртка с непрерывной оболочкой по спине и бокам.

Перед куртки строить из замкнутых изогнутых тканевых половин над грудной клеткой, с открытым животом и общим соединением с боковинами. Плоская экструзия контура не заменяет объём ткани. Для тонкой открытой поверхности доступен `mg.modify(panel, "solidify", thickness=.006, offset=1)`: толщину добавляет наружу, сохраняя исходную посадку. Ремни и пряжки подгонять к окончательной одежде через `mg.surface_point`, а не старые Y-координаты. Штанины имеют круговой рваный подол, общий пояс и объёмную перемычку; это не передние карточки поверх цилиндров.

Reusable base editor: use `mg.load_base` with the packed `samples/bases/cat_scout_v1.blend`, then declare native `mg.morph` controls (see `cat_character_base.py`). Preserve baked materials; do not recreate body parts or rebake a palette when adjusting the saved look. Static base only; no learned neural model or animation rig is implied.

- A torn ear's concave inner outline must be triangulated before adding bowl depth. Concentric rings about an arbitrary centre can cross the notches and create non-manifold seams after union. Keep boundary vertices shared with the lip; inset interior vertices behind the rim. Inspect the welded skin's connected component: no boundary, non-manifold or degenerate geometry. Restrict root smoothing to the ear attachment zones so it does not erase the central crown tuft. Evaluate yaw in front AND side closeups: an excessively turned ear hides its bowl.


- Scout face study v6: `sources/generate/examples/zombie_cat_scout_v6.py` is a separate reproducible revision; keep the v5 base intact. Use a shallow, unsubdivided muzzle loft with a broad upper ring and tapered chin; refine its two sloping front planes after welding rather than adding spherical cheeks. Preserve cheek corners in the measured head rings. Mirror six-sided socket contours about X (reverse winding on the mirrored side), give the top edges a slight outward slope and use minimal cutter bevel. Check a closed largest anatomical component after union, all six exported two-sided morphs, and front/profile orthographic views at the same 0.70 m frame. These changes improve the static study; they do not establish complete reference likeness or an animation rig. The reusable v6 base and controls are in `samples/bases/cat_scout_v6.blend` and `sources/generate/examples/cat_character_base_v6.py`.

- Face study v7 (`zombie_cat_scout_v7.py`, reusable `cat_character_base_v7.py`): raise sockets, eye centres, seating rays and associated forehead scars together by 25 mm; taper the upper cranium while leaving ears and body intact. Preserve the unsubdivided shallow muzzle's flat polygons by adding it in the final exact Boolean union AFTER the organic skin pass. Recut the six-sided sockets after voxel smoothing so their rim stays polygonal. Keep all previous bases. Validate the final skin's largest component, all six two-sided morphs, materials and strict GLB/FBX export; compare identical 0.70 m orthographic front/profile frames without textures first. This is a static improvement, not complete reference likeness; the skull remains rounder/wider and ears narrower than the sheet.
