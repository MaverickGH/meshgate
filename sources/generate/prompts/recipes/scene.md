---
title: Scenes and environments
keywords: scene, level, environment, diorama, forest, glade, grove, street, village, camp, park, garden, yard, field, graveyard, market, alley, square, лес, поляна, роща, сцена, уровень, окружение, диорама, улица, деревня, лагерь, парк, сад, двор, поле, кладбище, рынок, площадь
example: forest_glade.py
---
- Model a scene the way a level artist does: a few pieces built well, then placed many times. Every repeated thing —
  trees, rocks, lamps, fence posts, crates, benches, gravestones — is built once and repeated with `mg.instance`
  (one copy at a place, turned about the vertical) or `mg.scatter(..., instances=True)` (many over a surface).
  The file then stores each mesh once and engines draw the copies together.
- Keep the unique pieces few (a handful of tree, rock and prop variants) and vary them by turning, placing and the
  three scatter sizes; a hundred slightly different meshes cost far more than three good ones.
- Real scale in meters: a tree 4–12 m, a lamp post 3–4 m, a bench 1.5 m, a road lane 3.5 m. Lay out the ground first
  (a big plane or a gently shaped hill), then paths and big shapes, then props, then small scatter.
- Set things down with `mg.place` (onto the ground or another piece) and `mg.snap` — never float them at guessed
  heights. Instanced copies keep their turn when placed.
- Triangles count per copy, so a forest of 200 trees of 800 triangles is 160k: keep repeated pieces lean and let
  `scatter` counts drop on phones by themselves.
- Do not join instanced copies, and finish shaping and painting a piece before repeating it.
