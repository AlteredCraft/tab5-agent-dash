"""The VLW bitmap font format that M5GFX loads with loadFont().

Layout, all integers 32-bit big-endian:
  header:  glyph count, version (11), font size, 0, ascent, descent
  table:   per glyph: code point, height, width, advance, dY, dX, 0
  bitmaps: per glyph: width * height bytes of 8-bit coverage
dY is the distance from the baseline up to the top of the bitmap.

Without a glyph for the space character the loader invents a space width from
the font's height, which is wider than most fonts' own. Including a space
glyph with an empty bitmap makes it use that glyph's advance (checked on the
Tab5).
"""

import struct
from collections import namedtuple

Glyph = namedtuple("Glyph", "code width height advance dy dx bitmap")


class Font:
    def __init__(self, size, ascent, descent, glyphs):
        self.size = size
        self.glyphs = {glyph.code: glyph for glyph in glyphs}
        # M5GFX derives these the same way when it loads the file.
        self.max_ascent = max([ascent] + [glyph.dy for glyph in glyphs])
        self.max_descent = max([descent] + [glyph.height - glyph.dy for glyph in glyphs])


def encode(size, glyphs):
    glyphs = sorted(glyphs, key=lambda glyph: glyph.code)
    ascent = max(glyph.dy for glyph in glyphs)
    descent = max(glyph.height - glyph.dy for glyph in glyphs)
    out = [struct.pack(">6i", len(glyphs), 11, size, 0, ascent, descent)]
    for glyph in glyphs:
        out.append(struct.pack(">7i", glyph.code, glyph.height, glyph.width, glyph.advance, glyph.dy, glyph.dx, 0))
    for glyph in glyphs:
        if len(glyph.bitmap) != glyph.width * glyph.height:
            raise ValueError("bitmap size mismatch for U+%04X" % glyph.code)
        out.append(bytes(glyph.bitmap))
    return b"".join(out)


def decode(data):
    count, version, size, _, ascent, descent = struct.unpack_from(">6i", data, 0)
    if version != 11:
        raise ValueError("unsupported VLW version %d" % version)
    records = [struct.unpack_from(">7i", data, 24 + 28 * i) for i in range(count)]
    offset = 24 + 28 * count
    glyphs = []
    for code, height, width, advance, dy, dx, _ in records:
        glyphs.append(Glyph(code, width, height, advance, dy, dx, data[offset : offset + width * height]))
        offset += width * height
    return Font(size, ascent, descent, glyphs)
