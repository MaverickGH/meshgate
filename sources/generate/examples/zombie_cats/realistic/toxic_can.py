"""zc_toxic_can — giant opened cat-food tin with purple label, cyan fish, glowing green toxic goo."""
import math


def build(mg):
    steel = mg.color("steel", (0.42, 0.44, 0.5), rough=0.4, metal=1.0, material="metal")
    steel_d = mg.color("steel_dark", (0.15, 0.15, 0.18), rough=0.5, metal=1.0, material="metal")
    purple = mg.color("paint_purple", (0.40, 0.14, 0.52), rough=0.55, metal=0.1, material="metal")
    cyan = mg.color("paint_cyan", (0.13, 0.62, 0.72), rough=0.5, metal=0.1, material="metal")
    goo = mg.color("goo_green", (0.48, 0.88, 0.18), rough=0.25, glow=1.8, material="plain")

    R = 0.30
    parts = []
    # can body (purple painted metal)
    parts.append(mg.part("cyl", purple, loc=(0, 0, 0.31), scale=(R * 2, R * 2, 0.60),
                         vertices=32, bevel=0.005))
    # bottom disc / floor of tin visible? solid body already. bare metal foot
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.02), scale=(R * 2 + 0.01, R * 2 + 0.01, 0.04),
                         vertices=32))

    # raised metal bands and rims (torus rings around the body)
    def ring(z, minor, col, maj=R + 0.005):
        parts.append(mg.part("torus", col, loc=(0, 0, z), major_radius=maj, minor_radius=minor))

    ring(0.605, 0.035, steel)              # thick top rim
    ring(0.60, 0.02, steel_d, maj=R - 0.02)
    ring(0.05, 0.03, steel)                # bottom rim
    ring(0.475, 0.022, steel)              # upper band
    ring(0.13, 0.022, steel)               # lower band
    if mg.at_least("mobile-mid"):
        ring(0.545, 0.015, steel)
        ring(0.075, 0.015, steel)

    # rivets on the bands
    if mg.at_least("mobile-high"):
        for i in range(12):
            ang = i / 12 * math.tau
            x, y = math.cos(ang) * (R + 0.01), math.sin(ang) * (R + 0.01)
            parts.append(mg.part("sphere", steel_d, loc=(x, y, 0.475),
                                 scale=(0.02, 0.02, 0.02), segments=8))

    # cyan fish emblem on the front of the label (front faces -Y)
    fish = [(-0.13, 0.0), (-0.05, 0.065), (0.05, 0.045), (0.12, 0.10),
            (0.055, 0.0), (0.12, -0.10), (0.05, -0.045), (-0.05, -0.065)]
    parts.append(mg.extrude(fish, 0.02, cyan, loc=(0, -0.285, 0.29), bevel=0.004))
    parts.append(mg.part("sphere", steel_d, loc=(-0.075, -0.30, 0.31),
                         scale=(0.02, 0.02, 0.02), segments=8))  # fish eye

    # glowing goo dome inside the tin
    parts.append(mg.part("sphere", goo, loc=(0, 0, 0.58), scale=(R - 0.03, R - 0.03, 0.14),
                         segments=32, ring_count=16))
    # bubbles resting on the goo surface
    for bx, by, br in [(-0.10, 0.05, 0.05), (0.08, -0.07, 0.045), (0.02, 0.10, 0.038),
                       (0.14, 0.04, 0.03), (-0.12, -0.06, 0.03)]:
        parts.append(mg.part("sphere", goo, loc=(bx, by, 0.63),
                             scale=(br * 2, br * 2, br * 2), segments=mg.seg(14)))

    # goo drips spilling over the rim and down the outside
    for x, zend in [(-0.12, 0.40), (0.04, 0.34), (0.16, 0.43), (-0.20, 0.47)]:
        pts = [(x, -0.18, 0.61), (x, -0.31, 0.575), (x, -0.315, zend)]
        parts.append(mg.tube(pts, 0, goo, radii=[0.035, 0.03, 0.018],
                             sides=mg.seg(8), smooth=True))
        parts.append(mg.part("sphere", goo, loc=(x, -0.315, zend),
                             scale=(0.045, 0.045, 0.05), segments=mg.seg(12)))

    # puddles of goo on the ground
    for px, py, rx, ry in [(0.0, -0.42, 0.17, 0.12), (-0.36, -0.28, 0.11, 0.09),
                           (0.37, -0.24, 0.12, 0.10), (0.22, 0.36, 0.09, 0.07)]:
        parts.append(mg.part("sphere", goo, loc=(px, py, 0.015),
                             scale=(rx * 2, ry * 2, 0.05), segments=mg.seg(18), ring_count=8))

    # rising bubbles, and the round lid floating above the rim, tilted — as in the concept
    for bx, by, bz, br in [(-0.03, -0.02, 0.76, 0.045), (0.05, 0.03, 0.88, 0.035), (-0.06, 0.02, 0.98, 0.03),
                           (0.03, -0.03, 1.06, 0.025)]:
        parts.append(mg.part("sphere", goo, loc=(bx, by, bz), scale=(br * 2,) * 3, segments=mg.seg(14)))
    a = 0.3
    Lx, Ly, Lz = 0.0, 0.0, 1.2
    nx, ny, nz = 0.0, -math.sin(a), math.cos(a)
    parts.append(mg.part("cyl", steel, loc=(Lx, Ly, Lz), scale=(0.56, 0.56, 0.03),
                         rot=(a, 0, 0), vertices=32, bevel=0.006))
    parts.append(mg.part("torus", steel, loc=(Lx, Ly, Lz), major_radius=0.27,
                         minor_radius=0.03, rot=(a, 0, 0)))
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("torus", steel, loc=(Lx, Ly, Lz), major_radius=0.19,
                             minor_radius=0.012, rot=(a, 0, 0)))
    parts.append(mg.part("cyl", steel, loc=(Lx + 0.025 * nx, Ly + 0.025 * ny, Lz + 0.025 * nz),
                         scale=(0.05, 0.05, 0.02), rot=(a, 0, 0), vertices=mg.seg(12)))

    mg.join("zc_toxic_can", parts)
