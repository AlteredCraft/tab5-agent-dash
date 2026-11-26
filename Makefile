# tab5-agent-dash: common tasks. `make` lists them.
# Works with the GNU Make 3.81 that ships with macOS. Needs only `uv`.
#
# Variables (set on the command line only, e.g. `make serve ENV=~/keys/openrouter.env`):
#   ENV    env file with OPENROUTER_API_KEY and/or OPENROUTER_MANAGEMENT_KEY, for the collector
#   WIFI   env file with WIFI_NAME and WIFI_PASSWORD, for `make provision`
#   URL    collector URL the Tab5 polls (default: this Mac's .local name, port 8787)
#   HOST   address the collector listens on (default 0.0.0.0; 127.0.0.1 keeps it off the network)
#   PORT   Tab5 serial port; the first Espressif USB device when unset
#   ARGS   extra arguments passed through to the underlying tool

SHELL := /bin/bash
.DEFAULT_GOAL := help

PY := uv run python

# Only command-line values count, so an ENV or PORT exported in your shell never leaks in.
$(foreach v,ENV WIFI URL HOST PORT ARGS,$(if $(filter command line,$(origin $(v))),,$(eval $(v) :=)))

COLLECTOR_PORT := 8787
HOST := $(or $(HOST),0.0.0.0)
# A .local name keeps working when the Mac's address changes; the device looks it up once per connection.
URL := $(or $(URL),http://$(shell scutil --get LocalHostName 2>/dev/null || hostname -s).local:$(COLLECTOR_PORT)/usage.json)

# 0x303A is Espressif's USB vendor id: the Tab5 reports it both in its bootloader
# and under UIFlow2. Listing ports does not open them.
ifeq ($(PORT),)
PORT = $(shell $(PY) -c 'from serial.tools.list_ports import comports; print(next((p.device for p in comports() if p.vid == 0x303A), ""))' 2>/dev/null)
endif

# UIFlow2 for the Tab5, from M5Stack's M5Burner download server.
UIFLOW_VERSION := v2.5.5
UIFLOW_URL := https://m5burner.m5stack.com/firmware/de748c1072c12cac101b988672d9b799.bin
UIFLOW_SHA256 := 979fb10cf27af7f3211e416531c255ffeaaa3415f22c35f41fa06811149733a8
FIRMWARE := .local/firmware/uiflow2-tab5-$(UIFLOW_VERSION).bin

FONT_STAMP := device/dash/vlw/.built
FONT_INPUTS := device/dash/fonts.py tools/build_fonts.py tools/vlw.py $(wildcard fonts/*.ttf)

.PHONY: help test serve once fonts preview preview-live docs ports firmware deploy start provision clean

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  \033[1m%-13s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "  Variables: ENV, WIFI, URL=$(URL), HOST=$(HOST), PORT (auto-detected), ARGS"
	@echo "  New Tab5: make firmware, then make serve ENV=..., then make provision WIFI=..."

# --- Mac side ---

test: $(FONT_STAMP) ## Run all tests (collector, engine, themes rendered in every data state)
	uv run pytest -q $(ARGS)

serve: ## Run the collector the Tab5 polls: serve ENV=path/to/openrouter.env
	$(PY) -m collector.server --host $(HOST) --port $(COLLECTOR_PORT) $(if $(ENV),--env $(ENV)) $(ARGS)

once: ## Print the collector's payload once and exit: once ENV=...
	$(PY) -m collector.server --once $(if $(ENV),--env $(ENV)) $(ARGS)

# --- Themes ---

$(FONT_STAMP): $(FONT_INPUTS)
	$(PY) -m tools.build_fonts
	@touch $@

fonts: $(FONT_STAMP) ## Render fonts/ to the bitmap fonts the device loads (rebuilds only when inputs change)

preview: $(FONT_STAMP) ## Draw every theme to previews/*.png with sample data, using the device's own code
	$(PY) -m tools.preview $(ARGS)

preview-live: $(FONT_STAMP) ## Draw every theme with live data (needs `make serve` running)
	$(PY) -m tools.preview --url http://127.0.0.1:$(COLLECTOR_PORT)/usage.json $(ARGS)

docs: $(FONT_STAMP) ## Regenerate the theme images used by the guide in docs/ (sample data only)
	$(PY) -m tools.preview --out docs/img --regions

# --- Tab5 ---

ports: ## List serial ports and show which one is the Tab5
	@$(PY) -m serial.tools.list_ports -v
	@echo; echo "  Tab5: $(or $(PORT),not found)"

$(FIRMWARE):
	@mkdir -p $(dir $@)
	curl -fL --progress-bar -o $@.part $(UIFLOW_URL)
	@echo "$(UIFLOW_SHA256)  $@.part" | shasum -a 256 -c -
	@mv $@.part $@

# The image covers the whole flash, so this also wipes the dashboard and its Wi-Fi
# settings: run `make provision` afterwards. If the flasher cannot connect, put the
# Tab5 in download mode first (M5Stack's Tab5 page describes the button press).
firmware: $(FIRMWARE) ## Install the UIFlow2 firmware on the Tab5, replacing everything on it (once per device)
	@test -n "$(PORT)" || { echo "Tab5 not found on USB; see 'make ports' or pass PORT=..." >&2; exit 1; }
	uvx esptool --chip esp32p4 --port $(PORT) --baud 921600 write-flash 0x0 $(FIRMWARE) $(ARGS)

# Every device target below stops the running dashboard to reach the REPL. If the board
# is still starting up the tool says so; run the target again.
deploy: $(FONT_STAMP) ## Copy changed app files and fonts to the Tab5 (leaves the dashboard stopped)
	@test -n "$(PORT)" || { echo "Tab5 not found on USB; see 'make ports' or pass PORT=..." >&2; exit 1; }
	$(PY) -m tools.deploy --port $(PORT) $(ARGS)

start: $(FONT_STAMP) ## Copy changed files, then restart the Tab5 into the dashboard
	@test -n "$(PORT)" || { echo "Tab5 not found on USB; see 'make ports' or pass PORT=..." >&2; exit 1; }
	$(PY) -m tools.deploy --port $(PORT) --start $(ARGS)

provision: $(FONT_STAMP) ## Set the Tab5's Wi-Fi and collector URL, then start: provision WIFI=path/to/wifi.env [URL=...]
	@test -n "$(WIFI)" || { echo "usage: make provision WIFI=path/to/wifi.env [URL=...]  (file needs WIFI_NAME and WIFI_PASSWORD)" >&2; exit 2; }
	@test -n "$(PORT)" || { echo "Tab5 not found on USB; see 'make ports' or pass PORT=..." >&2; exit 1; }
	$(PY) -m tools.deploy --port $(PORT) --wifi-env $(WIFI) --url $(URL) --start $(ARGS)

# --- Housekeeping ---

clean: ## Remove generated previews, built fonts and caches (not .local backups)
	rm -rf previews device/dash/vlw .pytest_cache
	find . -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +
