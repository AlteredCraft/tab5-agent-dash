"""Render every theme to PNG, and its selection sound to WAV, using the same code the device runs.

    uv run python -m tools.preview                     # sample data, into previews/
    uv run python -m tools.preview --url http://127.0.0.1:8787/usage.json
    uv run python -m tools.preview --out docs/img --regions --battery 72   # images for the guide
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "device"))

from dash import model, settings, sound  # noqa: E402
from dash.engine import EASE_MS, Engine  # noqa: E402
from dash.themes import THEMES  # noqa: E402

from PIL import ImageDraw  # noqa: E402

from tools.host_surface import HostScreen  # noqa: E402


def sample_payload():
    hourly_cost = [0, 0, 0, 0, 0, 0, 0.4, 3.1, 5.2, 2.2, 6.8, 4.1, 0.6, 2.9, 7.4, 5.5]
    daily = [0, 0, 3.2, 0, 6.4, 0, 9.8, 14.1, 11.5, 0, 41.3, 30.2, 4.6, 0, 0, 2.1, 5.3, 0, 8.9, 0, 1.4, 6.2, 0, 0, 12.7, 55.4, 0, 3.8, 0, 38.2]
    return {
        "generated_at": "2026-11-26T23:40:00Z",
        "claude_code": {
            "today": {"cost_usd": 38.2, "total": 31_400_000, "output": 212_000},
            "last_7d": {"cost_usd": 113.31},
            "last_30d": {"cost_usd": 255.10},
            "daily": [{"date": "", "cost_usd": cost} for cost in daily],
            "hourly": [
                {"start": "2026-11-25T%02d:00:00-08:00" % h, "cost_usd": 0.0} for h in range(16, 24)
            ]
            + [{"start": "2026-11-26T%02d:00:00-08:00" % h, "cost_usd": c} for h, c in enumerate(hourly_cost)],
            "by_model_7d": [{"name": "claude-fable-5-2", "cost_usd": 76.27}, {"name": "claude-opus-5-5", "cost_usd": 5.03}],
            "by_project_7d": [
                {"name": "storefront-api", "cost_usd": 62.56},
                {"name": "research_notes", "cost_usd": 9.27},
                {"name": "tab5-agent-dash", "cost_usd": 3.44},
            ],
            "burn": {"output_tokens_per_min": 2340, "cost_per_hour": 5.5},
            "active_sessions": 1,
            "limits": {
                "five_hour": {"used_percentage": 62, "resets_at": "2026-11-27T01:28:00Z"},
                "seven_day": {"used_percentage": 34, "resets_at": "2026-11-30T02:00:00Z"},
            },
        },
        "openrouter": {
            "credits": {"total": 60, "used": 45.39, "remaining": 14.61},
            "key": {"usage": 0.2, "limit": 50},
        },
    }


def render(theme, view, at=EASE_MS):
    """Return (image, overflow notes) for one theme, `at` ms into its entry animation."""
    screen = HostScreen()
    engine = Engine(screen)
    engine.set_theme(theme, 0)
    engine.set_model(view, 0)
    engine.frame(at)
    overflow = [note for canvas in screen.canvases for note in canvas.overflow]
    return screen.image, overflow


def outline_regions(theme, image):
    """Mark each of a theme's regions on a copy of its rendering."""
    marked = image.copy()
    draw = ImageDraw.Draw(marked)
    for region in theme.regions():
        box = (region.x, region.y, region.x + region.w - 1, region.y + region.h - 1)
        draw.rectangle(box, outline=(255, 255, 255), width=3)
        draw.rectangle(box, outline=(255, 60, 120), width=1)
    return marked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="collector URL to render live data from")
    parser.add_argument("--out", type=Path, default=ROOT / "previews")
    parser.add_argument("--regions", action="store_true", help="also save <theme>-regions.png with region outlines")
    parser.add_argument("--battery", type=int, help="draw the on-battery indicator at this charge percentage")
    parser.add_argument("--no-sound", action="store_true", help="skip writing <theme>.wav")
    args = parser.parse_args()
    if args.url:
        with urllib.request.urlopen(args.url, timeout=10) as response:
            payload = json.loads(response.read())
    else:
        payload = sample_payload()
    args.out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        image, overflow = render(theme, model.build(payload, battery=args.battery))
        path = args.out / (theme.__name__.split(".")[-1] + ".png")
        image.save(path)
        if args.regions:
            outline_regions(theme, image).save(path.with_name(path.stem + "-regions.png"))
        print(path, *overflow, sep="\n  ")
        if not args.no_sound:
            path.with_suffix(".wav").write_bytes(sound.wav(theme.SOUND))
    image, overflow = render(settings, settings.view(settings.DEFAULTS, args.battery))
    path = args.out / "settings.png"
    image.save(path)
    print(path, *overflow, sep="\n  ")


if __name__ == "__main__":
    main()
