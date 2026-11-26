from collector import openrouter

KEY_BODY = {
    "data": {
        "label": "sk-or-v1-abc...123",
        "limit": 50,
        "limit_remaining": 49.8,
        "usage": 0.2,
        "usage_daily": 0.05,
        "usage_weekly": 0.1,
        "usage_monthly": 0.2,
    }
}
CREDITS_BODY = {"data": {"total_credits": 60, "total_usage": 45.4}}
ACTIVITY_BODY = {
    "data": [
        {
            "date": "2026-11-25 00:00:00",
            "model": "openai/gpt-5.6-sol",
            "usage": 1.5,
            "requests": 10,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "reasoning_tokens": 50,
        },
        {
            "date": "2026-11-25",
            "model": "google/gemma-4",
            "usage": 0.5,
            "requests": 4,
            "prompt_tokens": 300,
            "completion_tokens": 100,
        },
        {
            "date": "2026-11-24",
            "model": "openai/gpt-5.6-sol",
            "usage": 2.0,
            "requests": 6,
            "prompt_tokens": 500,
            "completion_tokens": 100,
        },
    ]
}


def fake_get(responses, calls=None):
    def get(path, key):
        if calls is not None:
            calls.append((path, key))
        return responses[path]

    return get


def test_fetch_with_regular_key_only():
    calls = []
    result = openrouter.fetch(
        "regular",
        get=fake_get({"/key": (200, KEY_BODY), "/credits": (200, CREDITS_BODY)}, calls),
    )
    assert result["credits"] == {"total": 60, "used": 45.4, "remaining": 14.6}
    assert result["key"] == {
        "usage": 0.2,
        "usage_daily": 0.05,
        "usage_weekly": 0.1,
        "usage_monthly": 0.2,
        "limit": 50,
        "limit_remaining": 49.8,
    }
    assert result["activity"] is None
    assert result["errors"] == []
    assert calls == [("/key", "regular"), ("/credits", "regular")]


def test_fetch_with_management_key_adds_activity():
    calls = []
    result = openrouter.fetch(
        "regular",
        "mgmt",
        get=fake_get(
            {"/key": (200, KEY_BODY), "/credits": (200, CREDITS_BODY), "/activity": (200, ACTIVITY_BODY)},
            calls,
        ),
    )
    assert ("/credits", "mgmt") in calls and ("/activity", "mgmt") in calls
    assert result["activity"]["daily"] == [
        {"date": "2026-11-24", "cost_usd": 2.0, "requests": 6, "tokens": 600},
        {"date": "2026-11-25", "cost_usd": 2.0, "requests": 14, "tokens": 1650},
    ]
    assert result["activity"]["by_model"] == [
        {"name": "openai/gpt-5.6-sol", "cost_usd": 3.5, "requests": 16, "tokens": 1850},
        {"name": "google/gemma-4", "cost_usd": 0.5, "requests": 4, "tokens": 400},
    ]


def test_fetch_reports_endpoint_errors_without_failing():
    result = openrouter.fetch(
        "regular",
        get=fake_get(
            {
                "/key": (200, KEY_BODY),
                "/credits": (403, {"error": {"message": "Only management keys can do this", "code": 403}}),
            }
        ),
    )
    assert result["key"]["usage"] == 0.2
    assert result["credits"] is None
    assert result["errors"] == ["/credits: 403 Only management keys can do this"]


def test_fetch_without_any_key():
    assert openrouter.fetch(None) is None
