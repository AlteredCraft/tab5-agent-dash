"""TNG: a starship-console look with elbow frames, block sidebars and segmented bars."""

from ..engine import Region
from ..model import money, tokens
from ..widgets import battery

NAME = "TNG"
BACKGROUND = 0x000000
ANIMATE = ("today_cost", "five_hour", "seven_day")

BLACK = 0x000000
ORANGE = 0xFF9900
PEACH = 0xFFCC99
LILAC = 0xCC99CC
BLUE = 0x9999FF
RED = 0xCC4444
DIM = 0x4A3418

SIDE = 170
BAR = 24
OUTER = 60
INNER = 30
GAP = 6
SEGMENTS = 20

# Lower sidebar blocks, in region coordinates: (top, height, colour, label). Each
# sits beside the content row it names.
BLOCKS = (
    (0, 152, ORANGE, "5 HOUR"),
    (158, 110, LILAC, "7 DAY"),
    (274, 110, BLUE, "CREDIT"),
    (390, 122, PEACH, "WEEK"),
)
ROW_TOPS = (250, 366, 482, 598)


def _upper_frame(s, m):
    """Sidebar running down from the top, turning right into the bar under the header."""
    s.rect(0, 0, SIDE, 200 - OUTER, PEACH)
    s.rect(OUTER, 200 - OUTER, SIDE - OUTER, OUTER, PEACH)
    s.arc(OUTER, 200 - OUTER, 0, OUTER, 180, 270, PEACH)
    s.rect(SIDE, 200 - BAR - INNER, INNER, INNER + BAR, PEACH)
    s.arc(SIDE + INNER, 200 - BAR - INNER, 0, INNER, 180, 270, BLACK)
    s.text("CLAUDE CODE", SIDE - 12, 20, "t_label", BLACK, 2)


def _lower_frame(s, m):
    """Sidebar blocks, the first turning right into the bar over the detail rows."""
    top, height, color, label = BLOCKS[0]
    s.arc(OUTER, OUTER, 0, OUTER, 270, 360, color)
    s.rect(OUTER, 0, SIDE - OUTER, OUTER, color)
    s.rect(0, OUTER, SIDE, height - OUTER, color)
    s.rect(SIDE, 0, INNER, BAR + INNER, color)
    s.arc(SIDE + INNER, BAR + INNER, 0, INNER, 270, 360, BLACK)
    for top, height, color, label in BLOCKS[1:]:
        s.rect(0, top, SIDE, height, color)
    for top, height, color, label in BLOCKS:
        s.text(label, SIDE - 12, top + height - 34, "t_label", BLACK, 2)


def _bar(colors):
    """A horizontal frame bar split into coloured lengths: (width, colour) pairs."""

    def draw(s, m):
        x = 0
        for i, (width, color) in enumerate(colors):
            last = i == len(colors) - 1
            s.rect(x, 0, s.w - x if last else width - GAP, BAR, color)
            x += width

    return draw


def _today(s, m):
    cost = money(m["today_cost"])
    font = "t_num110" if s.text_width(cost, "t_num110") <= 520 else "t_num60"
    s.text(cost, 0, 4, font, PEACH)


def _summary(s, m):
    s.text("AGENT USAGE", 500, 0, "t_title", ORANGE, 2)
    lines = (
        ("%s PER HOUR" % money(m["cost_per_hour"]), PEACH),
        ("%s TOKENS TODAY" % tokens(m["today_tokens"]), LILAC),
        (m["status"].upper(), BLUE),
    )
    for i, (line, color) in enumerate(lines):
        s.text(line, 500, 56 + i * 32, "t_label", color, 2)


def _filled(value):
    return 0 if value is None else int(SEGMENTS * min(max(value, 0), 100) / 100 + 0.5)


def _segments(s, filled, color):
    for i in range(SEGMENTS):
        s.rect(i * 17, 0, 14, 40, color if i < filled else DIM)


def _limit_number(field):
    def draw(s, m):
        value = m[field]
        s.text("%d%%" % round(value) if value is not None else "-", 0, 0, "t_num60", ORANGE)

    return draw, lambda m: None if m[field] is None else round(m[field])


def _limit_bar(field):
    def draw(s, m):
        value = m[field]
        _segments(s, _filled(value), RED if value is not None and value >= 90 else ORANGE)

    return draw, lambda m: (_filled(m[field]), m[field] is not None and m[field] >= 90)


def _limit_caption(field):
    def draw(s, m):
        text = m[field + "_resets"] if m[field] is not None else "not captured yet"
        s.text(text.upper(), 0, 0, "t_label", LILAC)

    return draw, lambda m: (m[field] is None, m[field + "_resets"])


