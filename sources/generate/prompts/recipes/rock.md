---
title: Rocks, ground and terrain pieces
keywords: rock, stone, boulder, cliff, pebble, ground, terrain, cave, crystal, ore, rubble, debris, tombstone, grave, statue, ruin, камень, скала, валун, галька, земля, пещера, кристалл, руда, обломки, надгробие, могила, статуя, руины
example: zombie_cats/realistic/tombstone_cat.py
---
- Rocks are a few overlapping `mg.blob` ellipsoids with low blend (0.5–0.7) for harder edges, then `noise` twice:
  a coarse pass (scale 4–8, amount 3–6 % of the size) and a fine one (scale 25–40).
- Carved stone (tombstones, statues, ruins): a bevelled cube or extrude as the block, `mg.cut` for engravings and
  paw prints (the cutter is a blob or extrude pushed a few centimetres in), `noise` for weathering, a `crease` crack.
- Paint moss on top (`facing=(0, 0, 1)`, rough 0.6) and grime near the ground (`below=`). Name stone colours
  "stone" / "rock" so the realistic finish draws cracks and moss.
- Pebbles and rubble around or on top: `mg.scatter` a small ico or blob with `facing=(0, 0, 1)`; for a lumpy
  surface `mg.modify(rock, "displace", strength=…, scale=…)`.
