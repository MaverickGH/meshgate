---
title: Creatures and characters
keywords: cat, kitten, dog, puppy, animal, creature, character, monster, zombie, beast, bird, fish, frog, mouse, rat, rabbit, bear, fox, wolf, horse, dragon, pet, mascot, person, human, figure, doll, plush, toy, кот, кошка, котёнок, котенок, собака, щенок, животное, зверь, существо, персонаж, монстр, зомби, птица, рыба, мышь, кролик, медведь, лиса, волк, лошадь, дракон, человек, фигурка, кукла, игрушка
example: zombie_cats/stylized/zombie_cat.py
---
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
