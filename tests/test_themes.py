import copy

import pytest

from dash import model
from dash.engine import EASE_MS
from dash.fonts import FONTS
from dash.themes import THEMES
from tools.host_surface import font
from tools.preview import render, sample_payload


def variants():
    full = sample_payload()

    no_limits = copy.deepcopy(full)
    no_limits["claude_code"]["limits"] = None

    no_openrouter = copy.deepcopy(full)
    no_openrouter["openrouter"] = None

    extreme = copy.deepcopy(full)
    claude = extreme["claude_code"]
    claude["today"] = {"cost_usd": 12345.67, "total": 9_876_543_210, "output": 123_456_789}
    claude["last_7d"]["cost_usd"] = 98765.43
    claude["last_30d"]["cost_usd"] = 123456.78
    claude["burn"] = {"output_tokens_per_min": 987654, "cost_per_hour": 9876.54}
    claude["active_sessions"] = 12
    claude["limits"]["five_hour"]["used_percentage"] = 100
    claude["limits"]["seven_day"]["used_percentage"] = 3
    claude["by_project_7d"] = [{"name": "W" * 40, "cost_usd": 55555.55}] * 3
    claude["by_model_7d"] = [{"name": "claude-fable-5-2", "cost_usd": 55555.55}] * 2
    extreme["openrouter"]["credits"] = {"total": 100000, "used": 99999.5, "remaining": 0.5}
    extreme["openrouter"]["key"] = {"usage": 12345.67, "limit": 50000}

    quiet = copy.deepcopy(full)
    quiet["claude_code"]["today"] = {"cost_usd": 0, "total": 0, "output": 0}
    quiet["claude_code"]["hourly"] = [dict(h, cost_usd=0.0) for h in quiet["claude_code"]["hourly"]]
    quiet["claude_code"]["daily"] = [dict(d, cost_usd=0.0) for d in quiet["claude_code"]["daily"]]
    quiet["claude_code"]["by_model_7d"] = []
    quiet["claude_code"]["by_project_7d"] = []
    quiet["claude_code"]["active_sessions"] = 0

    return {
        "full": model.build(full),
        "no limits": model.build(no_limits),
        "no openrouter": model.build(no_openrouter),
        "extreme values": model.build(extreme),
        "quiet day": model.build(quiet),
        "stale": model.build(full, stale_min=42),
        "on battery": model.build(full, battery=37),
        "on a full battery": model.build(full, battery=100),
        "waiting for the Mac": model.build(None),
    }


VARIANTS = variants()


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.NAME)
@pytest.mark.parametrize("name", VARIANTS)
@pytest.mark.parametrize("at", [0, EASE_MS // 3, EASE_MS])
def test_theme_draws_every_state_inside_its_regions(theme, name, at):
    image, overflow = render(theme, VARIANTS[name], at)
    assert overflow == []
    assert image.size == (1280, 720)


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.NAME)
def test_theme_regions_stay_on_screen_and_animate_known_fields(theme):
    for region in theme.regions():
        assert region.x >= 0 and region.y >= 0
        assert region.x + region.w <= 1280 and region.y + region.h <= 720
    assert set(theme.ANIMATE) <= set(VARIANTS["full"])


def test_every_registered_font_is_built():
    for key in FONTS:
        assert font(key).glyphs
