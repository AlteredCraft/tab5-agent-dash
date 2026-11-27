"""Requests the collector passes to the device: restart or power off.

They exist because the Tab5's USB console can stop answering while the
dashboard keeps running, and then Wi-Fi is the only way to reach it. Each
request is the time it was made. The device acts only when a value rises
above the one it saw first, so an old request never fires again after a
restart, and a restarted collector (values back to 0) triggers nothing.
"""

ACTIONS = ("off", "restart")


def action(seen, current):
    """Return "off", "restart" or None, comparing a payload's control block with the first one seen."""
    for name in ACTIONS:
        if (current.get(name) or 0) > (seen.get(name) or 0):
            return name
    return None
