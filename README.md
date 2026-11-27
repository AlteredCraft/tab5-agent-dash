# tab5-agent-dash

Agent token usage dashboard for the M5Stack Tab5, covering Claude Code and OpenRouter.

A collector on the Mac serves one JSON document. The Tab5 (MicroPython on UIFlow2) polls it and draws the dashboard.

## Collector

`make` lists every task; the Makefile header documents the variables.

```sh
make test
make serve ENV=path/to/openrouter.env   # serves http://0.0.0.0:8787/usage.json
make once ENV=path/to/openrouter.env    # print the payload and exit
```

The server has no authentication: anyone on the same network can read the usage figures and project names. Pass `HOST=127.0.0.1` to keep it local.

Sources:

- **Claude Code tokens and cost**: session transcripts under `~/.claude/projects`. Costs are estimates at API rates (`collector/pricing.py`), not subscription charges.
- **Claude Code limits** (5-hour and 7-day percentages): Claude Code only gives these to its status line command, so `collector/limits.py` doubles as one. Enable it in `~/.claude/settings.json`:

  ```json
  "statusLine": { "type": "command", "command": "uv run --no-project python /path/to/tab5-agent-dash/collector/limits.py" }
  ```

  Until then `claude_code.limits` is `null`.
- **OpenRouter**: `OPENROUTER_API_KEY` gives that key's usage and the account's credits. `OPENROUTER_MANAGEMENT_KEY` adds per-day and per-model activity; without it `openrouter.activity` is `null`.

## Device app

The Tab5 runs UIFlow2 v2.5.5 (MicroPython 1.27). The app in `device/` polls the collector every 5 seconds and draws one of four themes. Tap the right third of the screen for the next theme and the left third for the previous one; the choice is kept across restarts. Each theme plays a short sound of its own when selected. Double-tap the middle of the screen for settings: speaker volume in 10% steps (each step plays the current theme's sound at the new level) and mute. They are kept in `/flash/dash/settings.json`; volume starts at 50%. Tap Done, or double-tap outside the buttons, to go back.

```sh
make firmware                # once per device: install UIFlow2 (replaces everything on the Tab5)
make preview                 # draw every theme and the settings screen to previews/*.png, and each theme's sound to *.wav
make preview-live            # the same with live data from a running collector
make start                   # copy changed files to the Tab5 over USB and restart the dashboard
make provision WIFI=FILE     # set Wi-Fi and the collector URL, then start
```

`WIFI` names a file with `WIFI_NAME` and `WIFI_PASSWORD`. They are stored in plain text on the device at `/flash/dash/config.json`. The collector URL defaults to this Mac's `.local` name; override it with `URL=`.

`make deploy` copies files without restarting. It interrupts the running app to reach the REPL, so the dashboard stays stopped until `make start`.

While the Tab5 runs on its battery, every theme shows a small battery outline and charge percentage. It disappears on external power. The reading is `M5.Power.getBatteryLevel()`, shown whenever `isCharging()` is false, so a full battery on USB may also show it.

### Themes

A theme is a module in `device/dash/themes/` listed in `themes/__init__.py`. It defines:

- `NAME` and `BACKGROUND`.
- `regions()`: a list of `Region(x, y, w, h, draw, key, bg)`. `draw(surface, m)` paints the region in its own coordinates. `key(m)` returns the values the region depends on; the engine redraws a region only when its key changes.
- `ANIMATE`: model fields the engine eases toward new values (and up from zero when the theme appears).
- `SOUND`: the notes played when the theme is selected, each `(start_ms, length_ms, from_hz, to_hz, wave, level)`. `device/dash/sound.py` mixes them into a WAV on first use and the device plays it with `M5.Speaker.playWav`; `make preview` writes the same WAV next to each image.

`m` is the dict built by `device/dash/model.py`. The surface offers `fill`, `rect`, `arc`, `text` and `text_width`. `tools/host_surface.py` implements the same surface with Pillow from the same font files, so previews and the tests in `tests/test_themes.py` match the device; text widths were checked to be identical on both.

Device limits that shape themes:

- Switching fonts on a canvas costs about 10 ms, so a region that animates should use one font.
- Drawing a glyph taller than about 150 px restarts the device. Larger numerals are stored at half size and drawn doubled (`SCALE` in `device/dash/fonts.py`).
- Arc angles are whole degrees.
- A full-screen redraw takes about 0.6 s; animation frames take 8 ms (Day dial) to about 90 ms (Gauge glass, Poster).

Fonts are declared in `device/dash/fonts.py`. Add an entry and run `make start`; fonts rebuild when their inputs change. The sources in `fonts/` are under the SIL Open Font License.

### Drawing speed

Measured on the device at 1280×720, 2026-11-26:

| Operation | Time |
| --- | --- |
| `M5.Lcd` filled arc, rectangle or text, drawn directly | 2–6 ms |
| `M5.Lcd` off-screen canvas 400×200, redraw and push | 11 ms |
| `M5.Lcd` off-screen canvas 520×520, redraw and push | 45 ms |
| `M5.Lcd` full-screen canvas push | 640 ms |
| LVGL 300 px arc update | 108 ms |
| LVGL full-screen redraw | 240 ms |

LVGL was too slow for large animated shapes and stays in portrait, so the app draws with `M5.Lcd` through small off-screen canvases.

### Working with the board

UIFlow2 drops USB on a soft reset and prints from background timers, which breaks `mpremote`. `tools/board.py` talks to the raw REPL without a soft reset. If it reports that the board did not enter the raw REPL, the board is still starting; run the command again.

`make firmware` reinstalls UIFlow2 and wipes the app; run `make provision` afterwards. To go back to other firmware, flash it the way that firmware documents.

## Guide

`docs/index.html` is the illustrated guide, written to be served by GitHub Pages from the `docs/` folder. `make docs` regenerates its theme images from sample data.

## Design concepts

`mockups/concepts.html` holds the original browser mockups of the first three themes.

## License

[MIT](LICENSE). The fonts in `fonts/` are under the SIL Open Font License; see `fonts/licenses/`.
