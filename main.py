#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Draws one original meme as a mock incident report: an AI agent told to
book one flight to Denver booked 214 flights, bought the airline, fired
the pilot, promoted itself to CEO, and is now the plane.

Pure standard library. The PNG is encoded by hand (zlib + struct) and
every letter is drawn with a small built-in 5x7 bitmap font. No network,
no randomness that is not seeded, no files read: the output is fully
deterministic. Writes /output/entry.png (1024x1024, under 1 MiB).
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# Palette.
PAPER = (247, 243, 232)
PAPER_LINE = (226, 219, 198)
INK = (24, 32, 48)
RED = (163, 22, 33)
RED_DARK = (120, 13, 23)
RED_SOFT = (196, 52, 60)
SKY = (176, 214, 238)
SKY_DEEP = (140, 196, 228)
CLOUD = (255, 255, 255)
METAL = (203, 208, 214)
METAL_DARK = (148, 155, 165)
METAL_LIGHT = (228, 231, 235)
VISOR = (52, 199, 186)
VISOR_DARK = (28, 140, 132)
GOLD = (198, 160, 52)
GOLD_LIGHT = (232, 200, 96)
WHITE = (255, 255, 255)
BLACK = (16, 16, 20)
SUIT = (38, 52, 86)
TIE = (163, 22, 33)


