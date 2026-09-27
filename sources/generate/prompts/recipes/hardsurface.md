---
title: Props, furniture and machines
keywords: crate, box, barrel, chest, chair, table, bench, lamp, sign, fence, gate, door, weapon, sword, gun, tool, machine, robot, vehicle, car, truck, cart, can, bottle, cup, pot, furniture, shelf, prop, ящик, коробка, бочка, сундук, стул, стол, скамейка, лампа, фонарь, знак, забор, ворота, дверь, оружие, меч, инструмент, машина, робот, тележка, банка, бутылка, чашка, горшок, мебель, полка
example: treasure_chest.py
---
- Block out with primitives, lathe (anything round: cans, bottles, lamp posts, wheels) and extrude (flat outlines:
  signs, blades, brackets). Bevel every visible edge a little (`bevel=` 0.5–2 % of the part) — nothing real is
  razor sharp.
- Build what the object IS: planks with gaps, bands and rivets on a barrel, a lid that is a separate part with a
  hinge and an `open` clip if it opens. Gate bolts, rivets and scratches with `mg.at_least(...)`.
- Wear on realistic models: dents with `sculpt("inflate", amount<0)` on subdivided parts, a snapped plank
  (`mg.cut` with a jagged extrude), rust painted near the bottom (`below=`), paint chipped at edges.
- Cables and hoses are `mg.curve`s that sag between points; rows of planks, rungs or bolts are one part plus
  `mg.modify(part, "array", count=…, offset=…)`; grilles and cages `mg.modify(box, "wireframe", thickness=…)`;
  straps `mg.modify(band, "shrinkwrap", target=…)`.
