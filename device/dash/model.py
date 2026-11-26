"""Turns the collector's payload into the flat dict that themes draw from.

Runs on MicroPython and CPython, so it avoids datetime and regular expressions.
"""

from .fonts import TEXT

WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
PROJECT_NAME_LIMIT = 22


def thousands(n):
    digits = str(int(n))
    out = ""
    while len(digits) > 3:
        out = "," + digits[-3:] + out
        digits = digits[:-3]
    return digits + out


def money(value):
    cents = int(round(value * 100))
    return "$%s.%02d" % (thousands(cents // 100), cents % 100)


def tokens(n):
    if n >= 1000000000:
        return "%.1fB" % (n / 1000000000)
    if n >= 1000000:
        return "%.1fM" % (n / 1000000)
    if n >= 1000:
        return "%dK" % (n // 1000)
    return str(int(n))


def _drawable(text):
    """Names come from outside, and the fonts only hold the TEXT characters."""
    return "".join(c if c in TEXT or c == " " else "-" for c in text)


def model_name(model_id):
    name = _drawable(model_id.split("/")[-1])
    if not name.startswith("claude-"):
        return name
    parts = name.split("-")[1:]
    version = ".".join(p for p in parts[1:] if p.isdigit())
    family = parts[0][0].upper() + parts[0][1:]
    return (family + " " + version).strip()


def project_name(name):
    while name.startswith("_"):
        name = name[1:]
    return _drawable(name.replace("_", " ").lower())[:PROJECT_NAME_LIMIT]


def _days_from_civil(y, m, d):
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def _utc_minutes(iso):
    days = _days_from_civil(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]))
    return days * 1440 + int(iso[11:13]) * 60 + int(iso[14:16])


def _offset_minutes(iso_local):
    tail = iso_local[19:]
    if len(tail) < 6:
        return 0
    sign = -1 if tail[0] == "-" else 1
    return sign * (int(tail[1:3]) * 60 + int(tail[4:6]))


def _resets_text(window, now_minutes, offset):
    if not window or not window.get("resets_at"):
        return ""
    resets = _utc_minutes(window["resets_at"])
    remaining = resets - now_minutes
    if remaining <= 0:
        return ""
    if remaining < 60:
        return "resets in %d min" % remaining
    if remaining < 1440:
        return "resets in %d h %d min" % (remaining // 60, remaining % 60)
    local = resets + offset
    weekday = WEEKDAYS[(local // 1440 + 4) % 7]
    return "resets %s %02d:%02d" % (weekday, local % 1440 // 60, local % 60)


def _status(ok, active_sessions, stale_min):
    if not ok:
        return "Waiting for the Mac"
    if stale_min and stale_min >= 2:
        return "No data for %d min" % stale_min
    if active_sessions == 1:
        return "1 session working"
    if active_sessions:
        return "%d sessions working" % active_sessions
    return "Idle"


def build(payload, stale_min=0, battery=None):
    """`battery` is the charge percentage while running on battery, else None."""
    m = {
        "battery": battery,
        "ok": False,
        "today_cost": 0,
        "today_tokens": 0,
        "today_written": 0,
        "cost_per_hour": 0,
        "tokens_per_min": 0,
        "week_cost": 0,
        "month_cost": 0,
        "daily": [0.0] * 30,
        "hourly": [0.0] * 24,
        "now_hour": 0.0,
        "cur_hour": 0,
        "five_hour": None,
        "five_hour_resets": "",
        "seven_day": None,
        "seven_day_resets": "",
        "models": [],
        "projects": [],
        "or_remaining": None,
        "or_total": None,
        "or_used": None,
        "or_key_usage": None,
        "or_key_limit": None,
    }
    claude = payload and payload.get("claude_code")
    if not claude:
        m["status"] = _status(False, 0, stale_min)
        return m

    m["ok"] = True
    m["today_cost"] = claude["today"]["cost_usd"]
    m["today_tokens"] = claude["today"]["total"]
    m["today_written"] = claude["today"]["output"]
    m["cost_per_hour"] = claude["burn"]["cost_per_hour"]
    m["tokens_per_min"] = int(claude["burn"]["output_tokens_per_min"])
    m["week_cost"] = claude["last_7d"]["cost_usd"]
    m["month_cost"] = claude["last_30d"]["cost_usd"]
    m["daily"] = [day["cost_usd"] for day in claude["daily"]]
    m["status"] = _status(True, claude.get("active_sessions", 0), stale_min)

    now_minutes = _utc_minutes(payload["generated_at"])
    hours = claude["hourly"]
    offset = _offset_minutes(hours[-1]["start"]) if hours else 0
    local_minutes = (now_minutes + offset) % 1440
    m["now_hour"] = local_minutes / 60
    m["cur_hour"] = local_minutes // 60
    if hours:
        today = hours[-1]["start"][:10]
        for hour in hours:
            if hour["start"][:10] == today:
                m["hourly"][int(hour["start"][11:13])] = hour["cost_usd"]

    limits = claude.get("limits") or {}
    for name in ("five_hour", "seven_day"):
        window = limits.get(name)
        if window:
            m[name] = window["used_percentage"]
            m[name + "_resets"] = _resets_text(window, now_minutes, offset)

    m["models"] = [(model_name(row["name"]), row["cost_usd"]) for row in claude["by_model_7d"][:3]]
    m["projects"] = [(project_name(row["name"]), row["cost_usd"]) for row in claude["by_project_7d"][:3]]

    openrouter = payload.get("openrouter") or {}
    credits = openrouter.get("credits")
    if credits:
        m["or_remaining"] = credits["remaining"]
        m["or_total"] = credits["total"]
        m["or_used"] = credits["used"]
    key = openrouter.get("key")
    if key:
        m["or_key_usage"] = key.get("usage")
        m["or_key_limit"] = key.get("limit")
    return m
