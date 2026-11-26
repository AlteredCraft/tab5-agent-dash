"""Gauge glass: limits and credit as liquid levels in measuring tubes."""

from ..engine import Region
from ..model import money, tokens
from ..widgets import battery

NAME = "Gauge glass"
BACKGROUND = 0xE6EBEA
ANIMATE = ("five_hour", "seven_day", "or_remaining", "today_cost")

INK = 0x14213D
COBALT = 0x1F4FD8
AMBER = 0xF2A20C
RED = 0xD63A2F
GLASS = 0xF7FAF9
TICK = 0x8C9AA1
MUTED = 0x5C6B73

TUBE_W = 104
TUBE_H = 430


def _tube(s, level, color):
    x, y = 8, 8
    s.rect(x, y, TUBE_W, TUBE_H, GLASS)
    if level is not None:
        fill = int(TUBE_H * min(max(level, 0), 100) / 100)
        s.rect(x, y + TUBE_H - fill, TUBE_W, fill, color)
        s.rect(x, y + TUBE_H - fill, TUBE_W, 5, INK)
    for edge in ((x, y, TUBE_W, 4), (x, y + TUBE_H - 4, TUBE_W, 4), (x, y, 4, TUBE_H), (x + TUBE_W - 4, y, 4, TUBE_H)):
        s.rect(edge[0], edge[1], edge[2], edge[3], INK)
    for i in range(11):
        ty = y + TUBE_H - TUBE_H * i // 10
        major = i % 5 == 0
        s.rect(x + TUBE_W + 8, ty - 1, 22 if major else 12, 2, INK if major else TICK)
        if major:
            s.text(str(i * 10), x + TUBE_W + 36, ty - 7 if i else ty - 13, "g_small", MUTED)


def _level_key(value):
    return None if value is None else int(TUBE_H * value / 100)


def _limit_tube(field):
    def draw(s, m):
        level = m[field]
        _tube(s, level, RED if level is not None and level >= 90 else COBALT)

    return draw, lambda m: _level_key(m[field])


def _limit_number(field):
    def draw(s, m):
        level = m[field]
        s.text("%d%%" % round(level) if level is not None else "-", 8, 4, "g_num60", INK)

    return draw, lambda m: None if m[field] is None else round(m[field])


def _limit_caption(field, title):
    def draw(s, m):
        s.text(title, 8, 4, "g_label", INK)
        s.text(m[field + "_resets"] if m[field] is not None else "not captured yet", 8, 36, "g_small", MUTED)

    return draw, lambda m: (m[field] is None, m[field + "_resets"])


def _credit_level(m):
    if m["or_remaining"] is None or not m["or_total"]:
        return None
    return 100 * m["or_remaining"] / m["or_total"]


def _credit_tube(s, m):
    level = _credit_level(m)
    _tube(s, level, RED if level is not None and level < 10 else AMBER)


def _credit_number(s, m):
    s.text(money(m["or_remaining"]) if m["or_remaining"] is not None else "-", 8, 4, "g_num60", INK)


def _credit_caption(s, m):
    known = m["or_remaining"] is not None
    s.text("Credit left", 8, 4, "g_label", INK)
    s.text("of %s bought" % money(m["or_total"]) if known else "no OpenRouter key", 8, 36, "g_small", MUTED)


def _credit_side(s, m):
    rows = (
        ("This key", m["or_key_usage"], "of a %s cap" % money(m["or_key_limit"]) if m["or_key_limit"] else "no cap"),
        ("All keys", m["or_used"], "spent so far"),
    )
    for i, (title, value, note) in enumerate(rows):
        y = i * 140
        s.text(title, 0, y, "g_text", MUTED)
        amount = money(value) if value is not None else "-"
        s.text(amount, 0, y + 30, "g_num44" if s.text_width(amount, "g_num44") <= 170 else "g_title", INK)
        s.text(note, 0, y + 78, "g_small", MUTED)


def _header(s, m):
    s.text("Claude Code", 8, 8, "g_title", INK)
    width = s.text_width(m["status"], "g_text")
    s.rect(832 - width - 24, 14, 14, 14, COBALT if "working" in m["status"] else TICK)
    s.text(m["status"], 832, 10, "g_text", MUTED, 2)


