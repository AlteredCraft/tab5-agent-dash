"""Font registry shared by the device and the Mac-side tools.

Each key names one pre-rendered font file (vlw/<key>.vlw; the directory
cannot be called fonts, or it would shadow this module on the device). The Mac builds
them with tools/build_fonts.py from: source file, weight (None for a static
font), pixel size, and the characters to include. The space character is always added.
"""

TEXT = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$%.,:-+'"
NUM = "0123456789$.,%-"

FONTS = {
    # Gauge glass
    "g_title": ("BarlowSemiCondensed-SemiBold.ttf", None, 30, TEXT),
    "g_label": ("BarlowSemiCondensed-SemiBold.ttf", None, 22, TEXT),
    "g_text": ("BarlowSemiCondensed-Regular.ttf", None, 22, TEXT),
    "g_small": ("BarlowSemiCondensed-Regular.ttf", None, 18, TEXT),
    "g_value": ("BarlowSemiCondensed-Medium.ttf", None, 24, TEXT),
    "g_num44": ("BarlowCondensed-SemiBold.ttf", None, 44, NUM),
    "g_num60": ("BarlowCondensed-SemiBold.ttf", None, 60, NUM),
    "g_num132": ("BarlowCondensed-SemiBold.ttf", None, 132, NUM),
    # Day dial
    "d_text": ("Figtree.ttf", 400, 20, TEXT),
    "d_bold": ("Figtree.ttf", 600, 20, TEXT),
    "d_row": ("Figtree.ttf", 400, 22, TEXT),
    "d_small": ("Figtree.ttf", 400, 18, TEXT),
    "d_rate": ("Unbounded.ttf", 700, 30, TEXT),
    "d_num40": ("Unbounded.ttf", 700, 40, NUM),
    "d_num60": ("Unbounded.ttf", 700, 60, NUM),
    # Poster
    "p_head": ("Archivo.ttf", 700, 28, TEXT),
    "p_text": ("Archivo.ttf", 500, 28, TEXT),
    "p_mid": ("Archivo.ttf", 500, 24, TEXT),
    "p_bold": ("Archivo.ttf", 700, 26, TEXT),
    "p_num150": ("BigShouldersDisplay.ttf", 800, 150, NUM),
    "p_num190": ("BigShouldersDisplay.ttf", 800, 95, NUM),
    "p_num240": ("BigShouldersDisplay.ttf", 800, 120, NUM),
}

# The Tab5 restarts when asked to draw glyphs much taller than 150 px, so
# larger sizes are stored at half size and drawn doubled.
SCALE = {"p_num190": 2, "p_num240": 2}

DEVICE_DIR = "/flash/dash/vlw"


def device_path(key):
    return DEVICE_DIR + "/" + key + ".vlw"
