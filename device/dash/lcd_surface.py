"""The drawing surface themes use, on the Tab5's display (M5GFX)."""

from .fonts import SCALE, device_path


class LcdCanvas:
    def __init__(self, lcd, w, h):
        self._c = lcd.newCanvas(w, h, 16, True)
        self._font = None

    def fill(self, color):
        self._c.fillScreen(color)

    def rect(self, x, y, w, h, color):
        if w > 0 and h > 0:
            self._c.fillRect(int(x), int(y), int(w), int(h), color)

    def arc(self, cx, cy, r0, r1, a0, a1, color):
        """Ring segment between radii r0 and r1. Whole degrees, clockwise from the top."""
        a0, a1 = int(a0), int(a1)
        if a1 <= a0:
            return
        # M5GFX measures angles clockwise from 3 o'clock.
        if a1 - a0 >= 360:
            start, end = 0, 360
        else:
            start = (a0 + 270) % 360
            end = start + (a1 - a0)
        self._c.fillArc(int(cx), int(cy), int(r0), int(r1), start, end, color)

    def _use(self, font):
        if font != self._font:
            self._c.loadFont(device_path(font))
            self._c.setTextSize(SCALE.get(font, 1))
            self._font = font

    def text_width(self, s, font):
        self._use(font)
        return self._c.textWidth(s)

    def text(self, s, x, y, font, color, align=0):
        """Draw text with its top at y. align: 0 left, 1 centre, 2 right of x."""
        self._use(font)
        if align:
            width = self._c.textWidth(s)
            x -= width // 2 if align == 1 else width
        # With one argument the background defaults to black and is painted as
        # a box behind the text. Equal colours mean "no background" in M5GFX.
        self._c.setTextColor(color, color)
        self._c.drawString(s, int(x), int(y))

    def push(self, x, y):
        self._c.push(x, y)

    def close(self):
        self._c.delete()


class LcdScreen:
    def __init__(self, lcd):
        self._lcd = lcd

    def fill(self, color):
        self._lcd.fillScreen(color)

    def canvas(self, w, h):
        return LcdCanvas(self._lcd, w, h)
