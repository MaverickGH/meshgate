---
title: Reworking a ready-made model
keywords: library, sketchfab, objaverse, rework, remake, based on, from model, uid, библиотека, готовая модель, переделать, на основе
example: sculpted_cat.py
---
- `mg.model(uid, colour, size=…, turn=…)` brings a free library model in as one piece (rest pose, meters, standing
  on the ground). Its textures are dropped: repaint it with `mg.paint` regions (a pale belly, dark back, wounds).
- Take only the part you need with `keep=((x1, y1, z1), (x2, y2, z2))` (a head, a paw) and sink the open edge into
  your own blob or part; drop the rest with `drop=`.
- Make it yours: sculpt (`noise`, `crease`, `inflate`), cut (a torn ear), add hard parts (stitches, collar, glowing
  eyes). The author and licence are credited automatically — never use a model the user did not choose.
