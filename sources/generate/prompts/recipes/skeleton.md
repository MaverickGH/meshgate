---
title: Skeletons and bones
keywords: skeleton, fish bones, fish skeleton, bone, bones, skull, ribs, spine, vertebra, fishbone, fossil, remains, carcass, скелет, скелеты, скелетов, кость, кости, костей, костями, череп, черепа, рёбра, ребра, рёбер, позвоночник, останки
example: zombie_cats/realistic/bones_pile.py
---
- Spines are one `mg.curve` through 6–10 points with shrinking radii, vertebrae as short discs threaded on it
  (a loop over the curve points, each `cyl` turned to the local direction).
- Ribs are `mg.curve` arcs with 3–4 points and radii tapering to a point, all sweeping the same way (toward the
  tail); long under the belly, shorter along the back. Fin rays fan out from one point.
- Skulls are a small `mg.blob` (cranium, snout, cheek plates) with the eye sockets cut, the socket painted dark,
  a hanging lower jaw as a curve and needle teeth as tiny cones on the rich tiers.
- Bones lie on the ground: the thickest part touches z = 0. Several skeletons in a pile: build each at its own
  place and angle (transform the points yourself) instead of copying, and lift the top one a little.
- Colours named "bone" get pores and grime in the realistic finish; paint older, yellowed patches with `mg.paint`.
