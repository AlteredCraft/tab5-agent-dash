from dash import model


def payload(**claude_overrides):
    hourly = [
        {"start": "2026-11-25T%02d:00:00-08:00" % h, "cost_usd": 9.0, "output": 1, "total": 1}
        for h in range(16, 24)
    ] + [
        {"start": "2026-11-26T%02d:00:00-08:00" % h, "cost_usd": float(h), "output": 1, "total": 1}
        for h in range(0, 16)
    ]
    claude = {
        "today": {"cost_usd": 38.2, "total": 31_400_000, "output": 212_000},
        "last_7d": {"cost_usd": 81.29},
        "last_30d": {"cost_usd": 232.29},
        "daily": [{"date": "x", "cost_usd": float(i)} for i in range(30)],
        "hourly": hourly,
        "by_model_7d": [
            {"name": "claude-fable-5-2", "cost_usd": 76.27},
            {"name": "claude-opus-5-5", "cost_usd": 5.03},
        ],
        "by_project_7d": [
            {"name": "storefront-api", "cost_usd": 62.56},
            {"name": "_RESEARCH_NOTES", "cost_usd": 9.27},
            {"name": "a", "cost_usd": 3.0},
            {"name": "b", "cost_usd": 2.0},
        ],
        "burn": {"output_tokens_per_min": 2340.4, "cost_per_hour": 5.5},
        "active_sessions": 1,
        "limits": {
            "captured_at": "2026-11-26T23:30:00Z",
            "five_hour": {"used_percentage": 62, "resets_at": "2026-11-27T01:28:00Z"},
            "seven_day": {"used_percentage": 34.4, "resets_at": "2026-11-30T02:00:00Z"},
        },
    }
    claude.update(claude_overrides)
    return {
        "generated_at": "2026-11-26T23:40:00Z",
        "claude_code": claude,
        "openrouter": {
            "credits": {"total": 60, "used": 45.39, "remaining": 14.61},
            "key": {"usage": 0.2, "limit": 50},
            "activity": None,
            "errors": [],
        },
    }


def test_formatting_helpers():
    assert model.money(38.2) == "$38.20"
    assert model.money(1234.5) == "$1,234.50"
    assert model.money(0) == "$0.00"
    assert model.tokens(31_400_000) == "31.4M"
    assert model.tokens(212_000) == "212K"
    assert model.tokens(950) == "950"
    assert model.tokens(2_500_000_000) == "2.5B"
    assert model.thousands(2340) == "2,340"
    assert model.thousands(12) == "12"


def test_build_core_fields():
    m = model.build(payload())
    assert m["ok"] is True
    assert m["today_cost"] == 38.2
    assert m["today_tokens"] == 31_400_000
    assert m["today_written"] == 212_000
    assert m["cost_per_hour"] == 5.5
    assert m["tokens_per_min"] == 2340
    assert m["week_cost"] == 81.29
    assert m["month_cost"] == 232.29
    assert m["daily"] == [float(i) for i in range(30)]
    assert m["status"] == "1 session working"


def test_build_hourly_is_aligned_to_todays_clock():
    m = model.build(payload())
    assert len(m["hourly"]) == 24
    assert m["hourly"][:16] == [float(h) for h in range(16)]
    assert m["hourly"][16:] == [0.0] * 8
    assert m["cur_hour"] == 15
    assert abs(m["now_hour"] - (15 + 40 / 60)) < 1e-6


def test_build_limits_and_reset_text():
    m = model.build(payload())
    assert m["five_hour"] == 62
    assert m["five_hour_resets"] == "resets in 1 h 48 min"
    assert m["seven_day"] == 34.4
    # 2026-11-30T02:00Z is Sunday 29 November 18:00 at UTC-8
    assert m["seven_day_resets"] == "resets Sunday 18:00"


def test_reset_text_under_an_hour():
    limits = {"five_hour": {"used_percentage": 5, "resets_at": "2026-11-27T00:25:00Z"}}
    m = model.build(payload(limits=limits))
    assert m["five_hour_resets"] == "resets in 45 min"
    assert m["seven_day"] is None
    assert m["seven_day_resets"] == ""


def test_build_without_limits():
    m = model.build(payload(limits=None))
    assert m["five_hour"] is None and m["seven_day"] is None


def test_build_names():
    m = model.build(payload())
    assert m["models"] == [("Fable 5.2", 76.27), ("Opus 5.5", 5.03)]
    assert m["projects"] == [("storefront-api", 62.56), ("research notes", 9.27), ("a", 3.0)]
    assert model.model_name("openai/gpt-5.6-sol") == "gpt-5.6-sol"
    assert model.project_name("a-very-long-project-name-that-overflows") == "a-very-long-project-na"
    assert model.project_name("@scope/pkg") == "-scope-pkg"


def test_build_openrouter():
    m = model.build(payload())
    assert (m["or_remaining"], m["or_total"], m["or_used"]) == (14.61, 60, 45.39)
    assert (m["or_key_usage"], m["or_key_limit"]) == (0.2, 50)
    data = payload()
    data["openrouter"] = None
    assert model.build(data)["or_remaining"] is None


def test_status_text():
    assert model.build(payload(active_sessions=0))["status"] == "Idle"
    assert model.build(payload(active_sessions=3))["status"] == "3 sessions working"
    assert model.build(payload(), stale_min=4)["status"] == "No data for 4 min"


def test_battery_is_passed_through():
    assert model.build(payload())["battery"] is None
    assert model.build(payload(), battery=64)["battery"] == 64
    assert model.build(None, battery=5)["battery"] == 5


def test_build_without_payload():
    m = model.build(None)
    assert m["ok"] is False
    assert m["status"] == "Waiting for the Mac"
    assert m["today_cost"] == 0
    assert len(m["hourly"]) == 24 and len(m["daily"]) == 30
    assert m["five_hour"] is None and m["or_remaining"] is None
