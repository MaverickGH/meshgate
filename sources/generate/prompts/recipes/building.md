---
title: Buildings and architecture
keywords: modular kit, modular, house, building, tower, wall, castle, hut, shed, shop, church, windmill, bridge, ruin, roof, window, arch, column, gazebo, barn, cabin, дом, здание, башня, стена, замок, хижина, сарай, магазин, церковь, мельница, мост, крыша, окно, арка, колонна, амбар
example: windmill.py
---
- Start from the footprint and the floor heights; walls are cubes (closed, with thickness), windows and doors are
  `mg.cut` openings with a frame part and an inset glass or dark panel — not holes into a hollow inside.
- Roofs: extrude a gable outline along the depth, overhang the walls by 5–10 %; tiles or planks as a few long parts,
  not hundreds of small ones. Chimneys, beams and trim sell the scale.
- Repeat with loops (planks, bricks rows, fence pickets) but keep the triangle budget: detail on the silhouette.
- Walls, floors and roofs of any size: `mg.tile` materials ("bricks", "plaster", "planks", "shingles", "tiles")
  at their real scale (size = meters per repeat); frames, doors and trim stay palette colours. Neighbouring walls
  continue the pattern by themselves.
- Asked for a modular kit (wall pieces, doorways, floors for a level): one `mg.module` per piece on a shared grid
  (2 m, or 4 m for big buildings), each built from its corner at the origin with footprint = cells it covers; tile
  sizes that divide the grid, so patterns carry on across joints. Every module is exported on its own as well.
