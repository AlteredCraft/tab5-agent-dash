"""A Pillow implementation of the drawing surface themes use, for previews and tests.

Text is drawn from the same VLW files and with the same metric rules as the
device, so layouts match to the pixel.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

from dash.fonts import SCALE

from tools import vlw

FONT_DIR = Path(__file__).resolve().parent.parent / "device" / "dash" / "vlw"
_fonts = {}


def font(key):
    if key not in _fonts:
        loaded = vlw.decode((FONT_DIR / (key + ".vlw")).read_bytes())
        _fonts[key] = _scaled(loaded, SCALE[key]) if key in SCALE else loaded
    return _fonts[key]


def _scaled(f, n):
    """Pixel-double a font the way the device does for SCALE entries."""
    glyphs = []
    for g in f.glyphs.values():
        if g.width and g.height:
            image = Image.frombytes("L", (g.width, g.height), g.bitmap).resize((g.width * n, g.height * n), Image.NEAREST)
            bitmap = image.tobytes()
        else:
            bitmap = b""
        glyphs.append(vlw.Glyph(g.code, g.width * n, g.height * n, g.advance * n, g.dy * n, g.dx * n, bitmap))
    scaled = vlw.Font(f.size * n, 0, 0, glyphs)
    scaled.max_ascent = f.max_ascent * n
    scaled.max_descent = f.max_descent * n
    return scaled


def _rgb(color):
    return (color >> 16 & 255, color >> 8 & 255, color & 255)


class HostSurface:
    def __init__(self, w, h, parent=None):
        self.w, self.h = w, h
        self.image = Image.new("RGB", (w, h))
        self._draw = ImageDraw.Draw(self.image)
        self._parent = parent
        self.overflow = []

    def fill(self, color):
        self._draw.rectangle((0, 0, self.w, self.h), fill=_rgb(color))

    def rect(self, x, y, w, h, color):
        if w > 0 and h > 0:
            self._note(x, y, w, h, "rect")
            self._draw.rectangle((x, y, x + w - 1, y + h - 1), fill=_rgb(color))

    def arc(self, cx, cy, r0, r1, a0, a1, color):
        """Ring segment between radii r0 and r1. Whole degrees, clockwise from the top."""
        a0, a1 = int(a0), int(a1)
        if a1 <= a0:
            return
        # Bound the swept segment, not the whole circle: a corner piece may
        # sit at a region's edge with its circle's centre outside it.
        points = [
            (cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a)))
            for a in [*range(a0, a1, 5), a1]
            for r in (r0, r1)
        ]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self._note(round(min(xs)), round(min(ys)), round(max(xs) - min(xs)), round(max(ys) - min(ys)), "arc")
        self._draw.arc((cx - r1, cy - r1, cx + r1, cy + r1), a0 - 90, a1 - 90, fill=_rgb(color), width=r1 - r0)

    def text_width(self, s, font_key):
        f = font(font_key)
        return sum(self._glyph(f, c, font_key).advance for c in s)

    def text(self, s, x, y, font_key, color, align=0):
        """Draw text with its top at y. align: 0 left, 1 centre, 2 right of x."""
        f = font(font_key)
        width = self.text_width(s, font_key)
        x = int(x - (width // 2 if align == 1 else width if align == 2 else 0))
        self._note(x, y, width, f.max_ascent + f.max_descent, "text %r" % s)
        for c in s:
            g = self._glyph(f, c, font_key)
            if g.width and g.height:
                mask = Image.frombytes("L", (g.width, g.height), g.bitmap)
                self.image.paste(_rgb(color), (x + g.dx, int(y) + f.max_ascent - g.dy), mask)
            x += g.advance

    def push(self, x, y):
        self._parent.image.paste(self.image, (x, y))

    def close(self):
        pass

    @staticmethod
    def _glyph(f, c, font_key):
        try:
            return f.glyphs[ord(c)]
        except KeyError:
            raise ValueError("font %s has no glyph for %r" % (font_key, c)) from None

    def _note(self, x, y, w, h, what):
        if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
            self.overflow.append("%s at %d,%d size %dx%d" % (what, x, y, w, h))


class HostScreen:
    """Stands in for the Tab5 display: 1280 by 720."""

    def __init__(self, w=1280, h=720):
        self.w, self.h = w, h
        self.image = Image.new("RGB", (w, h))
        self.canvases = []

    def fill(self, color):
        self.image.paste(_rgb(color), (0, 0, self.w, self.h))

    def canvas(self, w, h):
        surface = HostSurface(w, h, parent=self)
        self.canvases.append(surface)
        return surface
