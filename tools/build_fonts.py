"""Render the fonts in device/dash/fonts.py to VLW files under device/dash/vlw/."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "device"))

from dash.fonts import FONTS  # noqa: E402

from tools import vlw  # noqa: E402

SOURCE_DIR = ROOT / "fonts"
OUTPUT_DIR = ROOT / "device" / "dash" / "vlw"


def load(source, weight, size):
    font = ImageFont.truetype(str(SOURCE_DIR / source), size)
    if weight is not None:
        axes = font.get_variation_axes()
        font.set_variation_by_axes([weight if axis["name"] in ("Weight", b"Weight") else axis["default"] for axis in axes])
    return font


def render(source, weight, size, characters):
    font = load(source, weight, size)
    glyphs = []
    for character in sorted(set(characters) | {" "}):
        left, top, right, bottom = font.getbbox(character, anchor="ls")
        width, height = right - left, bottom - top
        if character == " ":
            width = height = left = top = 0
        image = Image.new("L", (width, height), 0)
        ImageDraw.Draw(image).text((-left, -top), character, font=font, fill=255, anchor="ls")
        glyphs.append(
            vlw.Glyph(ord(character), width, height, round(font.getlength(character)), -top, left, image.tobytes())
        )
    return vlw.encode(size, glyphs)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for key, spec in FONTS.items():
        data = render(*spec)
        (OUTPUT_DIR / (key + ".vlw")).write_bytes(data)
        total += len(data)
        print("%-10s %7d bytes" % (key, len(data)))
    print("total %d KB" % (total // 1024))


if __name__ == "__main__":
    main()
