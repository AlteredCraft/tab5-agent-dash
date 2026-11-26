"""Device main loop: Wi-Fi, polling the collector, touch, and the engine."""

import json
import socket
import time

import M5
import network
import requests

from . import model
from .engine import Engine
from .lcd_surface import LcdScreen
from .themes import THEMES

CONFIG_PATH = "/flash/dash/config.json"
THEME_PATH = "/flash/dash/theme.txt"
POLL_MS = 5000
RETRY_MS = 15000
FETCH_TIMEOUT_S = 3


def _saved_theme():
    try:
        with open(THEME_PATH) as f:
            return int(f.read()) % len(THEMES)
    except (OSError, ValueError):
        return 0


def _save_theme(index):
    with open(THEME_PATH, "w") as f:
        f.write(str(index))


def _resolved(url):
    """Replace the host with its address. A .local name takes about 2 s to
    look up on the device, so it is done once rather than on every poll."""
    scheme, rest = url.split("://", 1)
    hostport, _, path = rest.partition("/")
    host, _, port = hostport.partition(":")
    port = int(port or 80)
    try:
        address = socket.getaddrinfo(host, port)[0][-1][0]
    except Exception:
        return None
    return "%s://%s:%d/%s" % (scheme, address, port, path)


def _battery():
    """Charge percentage while running on the battery, None on external power."""
    power = M5.Power
    return None if power.isCharging() else power.getBatteryLevel()


def _fetch(url):
    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT_S)
        try:
            return response.json() if response.status_code == 200 else None
        finally:
            response.close()
    except Exception:
        return None


def run():
    M5.begin()
    lcd = M5.Lcd
    lcd.setRotation(1)
    width = lcd.width()

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config["wifi_ssid"], config["wifi_password"])

    # ticks_ms wraps, so keep a clock that only grows.
    clock = 0
    last_ticks = time.ticks_ms()

    index = _saved_theme()
    engine = Engine(LcdScreen(lcd))
    engine.set_theme(THEMES[index], clock)
    engine.set_model(model.build(None, battery=_battery()), clock)

    payload = None
    target = None
    last_ok = None
    next_poll = 0
    touching = False

    while True:
        M5.update()
        ticks = time.ticks_ms()
        clock += time.ticks_diff(ticks, last_ticks)
        last_ticks = ticks

        touched = M5.Touch.getCount() > 0
        if touched and not touching:
            x = M5.Touch.getX()
            step = 1 if x > width * 2 // 3 else -1 if x < width // 3 else 0
            if step:
                index = (index + step) % len(THEMES)
                engine.set_theme(THEMES[index], clock)
                _save_theme(index)
        touching = touched

        if clock >= next_poll:
            fresh = None
            if wlan.isconnected():
                target = target or _resolved(config["url"])
                fresh = _fetch(target) if target else None
            if fresh:
                payload = fresh
                last_ok = clock
            else:
                target = None
            next_poll = clock + (POLL_MS if fresh else RETRY_MS)
            stale_min = 0 if last_ok is None else (clock - last_ok) // 60000
            engine.set_model(model.build(payload, stale_min, _battery()), clock)

        animating = engine.frame(clock)
        time.sleep_ms(5 if animating else 40)
