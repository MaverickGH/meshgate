---
title: Creatures and characters
keywords: cat, kitten, dog, puppy, animal, creature, character, monster, zombie, beast, bird, fish, frog, mouse, rat, rabbit, bear, fox, wolf, horse, dragon, pet, mascot, person, human, figure, doll, plush, toy, кот, кошка, котёнок, котенок, собака, щенок, животное, зверь, существо, персонаж, монстр, зомби, птица, рыба, мышь, кролик, медведь, лиса, волк, лошадь, дракон, человек, фигурка, кукла, игрушка
example: zombie_cats/realistic/zombie_cat.py
---
- Block the whole body as ONE `mg.blob`: hips, belly, chest, neck, head, cheeks, muzzle, chin as overlapping balls
  and ellipsoids; limbs as capsules inside the same blob so shoulders and hips melt in. Cut eye sockets with
  `"cut": True` balls and sit the eyeballs in them.
- Proportions first, detail later: for a cartoon or chibi look the head is 30–40 % of the height; for a real animal
  measure against the real one (a house cat: body 0.45 m, shoulder 0.25 m, head 0.1 m).
- A pose sells the character: arms forward for a zombie, weight on one leg, a tilted head. Put it in the shapes
  (capsule end points), not in rotations afterwards.
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
