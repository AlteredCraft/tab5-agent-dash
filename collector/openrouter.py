"""OpenRouter spend: per-key usage, account credits and (with a management key) activity."""

import json
import urllib.error
import urllib.request

BASE_URL = "https://openrouter.ai/api/v1"
KEY_FIELDS = ("usage", "usage_daily", "usage_weekly", "usage_monthly", "limit", "limit_remaining")


def http_get_json(path, key, timeout=10):
    request = urllib.request.Request(BASE_URL + path, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read())
        except ValueError:
            body = {}
        return error.code, body


def _summarize_activity(items):
    days, models = {}, {}
    for item in items:
        tokens = sum(item.get(field) or 0 for field in ("prompt_tokens", "completion_tokens", "reasoning_tokens"))
        for groups, name in ((days, str(item.get("date", ""))[:10]), (models, item.get("model") or "unknown")):
            group = groups.setdefault(name, {"cost_usd": 0.0, "requests": 0, "tokens": 0})
            group["cost_usd"] += item.get("usage") or 0
            group["requests"] += item.get("requests") or 0
            group["tokens"] += tokens
    for group in (*days.values(), *models.values()):
        group["cost_usd"] = round(group["cost_usd"], 4)
    return {
        "daily": [{"date": date, **days[date]} for date in sorted(days)],
        "by_model": sorted(
            ({"name": name, **group} for name, group in models.items()),
            key=lambda row: (-row["cost_usd"], row["name"]),
        ),
    }


def fetch(api_key, management_key=None, get=http_get_json):
    """Return the dashboard's OpenRouter section, or None when no key is configured.

    `/activity` is only served to management keys, so it is skipped without one.
    """
    if not api_key and not management_key:
        return None
    errors = []

    def data(path, key):
        status, body = get(path, key)
        if status != 200:
            message = (body.get("error") or {}).get("message", "request failed")
            errors.append(f"{path}: {status} {message}")
            return None
        return body.get("data")

    key_info = data("/key", api_key) if api_key else None
    credits = data("/credits", management_key or api_key)
    activity = data("/activity", management_key) if management_key else None

    return {
        "credits": credits
        and {
            "total": credits["total_credits"],
            "used": credits["total_usage"],
            "remaining": round(credits["total_credits"] - credits["total_usage"], 4),
        },
        "key": key_info and {field: key_info.get(field) for field in KEY_FIELDS},
        "activity": _summarize_activity(activity) if activity is not None else None,
        "errors": errors,
    }
