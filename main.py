#!/usr/bin/env python3
"""SKYWHALE v3 -- "THE BREACH", full rewrite for ai-excited-01 round 3.

A giant whale tears out of a sunset sea at the steepest moment of the
breach: tail still buried in a foam explosion, flukes fanned wide, body
arcing up toward the sun, spray bursting from the blowhole. A tiny
airplane crosses the top-right corner and a dwarfed city glitters far
below, so the scale of the animal hits at a glance.

Pure Python 3 standard library. A small scanline rasterizer paints the
scene into a byte buffer -- sky gradient, sun and rays, cloud sea, lit
city, the whale as a tapered tube along a Bezier spine, foam, spray,
airplane, birds -- and a zlib PNG encoder with per-row filter choice
writes exactly one deterministic 1024x1024 image.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
SEED = 20261117


# ---------------------------------------------------------------- colors

def mix(a, b, t):
    """Linear blend of two RGB triples, t in [0, 1]."""
    return (round(a[0] + (b[0] - a[0]) * t),
            round(a[1] + (b[1] - a[1]) * t),
            round(a[2] + (b[2] - a[2]) * t))


def shade(rgb, f):
    """Scale a color toward black (f < 1) or white (f > 1)."""
    if f <= 1.0:
        return (round(rgb[0] * f), round(rgb[1] * f), round(rgb[2] * f))
    return (round(rgb[0] + (255 - rgb[0]) * (f - 1.0)),
            round(rgb[1] + (255 - rgb[1]) * (f - 1.0)),
            round(rgb[2] + (255 - rgb[2]) * (f - 1.0)))


def ramp(stops, t):
    """Multi-stop vertical gradient. stops: [(pos, rgb), ...] sorted."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


# ---------------------------------------------------------------- canvas

