#!/usr/bin/env python3
"""SKYWHALE — a giant whale breaches upward through a sea of clouds over a
tiny city at golden sunset. One huge, instantly readable subject, a strong
diagonal momentum (tail bottom-left -> head top-right), bold flat colours.

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
CLOUD_BACK = (185, 168, 217)   # lavender shadow clouds
CLOUD_MID = (255, 217, 168)    # peach clouds
CLOUD_FRONT = (255, 246, 232)  # sunlit white clouds
WHALE_TOP = (31, 58, 95)       # deep navy back
WHALE_BELLY = (232, 241, 247)  # pale belly
WHALE_DARK = (16, 32, 56)      # mouth / eye
RIM = (255, 196, 107)          # sunset rim light on the whale's top edge
SPRAY = (235, 245, 252)
CITY = (42, 27, 61)
WINDOW = (255, 209, 102)
BIRD = (43, 30, 66)


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


def whale_outline():
    """Body outline as a polygon: a fat arc, tail bottom-left, head top-right."""
    p0, p1, p2 = (170.0, 860.0), (360.0, 800.0), (800.0, 300.0)

    def width(t):
        # narrow tail stalk -> fat mid-body -> big rounded head
        keys = [(0.0, 16), (0.15, 62), (0.45, 148), (0.70, 142),
                (0.90, 112), (1.0, 78)]
        for i in range(len(keys) - 1):
            t0, w0 = keys[i]
            t1, w1 = keys[i + 1]
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                s = u * u * (3 - 2 * u)  # smoothstep: no kinks in the outline
                return w0 + (w1 - w0) * s
        return keys[-1][1]

    left, right, centers, normals = [], [], [], []
    steps = 48
    for i in range(steps + 1):
        t = i / steps
        cx, cy = bezier(p0, p1, p2, t)
        dx, dy = bezier_deriv(p0, p1, p2, t)
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln  # normal; +n points up-left (sky side)
        w = width(t)
        centers.append((cx, cy))
        normals.append((nx, ny))
        left.append((cx + nx * w, cy + ny * w))
        right.append((cx - nx * w, cy - ny * w))
    # rounded nose: semicircle around the head tip
    cx, cy = centers[-1]
    nx, ny = normals[-1]
    w = width(1.0)
    nose = []
    for k in range(1, 9):
        a = math.pi * k / 9.0  # sweep from +n side to -n side over the tip
        px = cx + math.cos(a) * nx * w - math.sin(a) * (-ny) * w * 0.0
        # point on the cap circle, rotated from +n toward the head direction
        hx, hy = bezier_deriv(p0, p1, p2, 1.0)
        hl = math.hypot(hx, hy)
        hx, hy = hx / hl, hy / hl
        ang = math.atan2(ny, nx) - a  # from +n toward head direction
        nose.append((cx + math.cos(ang) * w, cy + math.sin(ang) * w))
    outline = left + nose + list(reversed(right))
    return outline, centers, normals, width


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

    # a few high drifting clouds (puffy, not flat discs)
    for (cx, cy, rx, ry, col) in [
        (640, 150, 95, 34, CLOUD_FRONT), (700, 172, 70, 26, CLOUD_MID),
        (120, 420, 85, 30, CLOUD_MID), (180, 440, 62, 22, CLOUD_FRONT),
        (900, 560, 100, 34, CLOUD_MID), (950, 582, 70, 24, CLOUD_FRONT),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # sea of clouds the whale bursts out of (back layers first)
    for (cx, cy, rx, ry, col) in [
        (80, 830, 260, 70, CLOUD_BACK), (420, 860, 300, 80, CLOUD_BACK),
        (780, 840, 280, 75, CLOUD_BACK), (1010, 870, 220, 70, CLOUD_BACK),
        (200, 900, 280, 75, CLOUD_MID), (560, 920, 320, 85, CLOUD_MID),
        (900, 910, 300, 80, CLOUD_MID),
        (60, 970, 300, 80, CLOUD_FRONT), (400, 985, 340, 85, CLOUD_FRONT),
        (760, 975, 330, 85, CLOUD_FRONT), (1020, 980, 260, 80, CLOUD_FRONT),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # lumpy puffs on top of the sea so its horizon is bumpy, not a flat band
    for (cx, cy, rx, ry, col) in [
        (40, 838, 130, 48, CLOUD_MID), (210, 822, 150, 54, CLOUD_FRONT),
        (380, 842, 140, 46, CLOUD_MID), (540, 820, 160, 56, CLOUD_FRONT),
        (720, 844, 145, 48, CLOUD_MID), (880, 824, 150, 52, CLOUD_FRONT),
        (1010, 846, 120, 46, CLOUD_MID),
    ]:
        canvas.ellipse(cx, cy, rx, ry, col)

    # ---- the whale ----
    # +n points down-right (belly side); -n points up-left (back / sky side)
    outline, centers, normals, width = whale_outline()
    p0, p1, p2 = (170.0, 860.0), (360.0, 800.0), (800.0, 300.0)

    # tail flukes (behind the body)
    tx, ty = centers[0]
    dx, dy = bezier_deriv(p0, p1, p2, 0.0)
    ln = math.hypot(dx, dy)
    dx, dy = dx / ln, dy / ln
    px, py = -dy, dx  # perpendicular
    flukes = [
        (tx - dx * 78 + px * 62, ty - dy * 78 + py * 62),
        (tx - dx * 34, ty - dy * 34),
        (tx - dx * 82 - px * 58, ty - dy * 82 - py * 58),
        (tx - dx * 18 - px * 26, ty - dy * 18 - py * 26),
        (tx - dx * 14 + px * 22, ty - dy * 14 + py * 22),
    ]
    canvas.polygon(flukes, WHALE_TOP)

    # pectoral fin: a broad triangle rooted along the belly edge, sweeping
    # down-right so it reads as clearly attached
    def belly_point(t, frac):
        cx, cy = bezier(p0, p1, p2, t)
        dx, dy = bezier_deriv(p0, p1, p2, t)
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        return (cx + nx * width(t) * frac, cy + ny * width(t) * frac)

    b1 = belly_point(0.46, 0.85)
    b2 = belly_point(0.60, 0.85)
    tip = ((b1[0] + b2[0]) / 2 + 36, (b1[1] + b2[1]) / 2 + 66)
    canvas.polygon([b1, tip, b2], WHALE_TOP)

    # body
    canvas.polygon(outline, WHALE_TOP)

    # pale belly band along the lower (belly) side
    belly = []
    for k in range(6, 47):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        belly.append((cx + nx * width(t) * 0.28, cy + ny * width(t) * 0.28))
    for k in range(46, 5, -1):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        belly.append((cx + nx * width(t) * 0.88, cy + ny * width(t) * 0.88))
    canvas.polygon(belly, WHALE_BELLY)

    # sunset rim light along the top (back) edge: a continuous gold line
    rim_pts = []
    for k in range(2, 49):
        t = k / 48
        cx, cy = centers[k]
        nx, ny = normals[k]
        rim_pts.append((cx - nx * (width(t) - 3), cy - ny * (width(t) - 3)))
    for j in range(len(rim_pts) - 1):
        canvas.line(rim_pts[j][0], rim_pts[j][1], rim_pts[j + 1][0],
                    rim_pts[j + 1][1], RIM, 6)

    # mouth: a dark curve sweeping back from the nose along the belly side
    mouth = []
    for k in range(0, 13):
        s = k / 12.0
        tt = 0.995 - 0.075 * s
        cx, cy = bezier(p0, p1, p2, tt)
        dx, dy = bezier_deriv(p0, p1, p2, tt)
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        mouth.append((cx + nx * width(tt) * (0.30 + 0.22 * s),
                      cy + ny * width(tt) * (0.30 + 0.22 * s)))
    for j in range(len(mouth) - 1):
        canvas.line(mouth[j][0], mouth[j][1], mouth[j + 1][0],
                    mouth[j + 1][1], WHALE_DARK, 6)

    # eye, with a glint (on the back side of the head)
    ex, ey = centers[44]
    nx, ny = normals[44]
    ex -= nx * width(44 / 48) * 0.38
    ey -= ny * width(44 / 48) * 0.38
    canvas.disc(ex, ey, 11, WHALE_DARK)
    canvas.disc(ex + 3, ey - 3, 3, (255, 255, 255))

    # spray bursting from the blowhole / around the nose: a tight fan of
    # droplets, no long straight streaks
    hx, hy = centers[-1]
    for _ in range(56):
        a = rng.uniform(-2.7, -0.4)
        d = rng.uniform(14, 95)
        r = rng.uniform(2, 6)
        canvas.disc(hx + math.cos(a) * d + rng.uniform(-6, 6),
                    hy + math.sin(a) * d * 0.75 + rng.uniform(-5, 5),
                    r, SPRAY)
    for a in (-2.2, -1.7, -1.2):
        canvas.line(hx + math.cos(a) * 26, hy + math.sin(a) * 20,
                    hx + math.cos(a) * 62, hy + math.sin(a) * 48,
                    SPRAY, 4)

    # foreground cloud puffs where the tail dives back into the sea
    for (cx, cy, rx, ry) in [(170, 905, 120, 36), (280, 945, 110, 32),
                             (70, 950, 100, 32)]:
        canvas.ellipse(cx, cy, rx, ry, CLOUD_FRONT)

    # ---- tiny city at the very bottom, dwarfed by the whale ----
    x = -10
    while x < W + 10:
        bw = rng.randint(38, 86)
        bh = rng.randint(36, 88)
        canvas.polygon([(x, H), (x, H - bh), (x + bw, H - bh), (x + bw, H)],
                       CITY)
        # lit windows
        for wy in range(H - bh + 8, H - 8, 13):
            for wx in range(x + 7, x + bw - 6, 12):
                if rng.random() < 0.45:
                    canvas.span(wy, wx, wx + 4, WINDOW)
                    canvas.span(wy + 1, wx, wx + 4, WINDOW)
        x += bw + rng.randint(4, 18)

    # birds, tiny chevrons fleeing the whale's path
    for (bx, by, s) in [(560, 210, 16), (610, 175, 12), (505, 150, 11),
                        (880, 180, 14), (700, 120, 10)]:
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
