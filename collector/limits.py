"""Subscription rate limits, captured from Claude Code's status line input.

Claude Code only exposes the 5-hour and 7-day limit percentages to its status
line command, so this file doubles as that command: run as a script it saves
the limits for the collector and prints a short status line. It must stay
importable without the rest of the package for that reason.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(os.environ.get("TAB5_DASH_STATE_DIR", "~/.cache/tab5-agent-dash")).expanduser() / "limits.json"
WINDOWS = ("five_hour", "seven_day")
LABELS = {"five_hour": "5h", "seven_day": "7d"}


def _iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def capture(statusline_input, path, now):
    rate_limits = statusline_input.get("rate_limits")
    if not isinstance(rate_limits, dict) or not rate_limits:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"captured_at": now.timestamp(), "rate_limits": rate_limits}))
    temporary.replace(path)


def read(path, now):
    try:
        state = json.loads(Path(path).read_text())
        result = {"captured_at": _iso_utc(datetime.fromtimestamp(state["captured_at"], timezone.utc))}
        rate_limits = state["rate_limits"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    for name in WINDOWS:
        window = rate_limits.get(name)
        if not isinstance(window, dict) or window.get("used_percentage") is None:
            continue
        resets_at = _parse_time(window.get("resets_at"))
        if resets_at is not None and resets_at <= now:
            continue
        result[name] = {
            "used_percentage": window["used_percentage"],
            "resets_at": _iso_utc(resets_at) if resets_at else None,
        }
    return result


def status_text(statusline_input):
    parts = []
    model = (statusline_input.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    rate_limits = statusline_input.get("rate_limits") or {}
    for name in WINDOWS:
        used = (rate_limits.get(name) or {}).get("used_percentage")
        if used is not None:
            parts.append(f"{LABELS[name]} {round(used)}%")
    return " · ".join(parts)


def main():
    try:
        statusline_input = json.load(sys.stdin)
    except ValueError:
        statusline_input = {}
    if not isinstance(statusline_input, dict):
        statusline_input = {}
    try:
        capture(statusline_input, DEFAULT_PATH, datetime.now(timezone.utc))
    except OSError:
        pass
    print(status_text(statusline_input))


if __name__ == "__main__":
    main()
