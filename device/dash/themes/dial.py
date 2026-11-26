"""Day dial: a 24-hour clock face with each hour's spend as a radial bar."""

from math import cos, radians, sin

from ..engine import Region
from ..model import money, thousands, tokens

NAME = "Day dial"
BACKGROUND = 0x1B1530
ANIMATE = ("today_cost",)

TRACK = 0x2E2550
ORANGE = 0xFF9F45
HOT = 0xFFD08A
PINK = 0xFF5D8F
MINT = 0x6EE7C5
TEXT = 0xF3EEFF
MUTED = 0x9D93BF

C = 330
BAR_R0 = 150
BAR_MAX = 108


def _bar_lengths(m):
    peak = max(m["hourly"]) or 1
    return tuple(int(BAR_MAX * value / peak) for value in m["hourly"])


def _ring_degrees(value):
    return 0 if value is None else int(3.6 * min(max(value, 0), 100))


def _hand_degrees(m):
    return int(m["now_hour"] * 15)


def _dial(s, m):
    for hour, length in enumerate(_bar_lengths(m)):
        a0, a1 = hour * 15 + 2, hour * 15 + 13
        s.arc(C, C, BAR_R0, BAR_R0 + 8, a0, a1, TRACK)
        if length:
            s.arc(C, C, BAR_R0, BAR_R0 + 8 + length, a0, a1, HOT if hour == m["cur_hour"] else ORANGE)
    for r0, field, color in ((292, "five_hour", PINK), (314, "seven_day", MINT)):
        s.arc(C, C, r0, r0 + 14, 0, 360, TRACK)
        s.arc(C, C, r0, r0 + 14, 0, _ring_degrees(m[field]), color)
    hand = _hand_degrees(m)
    s.arc(C, C, 136, 284, hand, hand + 1, TEXT)
    for hour in (0, 6, 12, 18):
        angle = radians(hour * 15 - 90)
        s.text(str(hour), C + 122 * cos(angle), C + 122 * sin(angle) - 7, "d_small", MUTED, 1)


def _center_number(s, m):
    cost = money(m["today_cost"])
    font = "d_num40" if s.text_width(cost, "d_num40") <= 206 else "d_rate"
    s.text(cost, 105, 6, font, TEXT, 1)


def _center_caption(s, m):
    s.text("today in Claude Code", 105, 4, "d_small", MUTED, 1)
    s.text("%s tokens" % tokens(m["today_tokens"]), 105, 30, "d_small", MUTED, 1)


def _limits(s, m):
    for x, field, title, color in ((10, "five_hour", "5-hour limit", PINK), (280, "seven_day", "7-day limit", MINT)):
        value = m[field]
        s.rect(x, 12, 8, 108, color)
        s.text("%d%%" % round(value) if value is not None else "-", x + 26, 12, "d_num60", color)
        s.text(title, x + 26, 72, "d_bold", TEXT)
        s.text(m[field + "_resets"] if value is not None else "not captured yet", x + 26, 100, "d_small", MUTED)


def _now(s, m):
    s.text("Right now", 10, 8, "d_text", MUTED)
    s.text(m["status"], 510, 8, "d_text", MUTED, 2)
    rate = "%s an hour" % money(m["cost_per_hour"])
    pace = "%s tokens a minute" % thousands(m["tokens_per_min"])
    s.text(rate, 10, 44, "d_rate", ORANGE)
    if s.text_width(rate, "d_rate") + s.text_width(pace, "d_text") <= 480:
        s.text(pace, 510, 52, "d_text", TEXT, 2)


def _week(s, m):
    s.text("This week", 10, 8, "d_text", MUTED)
    s.text(money(m["week_cost"]), 510, 8, "d_text", TEXT, 2)
    top = m["projects"][0][1] if m["projects"] else 0
    for i, (name, cost) in enumerate(m["projects"][:3]):
        y = 48 + i * 38
        while s.text_width(name, "d_row") > 236:
            name = name[:-1]
        s.text(name, 10, y, "d_row", TEXT)
        s.rect(260, y + 2, 150, 16, TRACK)
        s.rect(260, y + 2, max(4, int(150 * cost / top)) if top else 4, 16, ORANGE)
        s.text(money(cost), 510, y, "d_row", TEXT, 2)


def _openrouter(s, m):
    s.arc(80, 86, 52, 70, 0, 360, TRACK)
    if m["or_remaining"] is None:
        s.text("OpenRouter credit", 180, 22, "d_text", MUTED)
        s.text("no key configured", 180, 54, "d_row", TEXT)
        return
    share = m["or_remaining"] / m["or_total"] if m["or_total"] else 0
    s.arc(80, 86, 52, 70, 0, int(360 * share), MINT)
    s.text("%d%%" % round(100 * share), 80, 78, "d_bold", TEXT, 1)
    s.text("OpenRouter credit", 180, 22, "d_text", MUTED)
    s.text(money(m["or_remaining"]), 180, 52, "d_num40", TEXT)
    s.text("left of %s" % money(m["or_total"]), 180, 102, "d_text", MUTED)
    if m["or_key_usage"] is not None:
        s.text("%s spent on this key" % money(m["or_key_usage"]), 180, 130, "d_text", MUTED)


def regions():
    rule = lambda s, m: None
    return [
        Region(
            20,
            30,
            660,
            660,
            _dial,
            lambda m: (_bar_lengths(m), m["cur_hour"], _hand_degrees(m), _ring_degrees(m["five_hour"]), _ring_degrees(m["seven_day"])),
        ),
        Region(245, 308, 210, 52, _center_number, lambda m: round(m["today_cost"] * 100)),
        Region(245, 360, 210, 54, _center_caption, lambda m: m["today_tokens"]),
        Region(
            730,
            44,
            520,
            130,
            _limits,
            lambda m: tuple((None if m[f] is None else round(m[f]), m[f + "_resets"]) for f in ("five_hour", "seven_day")),
        ),
        Region(740, 196, 500, 2, rule, bg=TRACK),
        Region(730, 208, 520, 100, _now, lambda m: (m["status"], m["cost_per_hour"], m["tokens_per_min"])),
        Region(740, 320, 500, 2, rule, bg=TRACK),
        Region(730, 330, 520, 170, _week, lambda m: (m["week_cost"], tuple(m["projects"]))),
        Region(740, 512, 500, 2, rule, bg=TRACK),
        Region(730, 524, 520, 172, _openrouter, lambda m: (m["or_remaining"], m["or_total"], m["or_key_usage"])),
    ]
