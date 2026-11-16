#!/usr/bin/env python3
"""SKYWHALE v2 — "THE BREACH": a giant whale explodes upward out of a sea
of clouds over a tiny city at golden sunset, at the exact moment of the
breach. One huge, instantly readable subject, a steeper diagonal momentum
(tail bottom-left -> head top-right), a foam explosion where the body tears
out of the clouds, a big spray fan at the blowhole, sun rays converging on
the breach, and a tiny airplane crossing the top-right corner for scale.

Pure Python 3 stdlib only: a scanline vector rasterizer (spans, ellipse
spans, polygon fill) plus a zlib PNG encoder. No network, no external
assets, no randomness beyond a fixed seed -> byte-identical output on
every run. Writes one image to $MAKEFUN_OUTPUT_DIR/entry.png (or
/output/entry.png).
"""

import math
import os
import random
import struct
import zlib

W, H = 1024, 1024


# ---------------------------------------------------------------- palette
def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


SKY_STOPS = [
    (0, (24, 32, 96)),      # deep indigo, top
    (300, (122, 62, 140)),  # violet
    (560, (232, 93, 61)),   # burning orange
    (800, (255, 178, 90)),  # gold
    (1024, (255, 150, 80)), # warm horizon
]

SUN_GLOW = (255, 158, 87)
SUN_MID = (255, 196, 107)
SUN_CORE = (255, 233, 168)
RAY = (255, 183, 102)       # sun-ray wedges
CLOUD_BACK = (185, 168, 217)   # lavender shadow clouds
CLOUD_MID = (255, 217, 168)    # peach clouds
CLOUD_FRONT = (255, 246, 232)  # sunlit white clouds
FOAM = (255, 252, 246)         # breach foam / big spray
SPRAY = (235, 245, 252)
WHALE_TOP = (31, 58, 95)       # deep navy back
WHALE_BELLY = (232, 241, 247)  # pale belly
WHALE_DARK = (16, 32, 56)      # eye
RIM = (255, 196, 107)          # sunset rim light on the whale's top edge
CITY = (42, 27, 61)
WINDOW = (255, 209, 102)
BIRD = (43, 30, 66)
PLANE = (30, 24, 52)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rows = [bytearray(w * 3) for _ in range(h)]

    def span(self, y, x0, x1, color):
        """Fill [x0, x1) on row y with a solid RGB colour (clipped)."""
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w, int(x1))
        if x1 <= x0:
            return
        row = self.rows[y]
        r, g, b = color
        row[x0 * 3:x1 * 3] = bytes((r, g, b)) * (x1 - x0)

    def disc(self, cx, cy, r, color):
        """Filled circle via per-row spans."""
        r = int(r)
        cx, cy = int(cx), int(cy)
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.span(y, cx - dx, cx + dx + 1, color)

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            dy = (y - cy) / ry
            if abs(dy) >= 1:
                continue
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.span(y, cx - dx, cx + dx + 1, color)

    def line(self, x0, y0, x1, y1, color, width=3):
        """Thick line as a chain of small discs."""
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.2) + 1
        for i in range(n + 1):
            t = i / n
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                      width / 2.0, color)

    def polygon(self, points, color):
        """Even-odd scanline fill of a polygon [(x, y), ...]."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        y0, y1 = int(max(0, math.floor(min(ys)))), int(min(self.h - 1, math.ceil(max(ys))))
        edges = []
        n = len(points)
        for i in range(n):
            x0, yy0 = points[i]
            x1, yy1 = points[(i + 1) % n]
            if yy0 == yy1:
                continue
            edges.append((yy0, yy1, x0, x1))
        for y in range(y0, y1 + 1):
            xs = []
            for yy0, yy1, x0, x1 in edges:
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    t = (y - yy0) / (yy1 - yy0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.span(y, xs[i], xs[i + 1] + 1, color)

    def ring(self, cx, cy, rx, ry, color, width=10):
        """Ellipse outline: discs along the ellipse perimeter."""
        steps = int(2 * math.pi * max(rx, ry) / 9) + 24
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            self.disc(cx + math.cos(a) * rx, cy + math.sin(a) * ry,
                      width / 2.0, color)


# ---------------------------------------------------------------- scene
def sky(canvas):
    for y in range(H):
        for i in range(len(SKY_STOPS) - 1):
            y0, c0 = SKY_STOPS[i]
            y1, c1 = SKY_STOPS[i + 1]
            if y0 <= y <= y1:
                canvas.span(y, 0, W, lerp(c0, c1, (y - y0) / max(1, y1 - y0)))
                break


def bezier(p0, p1, p2, t):
    u = 1.0 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def bezier_deriv(p0, p1, p2, t):
    return (2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]),
            2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1]))


# Whale spine: tail low-left, head high-right, steeper and fatter than v1.
# The tail sits HIGH above the cloud sea (y ~770 vs clouds ~850) so the
# flukes stay in open sky instead of drowning in the clouds.
P0, P1, P2 = (300.0, 772.0), (450.0, 610.0), (795.0, 235.0)


def whale_width(t):
    # narrow tail stalk -> fat mid-body -> big rounded head
    keys = [(0.0, 20), (0.15, 78), (0.45, 168), (0.70, 160),
            (0.90, 126), (1.0, 86)]
    for i in range(len(keys) - 1):
        t0, w0 = keys[i]
        t1, w1 = keys[i + 1]
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            s = u * u * (3 - 2 * u)  # smoothstep: no kinks in the outline
            return w0 + (w1 - w0) * s
    return keys[-1][1]


def whale_outline():
    """Body outline as a polygon: a fat arc, tail bottom-left, head top-right."""
    left, right, centers, normals = [], [], [], []
    steps = 48
    for i in range(steps + 1):
        t = i / steps
        cx, cy = bezier(P0, P1, P2, t)
        dx, dy = bezier_deriv(P0, P1, P2, t)
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln  # normal; +n points up-left (sky side)
        w = whale_width(t)
        centers.append((cx, cy))
        normals.append((nx, ny))
        left.append((cx + nx * w, cy + ny * w))
        right.append((cx - nx * w, cy - ny * w))
    # rounded nose: semicircle around the head tip
    cx, cy = centers[-1]
    nx, ny = normals[-1]
    w = whale_width(1.0)
    nose = []
    for k in range(1, 9):
        a = math.pi * k / 9.0
        ang = math.atan2(ny, nx) - a  # from +n toward head direction
        nose.append((cx + math.cos(ang) * w, cy + math.sin(ang) * w))
    outline = left + nose + list(reversed(right))
    return outline, centers, normals


def draw(canvas):
    rng = random.Random(20261116)
    sky(canvas)

    # stars in the deep top sky
    for _ in range(46):
        x = rng.uniform(0, W)
        y = rng.uniform(0, 240)
        r = rng.choice((1, 1, 2))
        canvas.disc(x, y, r, (255, 244, 214))

    # sun, upper left, with a warm glow
    canvas.disc(238, 198, 132, SUN_GLOW)
    canvas.disc(238, 198, 104, SUN_MID)
    canvas.disc(238, 198, 76, SUN_CORE)

    # sun rays: SHORT thin wedges fanning down-right toward the breach,
    # kept in the upper-left sky so they read as light, not sticks
    sx, sy = 238, 198
    for ang_deg, length, half_w in [
        (14, 300, 6), (34, 340, 7), (54, 290, 6), (-12, 230, 5),
    ]:
        a = math.radians(ang_deg)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        tip = (sx + dx * length, sy + dy * length)
        base1 = (sx + px * half_w + dx * 95, sy + py * half_w + dy * 95)
        base2 = (sx - px * half_w + dx * 95, sy - py * half_w + dy * 95)
        canvas.polygon([base1, tip, base2], RAY)

    # (no distant whale: every version read as a dark hill, not a whale,
    # and the airplane + birds + city already carry the scale story)

    # a few high drifting clouds (puffy, not flat discs)
    for (cx, cy, rx, ry, col) in [
        (640, 150, 95, 34, CLOUD_FRONT), (700, 172, 70, 26, CLOUD_MID),
        (120, 420, 85, 30, CLOUD_MID), (180, 440, 62, 22, CLOUD_FRONT),
        (900, 560, 100, 34, CLOUD_MID), (950, 582, 70, 24, CLOUD_FRONT),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # sea of clouds the whale bursts out of (back layers first)
    for (cx, cy, rx, ry, col) in [
        (80, 860, 260, 70, CLOUD_BACK), (420, 880, 300, 80, CLOUD_BACK),
        (780, 870, 280, 75, CLOUD_BACK), (1010, 890, 220, 70, CLOUD_BACK),
        (200, 920, 280, 75, CLOUD_MID), (560, 940, 320, 85, CLOUD_MID),
        (900, 930, 300, 80, CLOUD_MID),
        (60, 985, 300, 80, CLOUD_FRONT), (400, 995, 340, 85, CLOUD_FRONT),
        (760, 990, 330, 85, CLOUD_FRONT), (1020, 995, 260, 80, CLOUD_FRONT),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # lumpy puffs on top of the sea so its horizon is bumpy, not a flat band
    for (cx, cy, rx, ry, col) in [
        (40, 862, 130, 48, CLOUD_MID), (210, 848, 150, 54, CLOUD_FRONT),
        (380, 866, 140, 46, CLOUD_MID), (540, 846, 160, 56, CLOUD_FRONT),
        (720, 868, 145, 48, CLOUD_MID), (880, 850, 150, 52, CLOUD_FRONT),
        (1010, 868, 120, 46, CLOUD_MID),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # ---- THE BREACH: foam explosion where the body tears out of the
    # cloud sea. Drawn BEFORE the whale, so the tail and flukes sit
    # visibly ON TOP of the foam instead of drowning in it. ----
    bx, by = 318, 878
    canvas.ring(bx, by, 135, 38, FOAM, 15)
    canvas.ring(bx, by, 92, 25, CLOUD_FRONT, 11)
    # a rising column of foam hugging the tail
    for (dx, dy, r) in [(0, -16, 24), (-26, -4, 18), (28, -2, 20),
                        (-48, 10, 14), (52, 12, 13), (-10, -34, 16),
                        (16, -28, 12)]:
        canvas.disc(bx + dx, by + dy, r, FOAM)
    # big flying droplets, clearly shaped (not speckle): chunky ellipses
    for (dx, dy, rx, ry) in [
        (-175, -48, 17, 11), (-138, -72, 13, 9), (-100, -88, 11, 8),
        (155, -52, 16, 11), (190, -26, 12, 8), (118, -80, 11, 8),
        (-198, -6, 10, 7), (210, 8, 9, 7), (82, -98, 9, 7),
        (-55, -94, 8, 6), (55, -86, 8, 6),
    ]:
        canvas.ellipse(bx + dx, by + dy, rx, ry, FOAM)

    # ---- the whale ----
    outline, centers, normals = whale_outline()

    # tail flukes: TWO SEPARATE BROAD triangles fanning out from the tail
    # end — wide lobes with a gap between them, so they read as flukes
    # instead of one thin blade. Drawn on top of the foam.
    tx, ty = centers[0]
    canvas.polygon([(tx, ty), (148, 728), (218, 826)], WHALE_TOP)
    canvas.polygon([(tx, ty), (356, 916), (252, 862)], WHALE_TOP)

    # pectoral fin: a broad triangle rooted along the belly edge, sweeping
    # down-right so it reads as clearly attached
    def belly_point(t, frac):
        cx, cy = bezier(P0, P1, P2, t)
        dx, dy = bezier_deriv(P0, P1, P2, t)
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        return (cx + nx * whale_width(t) * frac, cy + ny * whale_width(t) * frac)

    b1 = belly_point(0.46, 0.85)
    b2 = belly_point(0.60, 0.85)
    tip = ((b1[0] + b2[0]) / 2 + 44, (b1[1] + b2[1]) / 2 + 78)
    canvas.polygon([b1, tip, b2], WHALE_TOP)

    # body
    canvas.polygon(outline, WHALE_TOP)

    # pale belly band along the lower (belly) side
    belly = []
    for k in range(6, 47):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        belly.append((cx + nx * whale_width(t) * 0.28,
                      cy + ny * whale_width(t) * 0.28))
    for k in range(46, 5, -1):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        belly.append((cx + nx * whale_width(t) * 0.88,
                      cy + ny * whale_width(t) * 0.88))
    canvas.polygon(belly, WHALE_BELLY)

    # sunset rim light along the top (back) edge: a continuous gold line
    rim_pts = []
    for k in range(2, 49):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        rim_pts.append((cx - nx * (whale_width(t) - 3),
                        cy - ny * (whale_width(t) - 3)))
    for j in range(len(rim_pts) - 1):
        canvas.line(rim_pts[j][0], rim_pts[j][1], rim_pts[j + 1][0],
                    rim_pts[j + 1][1], RIM, 6)

    # no mouth line: every mouth curve tried read as a crack on the face,
    # so the whale stays clean with just the big eye (flat-style craft
    # beats a misleading feature)

    # eye: BIGGER, with a glint (on the back side of the head)
    ex, ey = centers[44]
    nx, ny = normals[44]
    ex -= nx * whale_width(44 / 48) * 0.38
    ey -= ny * whale_width(44 / 48) * 0.38
    canvas.disc(ex, ey, 15, WHALE_DARK)
    canvas.disc(ex + 5, ey - 5, 4, (255, 255, 255))

    # ---- spray bursting from the blowhole: a BIG fan of large droplets
    # plus three sweeping arcs, so it reads as an explosion, not noise ----
    hx, hy = centers[-1]
    for a in (-2.5, -2.0, -1.5, -1.0, -0.5):
        # arc streaks fanning out from the blowhole
        canvas.line(hx + math.cos(a) * 30, hy + math.sin(a) * 22,
                    hx + math.cos(a) * 105, hy + math.sin(a) * 78,
                    SPRAY, 7)
    for _ in range(34):
        a = rng.uniform(-2.8, -0.3)
        d = rng.uniform(24, 130)
        r = rng.uniform(5, 13)  # large, clearly shaped droplets
        canvas.disc(hx + math.cos(a) * d + rng.uniform(-8, 8),
                    hy + math.sin(a) * d * 0.75 + rng.uniform(-6, 6),
                    r, SPRAY)
    # a few hero droplets: big teardrops above the head
    for (dx, dy, rx, ry) in [(-30, -120, 16, 11), (25, -135, 14, 10),
                             (75, -105, 12, 9), (-75, -95, 11, 8)]:
        canvas.ellipse(hx + dx, hy + dy, rx, ry, FOAM)

    # foreground cloud puffs where the tail dives back into the sea
    # (kept low and to the sides so the flukes stay visible)
    for (cx, cy, rx, ry) in [(120, 950, 120, 36), (260, 975, 110, 32),
                             (60, 990, 100, 32)]:
        canvas.ellipse(cx, cy, rx, ry, CLOUD_FRONT)

    # ---- tiny city at the very bottom, dwarfed by the whale ----
    # taller towers now, so the scale twist reads at a glance
    x = -10
    while x < W + 10:
        bw = rng.randint(38, 86)
        bh = rng.randint(48, 118)
        if rng.random() < 0.12:
            bh = rng.randint(120, 150)  # landmark tower
        canvas.polygon([(x, H), (x, H - bh), (x + bw, H - bh), (x + bw, H)],
                       CITY)
        if bh > 118:  # antenna on the landmark towers
            canvas.line(x + bw / 2, H - bh, x + bw / 2, H - bh - 22,
                        CITY, 4)
            canvas.disc(x + bw / 2, H - bh - 24, 3, WINDOW)
        # lit windows
        for wy in range(H - bh + 8, H - 8, 13):
            for wx in range(x + 7, x + bw - 6, 12):
                if rng.random() < 0.45:
                    canvas.span(wy, wx, wx + 4, WINDOW)
                    canvas.span(wy + 1, wx, wx + 4, WINDOW)
        x += bw + rng.randint(4, 18)

    # ---- tiny airplane crossing the top-right corner, dwarfed by the
    # whale's nose: a small clean silhouette, well clear of the whale ----
    ax, ay = 930, 105
    # fuselage (tilted), one swept main wing below, small tail fin
    canvas.line(ax - 30, ay + 9, ax + 30, ay - 9, PLANE, 8)
    canvas.line(ax - 2, ay + 1, ax + 6, ay + 24, PLANE, 6)
    canvas.line(ax + 24, ay - 7, ax + 34, ay - 20, PLANE, 5)
    for k in range(3):
        canvas.disc(ax - 12 + k * 11, ay + 1 - k * 3, 2, WINDOW)
    canvas.line(ax - 33, ay + 10, ax - 88, ay + 26, SPRAY, 3)

    # birds, tiny chevrons fleeing the whale's path
    for (bx, by, s) in [(560, 210, 16), (610, 175, 12), (505, 150, 11),
                        (700, 120, 10), (640, 320, 13), (480, 260, 10)]:
        canvas.line(bx - s, by, bx, by - s * 0.55, BIRD, 4)
        canvas.line(bx, by - s * 0.55, bx + s, by, BIRD, 4)


# ---------------------------------------------------------------- PNG out
def write_png(canvas, path):
    raw = b"".join(b"\x00" + bytes(row) for row in canvas.rows)
    comp = zlib.compress(raw, 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    canvas = Canvas(W, H)
    draw(canvas)
    size = write_png(canvas, os.path.join(out_dir, "entry.png"))
    print(f"wrote {os.path.join(out_dir, 'entry.png')} ({size} bytes)")


if __name__ == "__main__":
    main()
