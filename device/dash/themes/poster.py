"""Poster: two flat colour fields and very large numerals."""

from ..engine import Region
from ..model import money, tokens
from ..widgets import battery

NAME = "Poster"
BACKGROUND = 0x14143C
ANIMATE = ("today_cost", "five_hour", "seven_day")
# A punchy pop, then a bright two-note stab.
SOUND = (
    (0, 70, 900, 140, "square", 22),
    (0, 20, 0, 0, "noise", 25),
    (90, 120, 523, 523, "triangle", 55),
    (200, 260, 784, 784, "triangle", 55),
    (200, 260, 1046, 1046, "triangle", 25),
)

INK = 0x14143C
YELLOW = 0xFFD21F
YELLOW_DARK = 0xE3B400
BLUE = 0x2D46F5
BLUE_DARK = 0x1F33C4
WHITE = 0xFFFFFF
BAR = 0x9AA2F2
BAR_EMPTY = 0x3A3A78

NUMERALS = ("p_num240", "p_num190", "p_num150")


def _fit(s, text, fonts, max_width):
    for font in fonts:
        if s.text_width(text, font) <= max_width:
            return font
    return fonts[-1]


def _claude_head(s, m):
    s.text("Claude Code", 44, 36, "p_head", INK)
    busy = "working" in m["status"]
    s.text("%s an hour right now" % money(m["cost_per_hour"]) if busy else m["status"], 756, 38, "p_mid", INK, 2)


def _claude_numeral(s, m):
    cost = money(m["today_cost"])
    font = _fit(s, cost, NUMERALS, 730)
    s.text(cost, 40, 8 + (240 - int(font[5:])) // 3, font, INK)


def _claude_caption(s, m):
    s.text("spent today, %s tokens" % tokens(m["today_tokens"]), 44, 2, "p_text", INK)


def _limit_widths(m):
    return tuple(None if m[f] is None else int(712 * min(max(m[f], 0), 100) / 100) for f in ("five_hour", "seven_day"))


def _claude_limits(s, m):
    rows = (("five_hour", "5-hour limit"), ("seven_day", "7-day limit"))
    for i, (field, title) in enumerate(rows):
        y = 10 + i * 64
        value = m[field]
        s.rect(44, y, 712, 52, YELLOW_DARK)
        if value is None:
            s.text(title + " not captured yet", 60, y + 15, "p_bold", INK)
            continue
        label = "%s %d%%" % (title, round(value))
        fill = _limit_widths(m)[i]
        s.rect(44, y, fill, 52, INK)
        inside = fill >= s.text_width(label, "p_bold") + 32
        s.text(label, 60 if inside else fill + 60, y + 15, "p_bold", YELLOW if inside else INK)
        if inside:
            resets = m[field + "_resets"]
            covered = fill > 712 - s.text_width(resets, "p_bold") - 32
            s.text(resets, 740, y + 15, "p_bold", YELLOW if covered else INK, 2)


def _openrouter_head(s, m):
    s.text("OpenRouter", 36, 36, "p_head", WHITE)


def _openrouter_numeral(s, m):
    if m["or_remaining"] is None:
        s.text("no key configured", 36, 80, "p_text", WHITE)
        return
    credit = money(m["or_remaining"])
    font = _fit(s, credit, NUMERALS[1:], 420)
    s.text(credit, 34, 16 + (190 - int(font[5:])) // 3, font, WHITE)


def _openrouter_rest(s, m):
    if m["or_remaining"] is None:
        return
    s.text("credit left of %s" % money(m["or_total"]), 36, 0, "p_text", WHITE)
    share = m["or_used"] / m["or_total"] if m["or_total"] else 0
    s.rect(36, 104, 400, 52, BLUE_DARK)
    s.rect(36, 104, int(400 * min(share, 1)), 52, WHITE)
    s.text("%d%% used" % round(100 * share), 52, 119, "p_bold", BLUE)
    if m["or_key_usage"] is not None:
        s.text("%s spent on this key" % money(m["or_key_usage"]), 36, 182, "p_mid", WHITE)


def _month_heights(m):
    peak = max(m["daily"]) or 1
    return tuple(int(84 * value / peak) for value in m["daily"])


def _month(s, m):
    s.text("Last 30 days", 44, 22, "p_bold", WHITE)
    s.text(money(m["month_cost"]), 1236, 22, "p_bold", WHITE, 2)
    heights = _month_heights(m)
    for i, height in enumerate(heights):
        color = YELLOW if i == len(heights) - 1 else BAR if height else BAR_EMPTY
        s.rect(44 + i * 1192 // 30, 148 - max(height, 3), 30, max(height, 3), color)


def regions():
    return [
        Region(0, 0, 800, 84, _claude_head, lambda m: (m["status"], m["cost_per_hour"]), bg=YELLOW),
        Region(0, 84, 800, 262, _claude_numeral, lambda m: round(m["today_cost"] * 100), bg=YELLOW),
        Region(0, 346, 800, 48, _claude_caption, lambda m: m["today_tokens"], bg=YELLOW),
        Region(
            0,
            394,
            800,
            154,
            _claude_limits,
            lambda m: (_limit_widths(m), m["five_hour_resets"], m["seven_day_resets"]),
            bg=YELLOW,
        ),
        Region(800, 0, 480, 84, _openrouter_head, bg=BLUE),
        Region(800, 84, 480, 216, _openrouter_numeral, lambda m: m["or_remaining"], bg=BLUE),
        Region(800, 300, 480, 248, _openrouter_rest, lambda m: (m["or_remaining"], m["or_total"], m["or_used"], m["or_key_usage"]), bg=BLUE),
        Region(0, 548, 1280, 172, _month, lambda m: (_month_heights(m), m["month_cost"]), bg=INK),
        battery(1136, 6, "p_mid", WHITE, bg=BLUE),
    ]
