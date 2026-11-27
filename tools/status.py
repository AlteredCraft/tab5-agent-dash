"""Report whether the pieces are up: the collector, its data sources, and the Tab5."""

import argparse
import json
import urllib.request
from datetime import datetime, timezone

from serial.tools.list_ports import comports

ESPRESSIF_VID = 0x303A


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def age(iso, now):
    seconds = (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    if seconds < 90:
        return "%d s ago" % seconds
    if seconds < 5400:
        return "%d min ago" % (seconds // 60)
    return "%d h ago" % (seconds // 3600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    base = "http://127.0.0.1:%d" % args.port
    now = datetime.now(timezone.utc)

    def line(name, text):
        print("  %-12s %s" % (name, text))

    usage = clients = None
    try:
        usage = get(base + "/usage.json")
        clients = get(base + "/status.json")["seconds_since_request"]
    except OSError:
        if usage is None:
            line("Collector", "not running. Start it with `make serve`.")

    if usage:
        claude = usage["claude_code"]
        outdated = clients is None
        line("Collector", "running on port %d%s" % (
            args.port, " (an older version: `make stop`, then `make serve`)" if outdated else ""))
        line("Claude Code", "$%.2f today, last activity %s" % (
            claude["today"]["cost_usd"],
            age(claude["last_activity_at"], now) if claude["last_activity_at"] else "never",
        ))
        limits = claude["limits"]
        if limits:
            windows = ["%s %d%%" % (label, limits[key]["used_percentage"])
                       for key, label in (("five_hour", "5-hour"), ("seven_day", "7-day")) if key in limits]
            line("Limits", "%s, reported %s" % (", ".join(windows) or "none current", age(limits["captured_at"], now)))
        else:
            line("Limits", "not captured. Add the status line command (see the README).")
        openrouter = usage["openrouter"]
        if not openrouter:
            line("OpenRouter", "no key given. Pass ENV=... to `make serve`.")
        elif openrouter.get("error") or openrouter.get("errors"):
            line("OpenRouter", "error: %s" % (openrouter.get("error") or "; ".join(openrouter["errors"])))
        else:
            line("OpenRouter", "$%.2f credit left" % openrouter["credits"]["remaining"])
        remote = {address: seconds for address, seconds in (clients or {}).items() if not address.startswith("127.")}
        if outdated:
            line("Tab5 Wi-Fi", "unknown until the collector is restarted")
        elif remote:
            address, seconds = min(remote.items(), key=lambda item: item[1])
            state = "polling" if seconds < 30 else "silent"
            line("Tab5 Wi-Fi", "%s: %s last asked %d s ago" % (state, address, seconds))
        else:
            line("Tab5 Wi-Fi", "no device has asked this collector yet")

    ports = [port.device for port in comports() if port.vid == ESPRESSIF_VID]
    line("Tab5 USB", ports[0] if ports else "not connected")


if __name__ == "__main__":
    main()
