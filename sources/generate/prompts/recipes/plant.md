---
title: Trees, plants and roots
keywords: tree, trunk, branch, bush, shrub, plant, flower, cactus, mushroom, root, vine, stump, log, grass, leaf, leaves, palm, pine, oak, dead tree, дерево, ствол, ветка, куст, растение, цветок, кактус, гриб, корень, пень, бревно, трава, лист, пальма, сосна, дуб
example: zombie_cats/realistic/dead_tree.py
---
- A trunk with branches is one `mg.skin`: points along the trunk, branch points joined to a trunk point with
  `edges=`; radii shrink toward the tips (trunk base ×1.5 for the root flare). Roots are short skin branches going
  down and out below z = 0.1.
- Gnarl it: `mg.twist` the trunk 0.3–0.8 rad, `mg.sculpt(..., "noise")` for bark (scale 10–25), a few `crease` lines
  along the trunk for bark furrows.
- Canopies are clusters of `mg.blob` balls (not one sphere) with `noise`; leaves on low tiers are the canopy blob,
  single leaves only at pc.
- Cacti and succulents: lathe or skin bodies, ribs by `crease` lines, spines as tiny cones gated with
  `mg.at_least("mobile-high")`. Never model the hidden inside of a pot: fill it with a soil disc.
