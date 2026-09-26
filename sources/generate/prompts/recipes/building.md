---
title: Buildings and architecture
keywords: house, building, tower, wall, castle, hut, shed, shop, church, windmill, bridge, ruin, roof, window, arch, column, gazebo, barn, cabin, дом, здание, башня, стена, замок, хижина, сарай, магазин, церковь, мельница, мост, крыша, окно, арка, колонна, амбар
example: windmill.py
---
- Start from the footprint and the floor heights; walls are cubes (closed, with thickness), windows and doors are
  `mg.cut` openings with a frame part and an inset glass or dark panel — not holes into a hollow inside.
- Roofs: extrude a gable outline along the depth, overhang the walls by 5–10 %; tiles or planks as a few long parts,
  not hundreds of small ones. Chimneys, beams and trim sell the scale.
- Repeat with loops (planks, bricks rows, fence pickets) but keep the triangle budget: detail on the silhouette.
