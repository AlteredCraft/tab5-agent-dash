import json

import pytest

from dash import settings
from dash.gestures import DoubleTap
from tools.preview import render


@pytest.mark.parametrize(
    "values",
    [
        {"volume": 0, "muted": False},
        {"volume": 50, "muted": False},
        {"volume": 100, "muted": False},
        {"volume": 70, "muted": True},
    ],
    ids=lambda v: "%d%s" % (v["volume"], " muted" if v["muted"] else ""),
)
@pytest.mark.parametrize("battery", [None, 100])
def test_settings_screen_draws_inside_its_regions(values, battery):
    image, overflow = render(settings, settings.view(values, battery))
    assert overflow == []
    assert image.size == (1280, 720)


def test_buttons_are_on_screen_and_apart():
    boxes = list(settings.BUTTONS.values())
    for x, y, w, h in boxes:
        assert x >= settings.SLOP and y >= settings.SLOP
        assert x + w + settings.SLOP <= 1280 and y + h + settings.SLOP <= 720
    for name, (x, y, w, h) in settings.BUTTONS.items():
        assert settings.hit(x + w // 2, y + h // 2) == name
    assert settings.hit(640, 280) is None  # the volume bar


def test_adjust_steps_and_clamps():
    values = {"volume": 90, "muted": False}
    values = settings.adjust(values, "up")
    assert values["volume"] == 100
    assert settings.adjust(values, "up")["volume"] == 100
    assert settings.adjust({"volume": 0, "muted": False}, "down")["volume"] == 0
    assert settings.adjust(values, "mute")["muted"] is True
    assert values["muted"] is False, "adjust returns a copy"


def test_speaker_volume_and_audible():
    assert settings.speaker_volume({"volume": 100, "muted": False}) == 255
    assert settings.speaker_volume({"volume": 100, "muted": True}) == 0
    assert settings.audible({"volume": 10, "muted": False})
    assert not settings.audible({"volume": 0, "muted": False})
    assert not settings.audible({"volume": 50, "muted": True})


def test_load_and_save_round_trip(tmp_path):
    path = str(tmp_path / "settings.json")
    assert settings.load(path) == settings.DEFAULTS
    settings.save(path, {"volume": 30, "muted": True})
    assert settings.load(path) == {"volume": 30, "muted": True}


@pytest.mark.parametrize("content", ["not json", "[]", '{"volume": "loud"}'])
def test_load_falls_back_to_defaults(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    assert settings.load(str(path)) == settings.DEFAULTS


def test_load_clamps_and_rounds(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"volume": 137, "muted": 0}))
    assert settings.load(str(path)) == {"volume": 100, "muted": False}
    path.write_text(json.dumps({"volume": 45}))
    assert settings.load(str(path))["volume"] == 40


def test_double_tap():
    taps = DoubleTap(window_ms=400, distance_px=80)
    assert not taps.press(640, 360, 0)
    assert taps.press(650, 370, 300)
    # A third tap starts a new pair rather than completing another.
    assert not taps.press(650, 370, 400)


def test_double_tap_needs_both_taps_close_in_time_and_place():
    taps = DoubleTap(window_ms=400, distance_px=80)
    assert not taps.press(640, 360, 0)
    assert not taps.press(640, 360, 500)  # too slow, becomes the first tap
    assert not taps.press(900, 360, 600)  # too far
    assert taps.press(890, 350, 800)
    taps.press(640, 360, 1000)
    taps.reset()
    assert not taps.press(640, 360, 1100)
