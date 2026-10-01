---
title: Creatures and characters
keywords: cat, kitten, dog, puppy, animal, creature, character, monster, zombie, beast, bird, fish, frog, mouse, rat, rabbit, bear, fox, wolf, horse, dragon, pet, mascot, person, human, figure, doll, plush, toy, кот, кошка, котёнок, котенок, собака, щенок, животное, зверь, существо, персонаж, монстр, зомби, птица, рыба, мышь, кролик, медведь, лиса, волк, лошадь, дракон, человек, фигурка, кукла, игрушка
example: zombie_cats/stylized/zombie_cat.py
---
- For a character sheet, first measure head width/height, shoulder width, hips, feet and ear tips. Use
  `mg.mesh(vertices, faces, color, face_colors=...)` for continuous planned polygon surfaces when primitive blocks
  cannot match the silhouette. Markings can share those faces instead of being protruding patches. A faceted
  character needs broad clean planes, not many tiny facets or a rectangular shape for every part.
- Read the shapes in the reference before choosing a tool, and do not default to balls: a character that is round
  everywhere looks like a clay doll. A toy / vinyl-figure / game-mascot character is blocks with soft edges — a boxy
  body with a flat front, a wide head box sitting right on the shoulders, straight arm and leg blocks — each a
  `mg.part("cube", …, bevel=…, subdiv=1, smooth=True)` (bevel about ¼ of the block's thinnest side; the low-poly
  finish turns it into one flat chamfer), all melted into one skin with `mg.union(blocks, fillet=0.02–0.03)` —
  round shoulder pieces join the arms to the body, a gap runs down the sides. Keep balls for what is round in the picture: paws, a muzzle, eyes, a belly
  patch. An organic body that bends (a real animal, a snake, a tentacle) is ONE `mg.skin` over a skeleton of points
  with `edges=` for the branches — clean quads with loops at every joint. A single `mg.blob` of balls is for lumpy
  things only (a slime, a boulder). Sink touching blocks a centimetre into each other, or leave a clear gap (2 cm
  and more): a gap of a few millimetres bakes into a dark smudge.
- Dress a character the way a character artist does: the body first (fur or skin), then the clothes over it with
  `mg.garment(body, cloth, above=, below=)` — a layer of the body's own surface with thickness, `open_front=` for an
  open shirt (the chest shows through), `along=` + `span=` for a sleeve — then straps with `mg.strap` along a path over
  the clothes (suspenders from the belt in front, over the shoulder, to the belt behind), buckles with `mg.buckle`,
  gear with `mg.pouch`. Clothes made as blocks with the body painted on them read as a toy; layers read as a character.
- Then detail, the way the sheet shows it — a clean blocky model with none of it reads as a toy box: torn cloth with
  `mg.fringe` (a hem at a height; a sleeve with `at=` its end and `axis=` back into it), bandages, belts, bracelets and
  raised stripes with `mg.wrap` round the limb (`slant=` for a bandage), scars and seams with `mg.stitch`, pouches,
  buckles, straps, toes and claws as small pieces, tufts that break the outline (cheeks, elbows). Measure the piece
  first with `mg.bounds` and put the details on its real surface.
- Read the finish of the sheet, not only its shapes: flat facets everywhere (a low-poly render, hard shading steps
  on the head) mean the low-poly style. Build such a head as a cube with a wide two-step bevel (`bevel` about a
  quarter of its depth, `bevel_segments=2`, a taper for the crown and the chin) — a many-sided head with flat front
  planes that carry the face; an icosphere head is faceted too, but its markings and sockets smear across the facets.
