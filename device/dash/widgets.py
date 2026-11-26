"""Regions that every theme shows the same way."""

from .engine import Region

WIDTH = 110
HEIGHT = 32


def battery(x, y, font, color, bg=None):
    """A small battery outline and percentage. Empty while the Tab5 is on external power."""

    def draw(s, m):
        level = m["battery"]
        if level is None:
            return
        for edge in ((0, 5, 36, 2), (0, 21, 36, 2), (0, 5, 2, 18), (34, 5, 2, 18), (36, 10, 3, 8)):
            s.rect(edge[0], edge[1], edge[2], edge[3], color)
        s.rect(4, 9, max(2, 28 * min(level, 100) // 100), 10, color)
        s.text("%d%%" % level, 46, 3, font, color)

    return Region(x, y, WIDTH, HEIGHT, draw, lambda m: m["battery"], bg)