def _today_number(s, m):
    cost = money(m["today_cost"])
    font = "g_num132" if s.text_width(cost, "g_num132") <= 404 else "g_num60"
    s.text(cost, 8, 4, font, INK)


def _today_detail(s, m):
    s.text("%s tokens, %s written" % (tokens(m["today_tokens"]), tokens(m["today_written"])), 8, 4, "g_value", INK)
    s.text("%s an hour right now" % money(m["cost_per_hour"]), 8, 40, "g_label", COBALT)


def _hour_heights(m):
    peak = max(m["hourly"]) or 1
    return tuple(int(104 * value / peak) for value in m["hourly"])


def _hours(s, m):
    base = 112
    for hour, height in enumerate(_hour_heights(m)):
        color = COBALT if hour == m["cur_hour"] else INK
        s.rect(8 + hour * 17, base - max(height, 2), 13, max(height, 2), color if height else TICK)
    s.rect(8, base + 4, 24 * 17 - 4, 2, INK)
    for hour in (0, 6, 12, 18):
        s.text("%d:00" % hour, 8 + hour * 17, base + 14, "g_small", MUTED)


def _models(s, m):
    s.text("This week by model", 8, 4, "g_text", MUTED)
    top = m["models"][0][1] if m["models"] else 0
    for i, (name, cost) in enumerate(m["models"][:2]):
        y = 44 + i * 44
        longest = 420 - 130 - 10 - s.text_width(money(cost), "g_value")
        width = max(6, int(min(190, longest) * cost / top)) if top else 6
        s.text(name, 8, y, "g_value", INK)
        s.rect(130, y, width, 20, COBALT if i == 0 else INK)
        s.text(money(cost), 130 + width + 10, y, "g_value", INK)


def regions():
    five_tube, five_tube_key = _limit_tube("five_hour")
    five_number, five_number_key = _limit_number("five_hour")
    five_caption, five_caption_key = _limit_caption("five_hour", "5-hour limit")
    seven_tube, seven_tube_key = _limit_tube("seven_day")
    seven_number, seven_number_key = _limit_number("seven_day")
    seven_caption, seven_caption_key = _limit_caption("seven_day", "7-day limit")
    return [
        Region(40, 26, 840, 52, _header, lambda m: m["status"]),
        Region(40, 96, 190, 446, five_tube, five_tube_key),
        Region(40, 550, 200, 62, five_number, five_number_key),
        Region(40, 614, 200, 70, five_caption, five_caption_key),
        Region(242, 96, 190, 446, seven_tube, seven_tube_key),
        Region(242, 550, 210, 62, seven_number, seven_number_key),
        Region(242, 614, 210, 70, seven_caption, seven_caption_key),
        Region(460, 96, 420, 32, lambda s, m: s.text("Today", 8, 4, "g_text", MUTED)),
        Region(460, 128, 420, 124, _today_number, lambda m: round(m["today_cost"] * 100)),
        Region(460, 252, 420, 74, _today_detail, lambda m: (m["today_tokens"], m["today_written"], m["cost_per_hour"])),
        Region(460, 352, 420, 150, _hours, lambda m: (_hour_heights(m), m["cur_hour"])),
        Region(460, 528, 420, 150, _models, lambda m: tuple(m["models"])),
        Region(899, 36, 2, 648, lambda s, m: None, bg=TICK),
        Region(926, 26, 330, 52, lambda s, m: s.text("OpenRouter", 8, 8, "g_title", INK)),
        Region(926, 96, 176, 446, _credit_tube, lambda m: _level_key(_credit_level(m))),
        Region(926, 550, 330, 62, _credit_number, lambda m: m["or_remaining"] and round(m["or_remaining"] * 100)),
        Region(926, 614, 330, 70, _credit_caption, lambda m: (m["or_remaining"] is None, m["or_total"])),
        Region(1110, 290, 170, 250, _credit_side, lambda m: (m["or_key_usage"], m["or_key_limit"], m["or_used"])),
        battery(1160, 2, "g_small", MUTED),
    ]