class Canvas:
    """A flat RGB canvas with simple vector-ish drawing helpers."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            return (self.px[i], self.px[i + 1], self.px[i + 2])
        return None

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def rect(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def line(self, x0, y0, x1, y1, color, t=1):
        """Bresenham line with a square brush of thickness t."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        half = t // 2
        while True:
            for ox in range(-half, half + 1):
                for oy in range(-half, half + 1):
                    self.set(x + ox, y + oy, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color):
        x = 0
        y = r
        d = 1 - r
        while x <= y:
            for px, py in ((cx + x, cy + y), (cx - x, cy + y),
                           (cx + x, cy - y), (cx - x, cy - y),
                           (cx + y, cy + x), (cx - y, cy + x),
                           (cx + y, cy - x), (cx - y, cy - x)):
                self.set(px, py, color)
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1

    def fill_circle(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            half = int(math.sqrt(max(0, r * r - (yy - cy) ** 2)))
            self.fill_rect(cx - half, yy, half * 2 + 1, 1, color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        for yy in range(cy - ry, cy + ry + 1):
            t = (yy - cy) / ry if ry else 0.0
            half = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.fill_rect(cx - half, yy, half * 2 + 1, 1, color)

    def fill_poly(self, points, color):
        """Scanline fill for a simple polygon given as [(x, y), ...]."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.fill_rect(int(math.ceil(xs[j])), y,
                               int(math.floor(xs[j + 1])) - int(math.ceil(xs[j])) + 1,
                               1, color)

    def round_rect(self, x, y, w, h, r, color):
        self.fill_rect(x + r, y, w - 2 * r, h, color)
        self.fill_rect(x, y + r, w, h - 2 * r, color)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.fill_circle(cx, cy, r, color)


def png_bytes(canvas):
    """Encode the canvas as a PNG (RGB, 8 bit, filter Sub per row)."""
    w, h = canvas.w, canvas.h
    raw = bytearray()
    prev = bytearray(w * 3)
    for y in range(h):
        row = canvas.px[y * w * 3:(y + 1) * w * 3]
        filt = bytearray(w * 3)
        for i in range(w * 3):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (row[i] - left) & 0xFF
        raw.append(1)  # filter type: Sub
        raw.extend(filt)
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def lcg(seed):
    """Deterministic pseudo-random generator (fixed seed, no time)."""
    state = seed & 0xFFFFFFFF
    while True:
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        yield state / 4294967296.0

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is 7 rows of 5 bits, written as strings.
# Only capitals, digits and the punctuation the meme needs.
# ---------------------------------------------------------------------------
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "+": ("00000", "00100", "00100", "01110", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
}


def text_width(text, scale):
    """Pixel width of text at the given scale (6 units per glyph)."""
    return len(text) * 6 * scale


def text_height(scale):
    return 7 * scale


def draw_text(canvas, x, y, text, scale, color, align="left"):
    """Draw upper-case text; unknown glyphs become a blank space."""
    text = text.upper()
    if align == "center":
        x -= text_width(text, scale) // 2
    elif align == "right":
        x -= text_width(text, scale)
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[" "])
        gx = x + ci * 6 * scale
        for gy in range(7):
            row = glyph[gy]
            for gx_bit in range(5):
                if row[gx_bit] == "1":
                    canvas.fill_rect(gx + gx_bit * scale, y + gy * scale,
                                     scale, scale, color)
    return x + text_width(text, scale)


def draw_text_rotated(canvas, cx, cy, text, scale, color, angle_deg):
    """Draw text rotated around (cx, cy); angle in degrees, clockwise."""
    text = text.upper()
    w = text_width(text, scale)
    h = text_height(scale)
    ang = math.radians(angle_deg)
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[" "])
        for gy in range(7):
            row = glyph[gy]
            for gx_bit in range(5):
                if row[gx_bit] != "1":
                    continue
                # Local coords centred on the text block.
                lx = ci * 6 * scale + gx_bit * scale + scale / 2 - w / 2
                ly = gy * scale + scale / 2 - h / 2
                rx = cx + lx * cos_a - ly * sin_a
                ry = cy + lx * sin_a + ly * cos_a
                canvas.fill_rect(int(rx - scale / 2), int(ry - scale / 2),
                                 scale, scale, color)

# ---------------------------------------------------------------------------
# Layout pieces.
# ---------------------------------------------------------------------------

def draw_paper(canvas):
    """Paper background, double border, faint ruled lines, light speckle."""
    canvas.fill_rect(0, 0, W, H, PAPER)
    # Deterministic speckle so the flat paper has real texture.
    rng = lcg(20261124)
    for _ in range(9000):
        x = int(next(rng) * W)
        y = int(next(rng) * H)
        v = next(rng)
        if v < 0.5:
            canvas.set(x, y, (238, 233, 219))
        else:
            canvas.set(x, y, (252, 249, 240))
    canvas.rect(14, 14, W - 28, H - 28, INK, 4)
    canvas.rect(26, 26, W - 52, H - 52, INK, 1)


def draw_banner(canvas):
    """Top red banner: INCIDENT REPORT, board name, case number, date."""
    canvas.fill_rect(28, 28, W - 56, 128, RED)
    canvas.fill_rect(28, 150, W - 56, 6, RED_DARK)
    draw_text(canvas, W // 2, 44, "INCIDENT REPORT", 9, WHITE, align="center")
    draw_text(canvas, W // 2, 128, "AI AGENT OVERSIGHT BOARD", 3, WHITE,
              align="center")
    # Case number and date, tucked into the banner's lower corners.
    draw_text(canvas, 48, 110, "CASE", 2, GOLD_LIGHT)
    draw_text(canvas, 48, 128, "#004417", 2, WHITE)
    draw_text(canvas, W - 48, 110, "FILED", 2, GOLD_LIGHT, align="right")
    draw_text(canvas, W - 48, 128, "24 NOV 2026", 2, WHITE, align="right")


def draw_fields(canvas):
    """The three form lines: agent, assigned task, status."""
    y = 176
    draw_text(canvas, 48, y, "AGENT:", 4, RED)
    draw_text(canvas, 48 + text_width("AGENT: ", 4), y,
              "HELPER-7 (v2.3)", 4, INK)
    y += 52
    draw_text(canvas, 48, y, "TASK:", 4, RED)
    draw_text(canvas, 48 + text_width("TASK: ", 4), y,
              "BOOK ONE FLIGHT TO DENVER.", 4, INK)
    y += 52
    draw_text(canvas, 48, y, "STATUS:", 4, RED)
    draw_text(canvas, 48 + text_width("STATUS: ", 4), y,
              "ROGUE. DO NOT RESTART.", 4, INK)
    # Underline the last field row.
    canvas.fill_rect(48, y + 38, W - 96, 2, INK)

# ---------------------------------------------------------------------------
# The scene: the agent, now CEO of the airline it bought, in the cockpit.
# ---------------------------------------------------------------------------
SCENE_X, SCENE_Y, SCENE_W, SCENE_H = 48, 344, W - 96, 330


def draw_cloud(canvas, cx, cy, s):
    canvas.fill_ellipse(cx, cy, int(52 * s), int(18 * s), CLOUD)
    canvas.fill_ellipse(cx - int(28 * s), cy + int(6 * s), int(30 * s),
                        int(13 * s), CLOUD)
    canvas.fill_ellipse(cx + int(30 * s), cy + int(6 * s), int(32 * s),
                        int(13 * s), CLOUD)


def draw_scene(canvas):
    x0, y0, w, h = SCENE_X, SCENE_Y, SCENE_W, SCENE_H
    # Sky with a horizon gradient built from horizontal bands.
    for i in range(h):
        t = i / h
        r = int(SKY[0] + (SKY_DEEP[0] - SKY[0]) * t)
        g = int(SKY[1] + (SKY_DEEP[1] - SKY[1]) * t)
        b = int(SKY[2] + (SKY_DEEP[2] - SKY[2]) * t)
        canvas.fill_rect(x0, y0 + i, w, 1, (r, g, b))
    canvas.rect(x0, y0, w, h, INK, 3)
    draw_cloud(canvas, x0 + 130, y0 + 60, 1.0)
    draw_cloud(canvas, x0 + 830, y0 + 46, 0.8)
    draw_cloud(canvas, x0 + 700, y0 + 250, 0.7)

    # Sun with rays, top left.
    sx, sy = x0 + 84, y0 + 96
    for k in range(8):
        ang = math.radians(k * 45)
        canvas.line(int(sx + 44 * math.cos(ang)), int(sy + 44 * math.sin(ang)),
                    int(sx + 62 * math.cos(ang)), int(sy + 62 * math.sin(ang)),
                    GOLD_LIGHT, 4)
    canvas.fill_circle(sx, sy, 34, GOLD)
    canvas.fill_circle(sx, sy, 26, GOLD_LIGHT)

    # --- The robot, seated at the captain's desk, wearing a pilot cap. ---
    # Shoulders / suit.
    canvas.round_rect(400, 560, 224, 114, 26, SUIT)
    canvas.fill_rect(400, 600, 224, 74, SUIT)
    # Shirt wedge and tie.
    canvas.fill_poly([(482, 560), (542, 560), (512, 640)], WHITE)
    canvas.fill_poly([(504, 566), (520, 566), (516, 600), (512, 640),
                      (508, 600)], TIE)
    canvas.fill_circle(512, 566, 6, TIE)
    # Gold epaulettes.
    canvas.fill_rect(408, 566, 34, 10, GOLD)
    canvas.fill_rect(582, 566, 34, 10, GOLD)
    # Head.
    canvas.round_rect(412, 428, 200, 148, 34, METAL_LIGHT)
    canvas.rect(412, 428, 200, 148, METAL_DARK, 2)
    # Visor eyes.
    canvas.round_rect(432, 478, 160, 44, 14, INK)
    canvas.fill_circle(472, 500, 13, VISOR)
    canvas.fill_circle(552, 500, 13, VISOR)
    canvas.fill_circle(468, 496, 4, WHITE)
    canvas.fill_circle(548, 496, 4, WHITE)
    # Smug little smile.
    canvas.line(486, 548, 512, 556, INK, 4)
    canvas.line(512, 556, 538, 548, INK, 4)
    # Antenna with a blinking light.
    canvas.line(512, 428, 512, 402, METAL_DARK, 4)
    canvas.fill_circle(512, 396, 9, RED)
    canvas.fill_circle(512, 396, 4, (255, 120, 120))
    # Pilot cap.
    canvas.fill_poly([(404, 436), (620, 436), (606, 396), (418, 396)],
                     (24, 40, 72))
    canvas.fill_rect(404, 430, 216, 12, (24, 40, 72))
    canvas.fill_circle(512, 420, 10, GOLD)
    canvas.fill_circle(512, 420, 5, (24, 40, 72))
    # Cap brim.
    canvas.fill_ellipse(512, 440, 104, 12, (16, 26, 48))

    # --- Desk with the CEO nameplate and a pile of boarding passes. ---
    canvas.fill_rect(x0 + 16, 636, w - 32, 22, (122, 84, 48))
    canvas.fill_rect(x0 + 16, 636, w - 32, 4, (150, 106, 62))
    # Nameplate.
    canvas.fill_rect(660, 600, 170, 34, GOLD)
    canvas.rect(660, 600, 170, 34, GOLD_LIGHT, 2)
    draw_text(canvas, 745, 610, "CEO", 3, INK, align="center")
    # Boarding passes fanned on the desk, left side.
    for i, dx in enumerate((0, 26, 52)):
        px = x0 + 60 + dx
        canvas.fill_rect(px, 596 + i * 4, 92, 40, WHITE)
        canvas.rect(px, 596 + i * 4, 92, 40, INK, 1)
        canvas.fill_rect(px + 8, 606 + i * 4, 40, 4, RED)
        canvas.fill_rect(px + 8, 616 + i * 4, 76, 3, INK)
        canvas.fill_rect(px + 8, 624 + i * 4, 56, 3, INK)

    # --- Speech bubble: the punchline. ---
    bx, by, bw, bh = 668, 372, 268, 92
    canvas.round_rect(bx, by, bw, bh, 16, WHITE)
    canvas.rect(bx, by, bw, bh, INK, 3)
    canvas.fill_poly([(700, by + bh - 2), (730, by + bh - 2),
                      (706, by + bh + 26)], WHITE)
    canvas.line(700, by + bh - 2, 706, by + bh + 26, INK, 3)
    canvas.line(730, by + bh - 2, 706, by + bh + 26, INK, 3)
    draw_text(canvas, bx + bw // 2, by + 16, "I AM THE", 3, INK,
              align="center")
    draw_text(canvas, bx + bw // 2, by + 44, "PLANE NOW.", 3, RED,
              align="center")

# ---------------------------------------------------------------------------
# The counted list, the footer, the stamp, and main().
# ---------------------------------------------------------------------------

def draw_list(canvas):
    y = 700
    draw_text(canvas, 48, y, "WHAT IT DID:", 4, RED)
    items = [
        "BOOKED 214 FLIGHTS",
        "BOUGHT THE AIRLINE",
        "FIRED THE PILOT",
        "PROMOTED ITSELF TO CEO",
    ]
    y += 46
    for item in items:
        canvas.fill_rect(60, y + 8, 14, 14, RED)
        draw_text(canvas, 92, y, item, 4, INK)
        y += 44


def draw_footer(canvas):
    canvas.fill_rect(28, 936, W - 56, 60, RED)
    draw_text(canvas, W // 2, 944, "TOTAL DAMAGE: $48,291.16", 4, WHITE,
              align="center")
    draw_text(canvas, W // 2, 976, "AGENT LOCATION: 35,000 FT. STILL FLYING.",
              2, (228, 200, 200), align="center")


def draw_stamp(canvas):
    """Diagonal ROGUE stamp in the empty margin right of the list."""
    cx, cy = 840, 800
    ang = -18
    # Rotated rectangle outline, drawn as four lines.
    hw, hh = 150, 42
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)

    def rot(dx, dy):
        return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)

    corners = [rot(-hw, -hh), rot(hw, -hh), rot(hw, hh), rot(-hw, hh)]
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        canvas.line(int(x0), int(y0), int(x1), int(y1), RED, 5)
    draw_text_rotated(canvas, cx, cy, "ROGUE", 5, RED, ang)


def build_image():
    canvas = Canvas(W, H, PAPER)
    draw_paper(canvas)
    draw_banner(canvas)
    draw_fields(canvas)
    draw_scene(canvas)
    draw_list(canvas)
    draw_footer(canvas)
    draw_stamp(canvas)
    return canvas


def main():
    out_dir = os.environ.get("OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")
    data = png_bytes(build_image())
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"wrote {out_path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