class Canvas:
    """Row-major RGB buffer with fast opaque spans and alpha blends."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.rows = [bytearray(w * 3) for _ in range(h)]

    def span(self, x0, x1, y, rgb):
        """Opaque horizontal run, clipped. x0/x1 inclusive."""
        y = int(y)
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        row = self.rows[y]
        row[x0 * 3:(x1 + 1) * 3] = bytes(rgb) * (x1 - x0 + 1)

    def blend_span(self, x0, x1, y, rgb, alpha):
        """Alpha-blended horizontal run, alpha in [0, 1]."""
        y = int(y)
        if y < 0 or y >= self.h or alpha <= 0.0:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        if alpha >= 1.0:
            self.span(x0, x1, y, rgb)
            return
        row = self.rows[y]
        ia = 1.0 - alpha
        for x in range(x0, x1 + 1):
            i = x * 3
            row[i] = round(row[i] * ia + rgb[0] * alpha)
            row[i + 1] = round(row[i + 1] * ia + rgb[1] * alpha)
            row[i + 2] = round(row[i + 2] * ia + rgb[2] * alpha)

    def px(self, x, y, rgb, alpha=1.0):
        if 0 <= x < self.w and 0 <= y < self.h:
            if alpha >= 1.0:
                i = x * 3
                self.rows[y][i:i + 3] = bytes(rgb)
            else:
                self.blend_span(x, x, y, rgb, alpha)

    def disc(self, cx, cy, r, rgb, alpha=1.0):
        """Filled circle by scanline spans."""
        r = int(r)
        if r <= 0:
            return
        for dy in range(-r, r + 1):
            half = int((r * r - dy * dy) ** 0.5)
            if alpha >= 1.0:
                self.span(cx - half, cx + half, cy + dy, rgb)
            else:
                self.blend_span(cx - half, cx + half, cy + dy, rgb, alpha)

    def ellipse(self, cx, cy, rx, ry, rgb, alpha=1.0):
        rx = int(rx)
        ry = int(ry)
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / (ry * ry)
            half = int(rx * (t ** 0.5)) if t > 0 else 0
            if alpha >= 1.0:
                self.span(cx - half, cx + half, cy + dy, rgb)
            else:
                self.blend_span(cx - half, cx + half, cy + dy, rgb, alpha)

    def poly(self, pts, rgb, alpha=1.0):
        """Filled polygon, scanline edge intersections."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = int(min(ys)), int(max(ys))
        n = len(pts)
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            xs = []
            for i in range(n):
                x0, ya = pts[i]
                x1, yb = pts[(i + 1) % n]
                if ya == yb:
                    continue
                if (ya <= y < yb) or (yb <= y < ya):
                    xs.append(x0 + (y - ya) * (x1 - x0) / (yb - ya))
            if len(xs) >= 2:
                xs.sort()
                for k in range(0, len(xs) - 1, 2):
                    if alpha >= 1.0:
                        self.span(xs[k], xs[k + 1], y, rgb)
                    else:
                        self.blend_span(xs[k], xs[k + 1], y, rgb, alpha)

    def thick_line(self, x0, y0, x1, y1, width, rgb, alpha=1.0):
        """Thick segment drawn as a chain of discs."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(2, int(dist / max(1.0, width * 0.4)))
        for i in range(steps + 1):
            t = i / steps
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                      width / 2.0, rgb, alpha)

    def vgrad(self, y0, y1, stops):
        """Fill rows y0..y1 with a vertical gradient."""
        span = max(1, y1 - y0)
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.span(0, self.w - 1, y, ramp(stops, (y - y0) / span))


# ---------------------------------------------------------------- palette

SKY = [(0.00, (26, 10, 64)),
       (0.30, (94, 26, 108)),
       (0.55, (196, 62, 96)),
       (0.78, (250, 128, 58)),
       (1.00, (255, 196, 96))]
SEA = [(0.00, (16, 74, 104)),
       (0.45, (10, 48, 76)),
       (1.00, (4, 20, 44))]
CLOUD = (255, 214, 168)
CLOUD_SHADE = (214, 128, 118)
CLOUD_DEEP = (146, 74, 108)
SUN_CORE = (255, 238, 178)
SUN_HALO = (255, 190, 92)
RAY = (255, 214, 130)
SEA_FOAM = (244, 250, 252)
FOAM_SHADE = (178, 202, 224)
CITY = (22, 12, 44)
WINDOW = (255, 202, 110)
GLITTER = (255, 196, 96)

HORIZON = 700          # y of the sea line
SUN = (772, 556)       # sun centre
BREACH = (408, 706)    # where the body tears out of the water


def paint_sky(cv):
    cv.vgrad(0, HORIZON, SKY)
    # faint horizontal warmth bands low in the sky
    for y in range(560, HORIZON, 3):
        t = (y - 560) / (HORIZON - 560)
        cv.blend_span(0, W - 1, y, (255, 170, 80), 0.05 + 0.10 * t)


def paint_sun(cv):
    sx, sy = SUN
    # halo: concentric translucent discs, biggest first
    for r, a in ((150, 0.10), (120, 0.14), (92, 0.20), (70, 0.30)):
        cv.disc(sx, sy, r, SUN_HALO, a)
    cv.disc(sx, sy, 52, SUN_CORE)
    cv.disc(sx, sy, 44, (255, 244, 200))
    # sun sits half behind a thin cloud wisp
    cv.ellipse(sx - 30, sy + 34, 120, 10, CLOUD_SHADE, 0.55)
    cv.ellipse(sx + 40, sy + 46, 90, 8, CLOUD_SHADE, 0.45)


def paint_rays(cv):
    """Sun rays as long translucent wedges fanning toward the breach."""
    sx, sy = SUN
    bx, by = BREACH
    for k in range(-4, 5):
        # each ray is a narrow triangle from near the sun to past the breach
        spread = k * 46
        tx, ty = bx + spread, by + 26
        # widen the wedge with a second point so it reads as a beam
        px, py = bx + spread * 1.9, by + 150
        alpha = 0.16 if k % 2 == 0 else 0.10
        cv.poly([(sx, sy), (tx, ty), (px, py)], RAY, alpha)
    # a bright core beam straight at the breach point
    cv.poly([(sx, sy), (bx - 14, by), (bx + 14, by + 120)], RAY, 0.22)


def paint_clouds(cv, rng):
    """High wisps plus the rolling cloud sea the whale bursts from."""
    # high thin wisps
    for (cx, cy, rx, ry, a) in [
            (180, 120, 150, 12, 0.35), (330, 96, 110, 9, 0.30),
            (620, 150, 170, 13, 0.32), (860, 90, 130, 10, 0.30),
            (120, 240, 120, 10, 0.28), (520, 210, 140, 11, 0.30),
            (900, 260, 150, 12, 0.30)]:
        cv.ellipse(cx, cy, rx, ry, CLOUD, a)
        cv.ellipse(cx, cy + 8, rx * 0.8, ry * 0.7, CLOUD_SHADE, a * 0.6)
    # cloud sea: a bumpy band hugging the horizon, lit from the sun side
    base_y = HORIZON - 6
    for x in range(-40, W + 40, 26):
        bump = 26 + 18 * math.sin(x * 0.011 + 1.2) + rng.uniform(-7, 7)
        cv.ellipse(x, base_y - bump * 0.35, 62, bump * 0.55, CLOUD, 0.95)
        cv.ellipse(x + 14, base_y - bump * 0.30, 46, bump * 0.42,
                   CLOUD_SHADE, 0.75)
    # deep shadow pockets between cloud rolls
    for x in range(10, W, 90):
        cv.ellipse(x + rng.uniform(-12, 12), base_y + 4,
                   34, 12, CLOUD_DEEP, 0.55)


def paint_sea(cv, rng):
    cv.vgrad(HORIZON, H - 1, SEA)
    # sun glitter: a shimmering path under the sun
    sx, _ = SUN
    for y in range(HORIZON + 8, H - 4, 6):
        t = (y - HORIZON) / (H - HORIZON)
        half = 26 + 150 * t
        n = int(4 + 26 * t)
        for _ in range(n):
            gx = sx + rng.uniform(-half, half)
            gw = rng.uniform(6, 26 + 40 * t)
            cv.blend_span(gx - gw / 2, gx + gw / 2, y, GLITTER,
                          rng.uniform(0.10, 0.38))
    # long swell lines
    for k, y in enumerate(range(HORIZON + 34, H - 10, 46)):
        cv.blend_span(0, W - 1, y, (30, 110, 140), 0.16)
        cv.blend_span(0, W - 1, y + 2, (4, 22, 48), 0.22)
    # foam flecks drifting on the swells
    for _ in range(240):
        fx = rng.uniform(0, W)
        fy = rng.uniform(HORIZON + 10, H - 6)
        cv.disc(fx, fy, rng.uniform(1, 3.4), SEA_FOAM,
                rng.uniform(0.25, 0.7))


def paint_city(cv, rng):
    """A dwarfed skyline along the horizon, windows lit at sunset."""
    x = -6
    while x < W + 10:
        bw = rng.uniform(26, 62)
        bh = rng.uniform(26, 118)
        # two landmark towers, taller than the rest
        if 120 < x < 200 or 800 < x < 880:
            bh = rng.uniform(130, 168)
        top = HORIZON - bh
        cv.poly([(x, HORIZON), (x, top), (x + bw, top), (x + bw, HORIZON)],
                CITY)
        # rooftop antenna on the tallest blocks
        if bh > 110:
            cv.thick_line(x + bw / 2, top, x + bw / 2, top - 26, 3, CITY)
            cv.disc(x + bw / 2, top - 28, 3, (255, 90, 90))
        # lit windows, sparse so the city reads tiny and far away
        rows = int(bh // 16)
        cols = int(bw // 13)
        for r in range(rows):
            for c in range(cols):
                if rng.random() < 0.34:
                    wx = x + 5 + c * 13
                    wy = top + 7 + r * 16
                    cv.span(wx, wx + 4, wy, WINDOW)
                    cv.span(wx, wx + 4, wy + 1, WINDOW)
        x += bw + rng.uniform(2, 10)
    # haze softens the city's base into the sea line
    for y in range(HORIZON - 4, HORIZON + 8):
        cv.blend_span(0, W - 1, y, (255, 170, 90), 0.10)


# ---------------------------------------------------------------- whale

BACK = (52, 80, 114)
BACK_DARK = (34, 54, 82)
BELLY = (238, 228, 206)
BELLY_SHADE = (214, 198, 172)
RIM = (255, 206, 110)
EYE = (12, 16, 26)

# Quadratic Bezier spine: tail buried in the foam -> head high right.
SPINE = ((296, 886), (436, 596), (694, 358))


def bezier(p0, p1, p2, t):
    u = 1.0 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def spine_radius(t):
    """Fat mid-body, tapering to a narrow tail stock and a blunt head."""
    if t < 0.12:
        return 34 + 300 * t          # tail stock widens fast
    if t < 0.62:
        return 66 + 96 * math.sin((t - 0.12) / 0.5 * math.pi * 0.5)
    return 112 - 48 * ((t - 0.62) / 0.38)   # head narrows toward the snout


def paint_whale_body(cv):
    """Body as overlapping discs along the spine (a tapered tube)."""
    steps = 150
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((bezier(*SPINE, t), spine_radius(t)))
    # dark outline first: slightly larger discs, so the body has an edge
    for (x, y), r in pts:
        cv.disc(x, y, r + 5, BACK_DARK)
    for (x, y), r in pts:
        cv.disc(x, y, r, BACK)
    # belly: a second, thinner tube offset toward the lower-left side
    for i in range(steps + 1):
        t = i / steps
        if t < 0.18 or t > 0.72:
            continue
        (x, y), r = pts[i]
        # perpendicular pointing down-left (the belly side)
        dx = pts[min(i + 1, steps)][0][0] - pts[max(i - 1, 0)][0][0]
        dy = pts[min(i + 1, steps)][0][1] - pts[max(i - 1, 0)][0][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        if nx > 0:
            nx, ny = -nx, -ny
        cv.disc(x + nx * r * 0.30, y + ny * r * 0.30, r * 0.50, BELLY)
        # soft halo so the belly edge feathers into the back
        cv.disc(x + nx * r * 0.30, y + ny * r * 0.30, r * 0.57, BELLY, 0.25)
    # belly shading: a soft band along the belly's lower edge
    for i in range(steps + 1):
        t = i / steps
        if t < 0.15 or t > 0.80:
            continue
        (x, y), r = pts[i]
        cv.disc(x - r * 0.42, y + r * 0.55, r * 0.30, BELLY_SHADE, 0.35)
    # sunlit rim along the upper-right edge of the body, mid-body only
    for i in range(steps + 1):
        t = i / steps
        if t < 0.50 or t > 0.80:
            continue
        (x, y), r = pts[i]
        dx = pts[min(i + 1, steps)][0][0] - pts[max(i - 1, 0)][0][0]
        dy = pts[min(i + 1, steps)][0][1] - pts[max(i - 1, 0)][0][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = dy / ln, -dx / ln
        if nx < 0:
            nx, ny = -nx, -ny
        cv.disc(x + nx * r * 0.86, y + ny * r * 0.86, 3.5, RIM, 0.5)
    # snout: a tapered rounded point past the spine end, no cheek patch
    hx, hy = bezier(*SPINE, 1.0)
    cv.disc(hx + 30, hy - 16, 50, BACK)
    cv.disc(hx + 30, hy - 16, 45, BACK)
    # faint jaw line under the snout
    cv.thick_line(hx - 6, hy + 34, hx + 58, hy + 8, 4, BACK_DARK, 0.5)


def paint_flukes(cv):
    """Two broad tail lobes fanning out of the foam at the tail stock."""
    tx, ty = bezier(*SPINE, 0.0)
    # left lobe sweeps out flat to the left, right lobe flat to the right
    cv.poly([(tx - 6, ty - 26), (tx - 236, ty + 34), (tx - 206, ty + 72),
             (tx - 70, ty + 40)], BACK_DARK)
    cv.poly([(tx - 6, ty - 26), (tx - 226, ty + 30), (tx - 198, ty + 62),
             (tx - 66, ty + 34)], BACK)
    cv.poly([(tx + 6, ty - 26), (tx + 224, ty + 22), (tx + 196, ty + 60),
             (tx + 62, ty + 36)], BACK_DARK)
    cv.poly([(tx + 6, ty - 26), (tx + 214, ty + 20), (tx + 188, ty + 52),
             (tx + 58, ty + 30)], BACK)
    # pale undersides catching the sunset
    cv.poly([(tx - 30, ty + 6), (tx - 196, ty + 46), (tx - 176, ty + 58),
             (tx - 52, ty + 26)], BELLY_SHADE, 0.8)
    cv.poly([(tx + 30, ty + 4), (tx + 186, ty + 38), (tx + 168, ty + 50),
             (tx + 48, ty + 24)], BELLY_SHADE, 0.8)
    # centre notch shadow where the lobes meet
    cv.poly([(tx - 14, ty - 22), (tx + 14, ty - 22), (tx, ty + 18)],
            BACK_DARK)


def paint_fin(cv):
    """One pectoral fin tucked against the mid-body, sunlit edge."""
    (x, y), r = bezier(*SPINE, 0.52), spine_radius(0.52)
    cv.poly([(x - 24, y + 52), (x - 132, y + 148), (x - 104, y + 156),
             (x - 4, y + 92)], BACK_DARK)
    cv.poly([(x - 22, y + 48), (x - 124, y + 140), (x - 100, y + 148),
             (x - 2, y + 86)], BACK)
    cv.thick_line(x - 30, y + 56, x - 120, y + 136, 3, RIM, 0.4)


def paint_eye(cv):
    hx, hy = bezier(*SPINE, 1.0)
    ex, ey = hx + 34, hy - 34
    cv.disc(ex, ey, 15, EYE)
    cv.disc(ex - 4, ey - 5, 6, (255, 255, 255))
    cv.disc(ex + 6, ey + 5, 3, (255, 255, 255), 0.7)
    # a faint smile-free brow ridge so the face stays clean
    cv.thick_line(ex - 20, ey - 22, ex + 22, ey - 24, 4, BACK_DARK, 0.6)


def _on_body(x, y):
    """True when a point lies inside the whale silhouette (plus margin)."""
    for i in range(51):
        t = i / 50
        px, py = bezier(*SPINE, t)
        if (x - px) ** 2 + (y - py) ** 2 < (spine_radius(t) + 14) ** 2:
            return True
    return False


def paint_breach_foam(cv, rng, stage):
    """Foam at the waterline. stage 'ring' paints the ring under the
    whale body; stage 'burst' paints column, droplets and streaks over it."""
    bx, by = BREACH
    if stage == "ring":
        # ring: white ellipse with the sea showing through its middle
        cv.ellipse(bx, by + 6, 208, 46, SEA_FOAM)
        cv.ellipse(bx, by + 8, 168, 30, (14, 62, 92))
        cv.ellipse(bx, by + 8, 150, 24, SEA_FOAM, 0.85)
        # ring crest highlights
        for k in range(-5, 6):
            cv.disc(bx + k * 34, by - 22 + abs(k) * 3, 13, SEA_FOAM)
        return
    # rising foam column hugging the tail stock, kept low at the waterline
    for i in range(40):
        t = i / 40
        fx = 322 + rng.uniform(-24, 24) + 36 * t
        fy = by - 8 - 78 * t + rng.uniform(-7, 7)
        fr = rng.uniform(9, 24) * (1.0 - 0.45 * t)
        cv.disc(fx, fy, fr, SEA_FOAM, rng.uniform(0.75, 1.0))
        if rng.random() < 0.5:
            cv.disc(fx + 6, fy + 5, fr * 0.55, FOAM_SHADE, 0.6)
    # big droplets arcing out of the ring, in two fans that clear the body
    placed = 0
    tries = 0
    while placed < 15 and tries < 80:
        tries += 1
        ang = rng.uniform(-2.7, -2.05)
        dist = rng.uniform(130, 280)
        dx = bx + math.cos(ang) * dist
        dy = by - 10 + math.sin(ang) * dist * 0.75
        if _on_body(dx, dy):
            continue
        cv.disc(dx, dy, rng.uniform(5, 15), SEA_FOAM,
                rng.uniform(0.7, 1.0))
        cv.disc(dx + 3, dy + 3, rng.uniform(2, 5), FOAM_SHADE, 0.6)
        placed += 1
    placed = 0
    tries = 0
    while placed < 13 and tries < 80:
        tries += 1
        ang = rng.uniform(-1.05, -0.45)
        dist = rng.uniform(200, 320)
        dx = bx + math.cos(ang) * dist
        dy = by - 10 + math.sin(ang) * dist * 0.75
        if _on_body(dx, dy):
            continue
        cv.disc(dx, dy, rng.uniform(5, 15), SEA_FOAM,
                rng.uniform(0.7, 1.0))
        cv.disc(dx + 3, dy + 3, rng.uniform(2, 5), FOAM_SHADE, 0.6)
        placed += 1
    # spray streaks: short white ticks at the ring's outer edges only
    for _ in range(18):
        side = 1 if rng.random() < 0.5 else -1
        x0 = bx + side * rng.uniform(105, 185)
        cv.thick_line(x0, by - 6, x0 + side * rng.uniform(10, 55),
                      by - rng.uniform(25, 70), 2.5, SEA_FOAM, 0.75)


def paint_spray(cv, rng):
    """Blowhole spray: a tall fan of droplets and sweeping arcs."""
    hx, hy = bezier(*SPINE, 1.0)
    ox, oy = hx + 8, hy - 62
    # sweeping arcs first (behind the droplets): three, wide, faint
    for k in range(3):
        a0 = math.radians(205 + k * 10)
        a1 = math.radians(325 - k * 6)
        r0 = 80 + k * 55
        steps = 40
        prev = None
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            px = ox + math.cos(a) * r0
            py = oy + math.sin(a) * r0 * 0.9 - 30 * (i / steps)
            if prev is not None:
                cv.thick_line(prev[0], prev[1], px, py, 3.5,
                              SEA_FOAM, 0.30)
            prev = (px, py)
    # droplet fan: big near the blowhole, small and fast at the edges
    for _ in range(150):
        ang = rng.uniform(math.radians(190), math.radians(350))
        dist = rng.uniform(18, 265)
        dx = ox + math.cos(ang) * dist
        dy = oy + math.sin(ang) * dist * 0.95 - 24 * (dist / 265)
        r = rng.uniform(2, 11) * (1.0 - dist / 420)
        cv.disc(dx, dy, max(1.5, r), SEA_FOAM, rng.uniform(0.65, 1.0))
    # dense white core right above the blowhole
    for _ in range(60):
        cv.disc(ox + rng.uniform(-26, 26), oy - rng.uniform(0, 70),
                rng.uniform(4, 10), SEA_FOAM, rng.uniform(0.8, 1.0))


# ---------------------------------------------------------------- sky life

def paint_airplane(cv):
    """A tiny jet crossing the top-right corner, dwarfed by the whale."""
    # contrail: two fading parallel lines trailing up-right
    cv.thick_line(838, 158, 1006, 84, 4, (255, 255, 255), 0.55)
    cv.thick_line(838, 166, 1002, 96, 3, (255, 255, 255), 0.35)
    # fuselage, nose pointing up-right along the contrail
    cv.poly([(806, 168), (848, 150), (856, 156), (814, 176)],
            (235, 238, 245))
    # swept wings
    cv.poly([(828, 158), (806, 138), (816, 134), (836, 152)],
            (205, 212, 222))
    cv.poly([(830, 166), (812, 186), (820, 190), (838, 170)],
            (205, 212, 222))
    # tail fin + sun glint on the nose
    cv.poly([(810, 166), (798, 150), (804, 148), (814, 162)],
            (205, 212, 222))
    cv.disc(850, 152, 2, (255, 210, 120))


def paint_birds(cv, rng):
    """Small distant birds, simple two-stroke gulls."""
    for _ in range(9):
        bx = rng.uniform(60, 420)
        by = rng.uniform(150, 330)
        s = rng.uniform(7, 15)
        cv.thick_line(bx - s, by, bx, by - s * 0.55, 2.5, (28, 18, 52))
        cv.thick_line(bx, by - s * 0.55, bx + s, by, 2.5, (28, 18, 52))


# ---------------------------------------------------------------- PNG out

def _filter_row(kind, row, prev):
    """One PNG scanline filter. row/prev are bytes of equal length."""
    if kind == 0:
        return row
    out = bytearray(len(row))
    if kind == 1:  # Sub
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            out[i] = (b - left) & 0xFF
    elif kind == 2:  # Up
        for i, b in enumerate(row):
            out[i] = (b - prev[i]) & 0xFF
    elif kind == 3:  # Average
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            out[i] = (b - ((left + prev[i]) >> 1)) & 0xFF
    else:  # Paeth
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            up = prev[i]
            up_left = prev[i - 3] if i >= 3 else 0
            p = left + up - up_left
            pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
            pred = left if (pa <= pb and pa <= pc) else (
                up if pb <= pc else up_left)
            out[i] = (b - pred) & 0xFF
    return bytes(out)


def _filter_score(data):
    """Sum of absolute values of signed bytes; smaller filters better."""
    return sum(v if v < 128 else 256 - v for v in data)


def write_png(cv, path):
    """Deterministic PNG: fixed filters chosen per row, zlib level 9."""
    raw = bytearray()
    prev = bytes(W * 3)
    for row in cv.rows:
        best = None
        best_score = None
        for kind in range(5):
            cand = _filter_row(kind, bytes(row), prev)
            score = _filter_score(cand)
            if best_score is None or score < best_score:
                best, best_score = kind, score
                best_data = cand
        raw.append(best)
        raw.extend(best_data)
        prev = bytes(row)
    body = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", body) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# ---------------------------------------------------------------- scene

def render():
    rng = random.Random(SEED)
    cv = Canvas(W, H)
    paint_sky(cv)
    paint_sun(cv)
    paint_rays(cv)
    paint_clouds(cv, rng)
    paint_city(cv, rng)
    paint_sea(cv, rng)
    paint_breach_foam(cv, rng, "ring")
    paint_whale_body(cv)
    paint_flukes(cv)
    paint_fin(cv)
    paint_eye(cv)
    paint_breach_foam(cv, rng, "burst")
    paint_spray(cv, rng)
    paint_airplane(cv)
    paint_birds(cv, rng)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(render(), path)
    print(f"wrote {path} ({size} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
