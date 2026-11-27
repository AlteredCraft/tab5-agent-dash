"""Touch gestures that need timing, kept apart from the device so they can be tested."""

DOUBLE_TAP_MS = 400
DOUBLE_TAP_PX = 80


class DoubleTap:
    """Feed it each new press; it says when a press completes a double tap."""

    def __init__(self, window_ms=DOUBLE_TAP_MS, distance_px=DOUBLE_TAP_PX):
        self.window_ms = window_ms
        self.distance_px = distance_px
        self._last = None

    def press(self, x, y, now):
        last = self._last
        if (
            last is not None
            and now - last[2] <= self.window_ms
            and abs(x - last[0]) <= self.distance_px
            and abs(y - last[1]) <= self.distance_px
        ):
            self._last = None
            return True
        self._last = (x, y, now)
        return False

    def reset(self):
        self._last = None