- Markings go on round the form the way the other views show them: a stripe down the face runs on over the crown and
  down the back of the head (`mg.wrap` round the head's left-right axis plus a `facing=(0, 1, 0)` patch behind); a
  patch round one eye reaches the forehead and the cheek. Worn clothes get faded patches, holes with the fur showing
  and stains — small `mg.patch`es on the garment, on its front, back and sides.
- Check every side against its own view: in the BACK view the character's right is on the image's right, so a tail
  that swings to one side must swing the same way in the back and the 3/4 back views; the arms' A-pose angle is
  measured in the front view (about 45° down is common), not guessed.
- Build it part by part, each in its own block — `with mg.section("head", anchor=neck_point):` … — head, ears,
  torso, arms (anchor = the shoulder), legs, tail, clothes and gear: MeshGate then compares every part with the
  reference on its own (how much wider, deeper, taller, higher it is drawn), fits each part by itself and tells you
  which part to fix first.
- Give a character a character creator, as games do: 4–10 `mg.morph` sliders at the end of build, the most wanted
  first — head size and width (`above=` the neck), ear size (`pieces=` the ear, `mirror=True`), eye size, muzzle,
  belly (`inflate=`), leg length (`stretch=(ankle z, hip z, metres)`), tail length. Scale round the point a part grows
  from (an ear's base, the hip), so it stays attached.
- Proportions first, detail later: for a cartoon or chibi look the head is 30–40 % of the height; for a real animal
  measure against the real one (a house cat: body 0.45 m, shoulder 0.25 m, head 0.1 m).
- A pose sells the character, but model the arms relaxed at the sides: the clips move them (a zombie walk holds them
  out in front), and the A-Pose / T-Pose setting raises them for the file's rest pose. Weight on one leg or a tilted
  head goes in the skeleton points, not in rotations afterwards.
- Paint the coat like a real animal: pale muzzle, chest and belly (`facing=(0, -1, 0)`), darker back and head top
  (`facing=(0, 1, 0)` / `(0, 0, 1)`), socks (`below=`), stripes as small overlapping regions; `rough=0.3–0.6` for
  natural edges. Colours named "fur" get the fur material in the realistic finish.
- Sculpt last: `noise` for a mangy coat (realistic only), `crease` along eyelids, mouth corners and scars,
  `inflate` negative for wounds and cheeks. Stitches are short thin tubes across the seam.
- Hard details stay parts: eyes (with a pupil in front), nose, claws (cones), collar (torus), bell, whiskers (thin
  tubes on mobile-high and up). Ears are cones with a flatter pink cone in front; tear one with `mg.cut`.
- Tails, tentacles and horns: `mg.skin` through 4–6 points with shrinking radii, then `mg.bend` if it should curl.
- Sharp features the clay cannot make come from the sharp brushes on the snapped surface: `ridge` + `pinch` for
  eyelids around the sockets, brows and lips, `crease` + `pinch` between fingers and toes, `layer` for paw pads.
- Eyes: `mg.eye(center, radius, iris, look=…, pupil="slit")` in each socket — glossy, with iris rings and depth.
- A coat: `mg.fur(body, length=…, count=…, droop=…)` over the painted body (not the face: limit it with `below=`
  or `at=` + `facing=`); it takes the painted colours and is skipped on low tiers by itself.
- A character that moves gets `mg.rig(joined_body, joints)` after the join (hips, chest, neck, head, head_top,
  shoulder/elbow/hand, hip/knee/ankle/toe on the left; the right is mirrored; `tail=` points) and clips with
  `mg.clip("idle", "idle")`, `mg.clip("walk", "zombie_walk" or "walk")`, `mg.clip("attack", "attack")`.
- Tails, whiskers and tentacles read best as `mg.curve` (smooth splines); fur tufts, warts or spikes can be
  `mg.scatter`ed over the body on the richer tiers.
- Spend triangles where eyes land: `mg.focus(face_centre, radius)` on the face and hands makes them denser within
  the budget; MeshGate reports pieces that float free by their code line — sink them into what they belong to.
- Markings with crisp edges that lie on the body (a white belly or chest, a bib, a face mask) are `mg.patch(body_piece,
  pale, at=…, size=(w, h))` — projected onto the surface, so they never stick out at their edges; round bumps (a
  muzzle, paws, socks) are pieces of their own; paint is for soft, fading patches. Fur cards shimmer at game resolution: use them for a few tufts, not a whole coat.
