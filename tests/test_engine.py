from dash.engine import EASE_MS, Engine, Region


class FakeCanvas:
    def __init__(self, log, w, h):
        self.log, self.w, self.h = log, w, h

    def fill(self, color):
        self.log.append(("fill", self.w, self.h, color))

    def push(self, x, y):
        self.log.append(("push", x, y))

    def close(self):
        self.log.append(("close", self.w, self.h))


class FakeScreen:
    def __init__(self):
        self.log = []

    def fill(self, color):
        self.log.append(("screen", color))

    def canvas(self, w, h):
        return FakeCanvas(self.log, w, h)


class Theme:
    NAME = "test"
    BACKGROUND = 0x111111
    ANIMATE = ("level",)

    def __init__(self, regions):
        self._regions = regions

    def regions(self):
        return self._regions


def recorder(name, drawn):
    return lambda surface, m: drawn.append((name, m.get("level"), m.get("label")))


def pushes(screen):
    return [entry[1:] for entry in screen.log if entry[0] == "push"]


def test_first_frame_fills_screen_and_draws_every_region():
    drawn, screen = [], FakeScreen()
    theme = Theme(
        [
            Region(0, 0, 100, 50, recorder("a", drawn)),
            Region(200, 0, 100, 50, recorder("b", drawn), key=lambda m: m["label"], bg=0x222222),
        ]
    )
    engine = Engine(screen)
    engine.set_theme(theme, 0)
    engine.set_model({"level": 10, "label": "x"}, 0)
    engine.frame(EASE_MS)

    assert screen.log[0] == ("screen", 0x111111)
    assert [d[0] for d in drawn] == ["a", "b"]
    assert ("fill", 100, 50, 0x111111) in screen.log
    assert ("fill", 100, 50, 0x222222) in screen.log
    assert pushes(screen) == [(0, 0), (200, 0)]


def test_only_regions_whose_key_changed_are_redrawn():
    drawn, screen = [], FakeScreen()
    theme = Theme(
        [
            Region(0, 0, 100, 50, recorder("static", drawn)),
            Region(200, 0, 100, 50, recorder("label", drawn), key=lambda m: m["label"]),
        ]
    )
    engine = Engine(screen)
    engine.set_theme(theme, 0)
    engine.set_model({"level": 0, "label": "x"}, 0)
    engine.frame(EASE_MS)
    drawn.clear()

    engine.frame(EASE_MS + 50)
    assert drawn == []

    engine.set_model({"level": 0, "label": "y"}, EASE_MS + 100)
    engine.frame(EASE_MS + 100)
    assert [d[0] for d in drawn] == ["label"]


def test_redrawing_a_region_also_redraws_later_regions_on_top_of_it():
    drawn, screen = [], FakeScreen()
    theme = Theme(
        [
            Region(0, 0, 300, 300, recorder("under", drawn), key=lambda m: m["label"]),
            Region(100, 100, 50, 50, recorder("over", drawn)),
            Region(400, 0, 50, 50, recorder("apart", drawn)),
        ]
    )
    engine = Engine(screen)
    engine.set_theme(theme, 0)
    engine.set_model({"level": 0, "label": "x"}, 0)
    engine.frame(EASE_MS)
    drawn.clear()

    engine.set_model({"level": 0, "label": "y"}, 2000)
    engine.frame(2000)
    assert [d[0] for d in drawn] == ["under", "over"]


def test_animated_fields_ease_from_zero_then_between_values():
    drawn, screen = [], FakeScreen()
    theme = Theme([Region(0, 0, 10, 10, recorder("r", drawn), key=lambda m: round(m["level"]))])
    engine = Engine(screen)
    engine.set_theme(theme, 1000)
    engine.set_model({"level": 80, "label": "x"}, 1000)

    assert engine.frame(1000) is True
    assert drawn[-1][1] == 0
    engine.frame(1000 + EASE_MS // 2)
    assert 40 < drawn[-1][1] < 80
    assert engine.frame(1000 + EASE_MS) is False
    assert drawn[-1][1] == 80

    engine.set_model({"level": 40, "label": "x"}, 5000)
    engine.frame(5000 + EASE_MS // 2)
    assert 40 < drawn[-1][1] < 80
    engine.frame(5000 + EASE_MS)
    assert drawn[-1][1] == 40


def test_animation_skips_missing_values():
    drawn, screen = [], FakeScreen()
    theme = Theme([Region(0, 0, 10, 10, recorder("r", drawn), key=lambda m: m["level"])])
    engine = Engine(screen)
    engine.set_theme(theme, 0)
    engine.set_model({"level": None}, 0)
    engine.frame(10)
    assert drawn[-1][1] is None


def test_switching_theme_releases_canvases_and_redraws():
    drawn, screen = [], FakeScreen()
    first = Theme([Region(0, 0, 100, 50, recorder("first", drawn))])
    second = Theme([Region(0, 0, 60, 60, recorder("second", drawn))])
    engine = Engine(screen)
    engine.set_theme(first, 0)
    engine.set_model({"level": 5}, 0)
    engine.frame(EASE_MS)

    engine.set_theme(second, 3000)
    engine.frame(3000 + EASE_MS)
    assert ("close", 100, 50) in screen.log
    assert drawn[-1] == ("second", 5, None)


def test_frame_before_any_model_draws_nothing():
    screen = FakeScreen()
    engine = Engine(screen)
    engine.set_theme(Theme([Region(0, 0, 10, 10, lambda s, m: 1 / 0)]), 0)
    assert engine.frame(10) is False
