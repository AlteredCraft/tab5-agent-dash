"""The settings screen: speaker volume and mute.

It is drawn by the engine like a theme (NAME, BACKGROUND, ANIMATE, regions()), from a
model built by view(). BUTTONS holds the touch targets in screen coordinates, and
load() and save() keep the values across restarts.
"""

import json

from .engine import Region
from .widgets import battery

NAME = "Settings"
BACKGROUND = 0x101418
ANIMATE = ()

PANEL = 0x1F2730
ACCENT = 0x4FC3F7
INK = 0x101418
TEXT = 0xEEF2F5
MUTED = 0x8A97A3
DIM = 0x2E3A45

STEP = 10
SEGMENTS = 100 // STEP
DEFAULTS = {"volume": 50, "muted": False}

# name: (x, y, w, h) on screen.
BUTTONS = {
    "down": (60, 210, 140, 140),
    "up": (1080, 210, 140, 140),
    "mute": (60, 480, 520, 120),
    "done": (700, 480, 520, 120),
}
# Touches this far outside a button still count, since fingers are wide.
SLOP = 12


def load(path):
    values = dict(DEFAULTS)
    try:
        with open(path) as f:
            saved = json.load(f)
        volume = int(saved.get("volume", values["volume"]))
        values["volume"] = max(0, min(100, volume - volume % STEP))
        values["muted"] = bool(saved.get("muted", values["muted"]))
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return values


def save(path, values):
    with open(path, "w") as f:
        json.dump({"volume": values["volume"], "muted": values["muted"]}, f)


def adjust(values, button):
    """The values after a press of button ("down", "up" or "mute")."""
    values = dict(values)
    if button == "down":
        values["volume"] = max(0, values["volume"] - STEP)
    elif button == "up":
        values["volume"] = min(100, values["volume"] + STEP)
    elif button == "mute":
        values["muted"] = not values["muted"]
    return values


def audible(values):
    return not values["muted"] and values["volume"] > 0


def speaker_volume(values):
    """The volume for M5.Speaker.setVolume, 0-255."""
    return 0 if values["muted"] else values["volume"] * 255 // 100


def hit(x, y):
    """The name of the button at a screen point, or None."""
    for name, (bx, by, bw, bh) in BUTTONS.items():
        if bx - SLOP <= x < bx + bw + SLOP and by - SLOP <= y < by + bh + SLOP:
            return name
    return None


def view(values, battery_level=None):
    return {"volume": values["volume"], "muted": values["muted"], "battery": battery_level}


def _button(name, draw, key=None):
    x, y, w, h = BUTTONS[name]
    return Region(x, y, w, h, draw, key)


def _plus_minus(plus):
    def draw(s, m):
        enabled = m["volume"] < 100 if plus else m["volume"] > 0
        s.rect(0, 0, s.w, s.h, PANEL)
        color = TEXT if enabled else DIM
        s.rect(s.w // 2 - 32, s.h // 2 - 5, 64, 10, color)
        if plus:
            s.rect(s.w // 2 - 5, s.h // 2 - 32, 10, 64, color)

    return draw, lambda m: m["volume"] in (0, 100)


def _bar(s, m):
    gap = 10
    width = (s.w - gap * (SEGMENTS - 1)) // SEGMENTS
    lit = m["volume"] // STEP
    for i in range(SEGMENTS):
        on = i < lit
        color = (MUTED if m["muted"] else ACCENT) if on else PANEL
        s.rect(i * (width + gap), 20, width, s.h - 40, color)


def _level(s, m):
    if m["muted"]:
        text = "Muted"
    elif m["volume"] == 0:
        text = "Off"
    else:
        text = "%d%%" % m["volume"]
    s.text(text, s.w // 2, 4, "s_button", MUTED if m["muted"] else TEXT, 1)


def _mute(s, m):
    muted = m["muted"]
    s.rect(0, 0, s.w, s.h, ACCENT if muted else PANEL)
    s.text("Unmute" if muted else "Mute", s.w // 2, s.h // 2 - 22, "s_button", INK if muted else TEXT, 1)


def _done(s, m):
    s.rect(0, 0, s.w, s.h, PANEL)
    s.rect(0, s.h - 6, s.w, 6, ACCENT)
    s.text("Done", s.w // 2, s.h // 2 - 22, "s_button", TEXT, 1)


def regions():
    down, down_key = _plus_minus(False)
    up, up_key = _plus_minus(True)
    return [
        Region(60, 40, 1000, 70, lambda s, m: s.text("Settings", 0, 6, "s_title", TEXT)),
        battery(1140, 58, "g_text", MUTED),
        Region(60, 150, 600, 40, lambda s, m: s.text("Sound", 0, 6, "g_label", MUTED)),
        _button("down", down, down_key),
        Region(230, 210, 820, 140, _bar, lambda m: (m["volume"], m["muted"])),
        _button("up", up, up_key),
        Region(230, 360, 820, 60, _level, lambda m: (m["volume"], m["muted"])),
        _button("mute", _mute, lambda m: m["muted"]),
        _button("done", _done),
        Region(
            60, 650, 1160, 40,
            lambda s, m: s.text("Double-tap the middle of the dashboard to open settings. Tap Done to return.", 0, 8, "g_small", MUTED),
        ),
    ]
