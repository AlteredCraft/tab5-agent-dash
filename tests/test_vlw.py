import struct

import pytest

from tools import vlw
from tools.build_fonts import render


def glyph(code, width=2, height=3, advance=4, dy=3, dx=0):
    return vlw.Glyph(code, width, height, advance, dy, dx, bytes(range(width * height)))


def test_round_trip_sorts_glyphs_and_keeps_bitmaps():
    data = vlw.encode(24, [glyph(ord("b"), dy=10, height=10), glyph(ord("a"), width=5)])
    count, version, size = struct.unpack_from(">3i", data, 0)
    assert (count, version, size) == (2, 11, 24)
    assert struct.unpack_from(">i", data, 24)[0] == ord("a")

    font = vlw.decode(data)
    assert font.glyphs[ord("a")] == glyph(ord("a"), width=5)
    assert font.glyphs[ord("b")].bitmap == bytes(range(20))


def test_metrics_come_from_the_glyphs():
    font = vlw.decode(vlw.encode(24, [glyph(ord("d"), dy=17, height=17), glyph(ord("g"), dy=11, height=16)]))
    assert font.max_ascent == 17
    assert font.max_descent == 5


def test_encode_rejects_wrong_bitmap_size():
    bad = vlw.Glyph(65, 2, 2, 3, 2, 0, b"\x00")
    with pytest.raises(ValueError):
        vlw.encode(10, [bad])


def test_rendered_fonts_carry_an_empty_space_glyph_with_the_real_advance():
    font = vlw.decode(render("BarlowSemiCondensed-Regular.ttf", None, 22, "ab"))
    space = font.glyphs[ord(" ")]
    assert (space.width, space.height, space.bitmap) == (0, 0, b"")
    assert 0 < space.advance < font.glyphs[ord("a")].advance
