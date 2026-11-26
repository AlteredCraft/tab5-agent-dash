"""Theme-independent drawing loop.

A theme is a module with NAME, BACKGROUND, ANIMATE (model fields to ease) and
regions(). Each Region draws one rectangle of the screen into an off-screen
canvas, and is redrawn only when its key changes. Regions later in the list
paint on top of earlier ones, so where two overlap, only the later region may
have content in the shared area.

The screen object supplies fill(color) and canvas(w, h). A canvas supplies the
drawing calls themes use, plus push(x, y) and close().
"""

EASE_MS = 700
_UNSET = object()


class Region:
    def __init__(self, x, y, w, h, draw, key=None, bg=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.draw = draw
        self.key = key
        self.bg = bg

    def intersects(self, other):
        return (
            self.x < other.x + other.w
            and other.x < self.x + self.w
            and self.y < other.y + other.h
            and other.y < self.y + self.h
        )


class Engine:
    def __init__(self, screen):
        self.screen = screen
        self.theme = None
        self.regions = []
        self._keys = []
        self._canvases = []
        self._target = None
        self._start = None
        self._t0 = 0

    def set_theme(self, theme, now):
        for canvas in self._canvases:
            if canvas is not None:
                canvas.close()
        self.theme = theme
        self.regions = theme.regions()
        self._keys = [_UNSET] * len(self.regions)
        self._canvases = [None] * len(self.regions)
        self._start = None
        self._t0 = now
        self.screen.fill(theme.BACKGROUND)

    def set_model(self, model, now):
        if self._target is not None:
            self._start = self._shown(now)
        self._target = model
        self._t0 = now

    def _shown(self, now):
        elapsed = now - self._t0
        if elapsed >= EASE_MS or self.theme is None:
            return self._target
        t = 1 - elapsed / EASE_MS
        eased = 1 - t * t * t
        shown = dict(self._target)
        for field in self.theme.ANIMATE:
            end = self._target.get(field)
            if end is None:
                continue
            begin = self._start.get(field) if self._start else 0
            if begin is None:
                begin = 0
            shown[field] = begin + (end - begin) * eased
        return shown

    def frame(self, now):
        """Redraw what changed. Returns True while an animation is running."""
        if self.theme is None or self._target is None:
            return False
        shown = self._shown(now)
        count = len(self.regions)
        dirty = [False] * count
        keys = [region.key(shown) if region.key else None for region in self.regions]
        for i in range(count):
            if keys[i] != self._keys[i]:
                dirty[i] = True
            if dirty[i]:
                for j in range(i + 1, count):
                    if self.regions[i].intersects(self.regions[j]):
                        dirty[j] = True
        for i in range(count):
            if not dirty[i]:
                continue
            region = self.regions[i]
            canvas = self._canvases[i]
            if canvas is None:
                canvas = self._canvases[i] = self.screen.canvas(region.w, region.h)
            canvas.fill(self.theme.BACKGROUND if region.bg is None else region.bg)
            region.draw(canvas, shown)
            canvas.push(region.x, region.y)
            self._keys[i] = keys[i]
        return now - self._t0 < EASE_MS