def _credit_share(m):
    if m["or_remaining"] is None or not m["or_total"]:
        return None
    return 100 * m["or_remaining"] / m["or_total"]


def _credit_number(s, m):
    known = m["or_remaining"] is not None
    s.text(money(m["or_remaining"]) if known else "-", 0, 0, "t_num60", BLUE)


def _credit_bar(s, m):
    share = _credit_share(m)
    _segments(s, _filled(share), RED if share is not None and share < 10 else BLUE)


def _credit_caption(s, m):
    known = m["or_remaining"] is not None
    text = "OPENROUTER CREDIT LEFT OF %s" % money(m["or_total"]) if known else "NO OPENROUTER KEY"
    s.text(text, 0, 0, "t_label", LILAC)


def _week_number(s, m):
    s.text(money(m["week_cost"]), 0, 0, "t_num60", PEACH)


def _week_caption(s, m):
    s.text("THIS WEEK    %s IN 30 DAYS" % money(m["month_cost"]), 0, 0, "t_label", LILAC)


def _hour_heights(m):
    peak = max(m["hourly"]) or 1
    return tuple(int(110 * value / peak) for value in m["hourly"])


def _hours(s, m):
    s.text("TODAY BY HOUR", 0, 0, "t_label", ORANGE)
    base = 156
    for hour, height in enumerate(_hour_heights(m)):
        color = PEACH if hour == m["cur_hour"] else ORANGE
        s.rect(hour * 19, base - max(height, 4), 15, max(height, 4), color if height else DIM)
    for hour in (0, 6, 12, 18):
        s.text("%02d" % hour, hour * 19, base + 8, "t_label", BLUE)


def _projects(s, m):
    s.text("PROJECTS THIS WEEK", 0, 0, "t_label", ORANGE)
    for i, (name, cost) in enumerate(m["projects"][:3]):
        y = 44 + i * 44
        name = name.upper()
        while s.text_width(name, "t_label") > 330:
            name = name[:-1]
        s.rect(0, y, 28, 30, (LILAC, BLUE, PEACH)[i])
        s.text(name, 42, y + 2, "t_label", PEACH)
        s.text(money(cost), 474, y + 2, "t_label", BLUE, 2)


def _row(top, number, bar, caption):
    number_draw, number_key = number
    bar_draw, bar_key = bar
    caption_draw, caption_key = caption
    return [
        Region(216, top + 4, 200, 64, number_draw, number_key),
        Region(420, top + 14, 344, 40, bar_draw, bar_key),
        Region(216, top + 70, 548, 32, caption_draw, caption_key),
    ]


def regions():
    upper_bar = ((560, LILAC), (160, ORANGE), (260, BLUE), (100, PEACH))
    lower_bar = ((300, ORANGE), (120, PEACH), (480, LILAC), (180, BLUE))
    rows = (
        _row(ROW_TOPS[0], _limit_number("five_hour"), _limit_bar("five_hour"), _limit_caption("five_hour"))
        + _row(ROW_TOPS[1], _limit_number("seven_day"), _limit_bar("seven_day"), _limit_caption("seven_day"))
        + _row(
            ROW_TOPS[2],
            (_credit_number, lambda m: m["or_remaining"]),
            (_credit_bar, lambda m: _filled(_credit_share(m))),
            (_credit_caption, lambda m: (m["or_remaining"] is None, m["or_total"])),
        )
    )
    return [
        Region(0, 0, SIDE + INNER, 200, _upper_frame),
        Region(SIDE + INNER + GAP, 200 - BAR, 1074, BAR, _bar(upper_bar)),
        Region(216, 16, 30, 30, lambda s, m: None, bg=ORANGE),
        Region(256, 16, 300, 30, lambda s, m: s.text("SPENT TODAY", 0, 2, "t_label", ORANGE)),
        Region(216, 50, 530, 124, _today, lambda m: round(m["today_cost"] * 100)),
        Region(760, 12, 504, 156, _summary, lambda m: (m["cost_per_hour"], m["today_tokens"], m["status"])),
        Region(0, 208, SIDE + INNER, 512, _lower_frame),
        Region(SIDE + INNER + GAP, 208, 1074, BAR, _bar(lower_bar)),
    ] + rows + [
        Region(216, ROW_TOPS[3] + 4, 300, 64, _week_number, lambda m: m["week_cost"]),
        Region(216, ROW_TOPS[3] + 70, 548, 32, _week_caption, lambda m: m["month_cost"]),
        Region(790, 250, 474, 200, _hours, lambda m: (_hour_heights(m), m["cur_hour"])),
        Region(790, 470, 474, 190, _projects, lambda m: tuple(m["projects"])),
        battery(1154, 684, "t_label", BLUE),
    ]
