"""zc_fence_broken: broken wooden garden fence, cat-ear pickets, some snapped, one hanging crooked."""
import math


def build(mg):
    wood_l = mg.color("wood_light", "#d8a45f", rough=0.7, material="wood")
    wood_d = mg.color("wood_dark", "#7a4a28", rough=0.78, material="wood")
    rust = mg.color("rust_nail", "#3f2c1c", rough=0.8, metal=0.2, material="rust")

    w, th, yf = 0.16, 0.03, -0.05          # picket width, thickness, front plane
    sh, notch, peak, h = 0.82, 0.88, 1.02, 1.02

    def ears(width, shoulder, valley, tip):
        return [(-width / 2, 0), (width / 2, 0), (width / 2, shoulder),
                (width * 0.25, tip), (0, valley), (-width * 0.25, tip), (-width / 2, shoulder)]

    parts = []

    # --- intact cat-ear pickets ---
    tall_x = [-0.80, -0.55, -0.30, 0.60]
    base = mg.extrude(ears(w, sh, notch, peak), th, wood_l, loc=(tall_x[0], yf, 0), bevel=0.006)
    parts.append(base)
    for x in tall_x[1:]:
        parts.append(mg.copy(base, loc=(x, yf, 0)))

    # one hanging crooked from a single nail (tilted picket)
    crooked = mg.copy(base, loc=(-0.04, yf - 0.03, 0.04), rot=(0.05, 0.0, 0.42))
    parts.append(crooked)

    # --- two pickets snapped short with jagged broken tops ---
    jag = [(-w / 2, 0), (w / 2, 0), (w / 2, 0.40), (w * 0.15, 0.55),
           (-0.02, 0.36), (-w * 0.30, 0.50), (-w / 2, 0.42)]
    short = mg.extrude(jag, th, wood_l, loc=(0.18, yf, 0), bevel=0.005)
    parts.append(short)
    parts.append(mg.copy(short, loc=(0.42, yf, 0), rot=(0, 0, -0.06)))

    # a fallen broken shard leaning at the base
    shard = [(-w / 2, 0), (w / 2, 0), (w / 2, 0.26), (0.0, 0.34), (-w / 2, 0.24)]
    parts.append(mg.extrude(shard, th, wood_l, loc=(0.30, yf - 0.02, 0.0), rot=(0, 0, 1.3)))

    # --- horizontal rails ---
    rail_len = 1.86
    for rz in (0.28, 0.74):
        parts.append(mg.part("cube", wood_d, loc=(0, 0.01, rz),
                             scale=(rail_len, 0.06, 0.12), bevel=0.01))

    # --- end posts ---
    for px in (-0.92, 0.92):
        parts.append(mg.part("cube", wood_d, loc=(px, 0.01, 0.55),
                             scale=(0.11, 0.11, 1.1), bevel=0.012, taper=0.9))

    # --- rusty nails on pickets and posts ---
    def nail(x, y, z):
        parts.append(mg.part("cyl", rust, loc=(x, y, z), scale=(0.036, 0.036, 0.02),
                             rot=(math.pi / 2, 0, 0), vertices=8, bevel=0.004))

    for x in tall_x:
        nail(x, yf - 0.03, 0.51)
    nail(-0.02, yf - 0.06, 0.55)      # the single nail the crooked picket hangs on
    nail(0.18, yf - 0.03, 0.30)
    nail(0.42, yf - 0.03, 0.30)
    for px in (-0.92, 0.92):
        nail(px, -0.06, 0.30)
        nail(px, -0.06, 0.74)

    mg.join("zc_fence_broken", parts)
