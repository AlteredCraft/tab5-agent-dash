# tab5-agent-dash: common tasks. `make` lists them.
# Works with the GNU Make 3.81 that ships with macOS. Needs only `uv`.
#
# Variables (set on the command line only, e.g. `make serve ENV=~/keys/openrouter.env`):
#   ENV    file with OPENROUTER_API_KEY and/or OPENROUTER_MANAGEMENT_KEY, for the collector
#          (default: .env.openrouter in this folder, if it exists)
#   WIFI   file with WIFI_NAME and WIFI_PASSWORD, for `make provision`
#          (default: .env.wifi in this folder, if it exists)
#   URL    collector URL the Tab5 polls (default: this Mac's .local name, port 8787)
#   HOST   address the collector listens on (default 0.0.0.0; 127.0.0.1 keeps it off the network)
#   PORT   Tab5 serial port; the first Espressif USB device when unset
#   ARGS   extra arguments passed through to the underlying tool
#
# Both default files match .gitignore's `.env.*`, so they are never committed.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PY := uv run python

# Only command-line values count, so an ENV or PORT exported in your shell never leaks in.
$(foreach v,ENV WIFI URL HOST PORT ARGS,$(if $(filter command line,$(origin $(v))),,$(eval $(v) :=)))

COLLECTOR_PORT := 8787
HOST := $(or $(HOST),0.0.0.0)
ENV := $(or $(ENV),$(wildcard .env.openrouter))
WIFI := $(or $(WIFI),$(wildcard .env.wifi))
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

# Used by every target that talks to the Tab5 over USB.
define need_tab5
	@test -n "$(PORT)" || { \
	  echo "No Tab5 found on USB."; \
	  echo "  - Plug it in with a data cable and make sure it is switched on."; \
	  echo "  - 'make ports' lists what the Mac can see; pass PORT=... to choose one."; \
	  exit 1; } >&2
endef

.PHONY: help firmware provision serve stop status test preview preview-live deploy payload docs fonts ports off clean

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^##@ / {printf "\n%s\n", substr($$0, 5)} /^[a-z-]+:.*## / {printf "  \033[1m%-13s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Variables: ENV=$(or $(ENV),(none)), WIFI=$(or $(WIFI),(none)), HOST=$(HOST), PORT (auto-detected), ARGS"
	@echo "           URL=$(URL)"

##@ Set up a Tab5 (once)

$(FIRMWARE):
	@mkdir -p $(dir $@)
	curl -fL --progress-bar -o $@.part $(UIFLOW_URL)
	@echo "$(UIFLOW_SHA256)  $@.part" | shasum -a 256 -c -
	@mv $@.part $@

# The image covers the whole flash, so this also wipes the dashboard and its Wi-Fi
# settings: run `make provision` afterwards.
firmware: $(FIRMWARE) ## Install the UIFlow2 firmware, replacing everything on the Tab5
	$(need_tab5)
	@uvx esptool --chip esp32p4 --port $(PORT) --baud 921600 write-flash 0x0 $(FIRMWARE) $(ARGS) || { \
	  echo; \
	  echo "Flashing failed. If the flasher could not connect, put the Tab5 in download mode"; \
	  echo "(see https://docs.m5stack.com/en/core/Tab5) and run 'make firmware' again."; \
	  exit 1; } >&2
	@echo "Firmware installed. Next: make provision"

provision: $(FONT_STAMP) ## Install the dashboard and set its Wi-Fi: provision WIFI=path/to/wifi.env
	@test -n "$(WIFI)" || { \
	  echo "No Wi-Fi settings given. Create a file named .env.wifi here with two lines:"; \
	  echo "    WIFI_NAME=your network name"; \
	  echo "    WIFI_PASSWORD=your network password"; \
	  echo "then run 'make provision' again. To use a file elsewhere: make provision WIFI=path/to/file"; \
	  exit 1; } >&2
	$(need_tab5)
	@$(PY) -m tools.deploy --port $(PORT) --wifi-env $(WIFI) --url $(URL) --start $(ARGS)

##@ Run

serve: ## Run the collector the Tab5 polls, until Ctrl-C: serve [ENV=path/to/openrouter.env]
	@$(PY) -m collector.server --host $(HOST) --port $(COLLECTOR_PORT) $(if $(ENV),--env $(ENV)) $(ARGS)

stop: ## Stop a collector left running in another terminal or in the background
	@if pkill -f '[c]ollector\.server' ; then echo "Collector stopped."; else echo "No collector was running."; fi

status: ## Show whether the collector, its data sources and the Tab5 are up
	@$(PY) -m tools.status --port $(COLLECTOR_PORT)

##@ Develop

test: $(FONT_STAMP) ## Run all tests (collector, engine, every theme in every data state)
	@uv run pytest -q $(ARGS)

preview: $(FONT_STAMP) ## Draw every theme to previews/*.png with sample data, using the device's own code
	@$(PY) -m tools.preview $(ARGS)

preview-live: $(FONT_STAMP) ## Draw every theme with live data from the running collector
	@$(PY) -m tools.preview --url http://127.0.0.1:$(COLLECTOR_PORT)/usage.json $(ARGS)

deploy: $(FONT_STAMP) ## Copy changed code and fonts to the Tab5 and restart the dashboard
	$(need_tab5)
	@$(PY) -m tools.deploy --port $(PORT) --start $(ARGS)

payload: ## Print the JSON the collector would serve right now: payload [ENV=...]
	@$(PY) -m collector.server --once $(if $(ENV),--env $(ENV)) $(ARGS)

docs: $(FONT_STAMP) ## Regenerate the theme images used by the guide in docs/ (sample data only)
	@$(PY) -m tools.preview --out docs/img --regions --battery 72

$(FONT_STAMP): $(FONT_INPUTS)
	@$(PY) -m tools.build_fonts
	@touch $@

fonts: $(FONT_STAMP) ## Rebuild the device's bitmap fonts (other targets do this when needed)

##@ Tab5 and housekeeping

ports: ## List serial ports and show which one is the Tab5
	@$(PY) -m serial.tools.list_ports -v
	@echo; echo "  Tab5: $(or $(PORT),not found)"

off: ## Power the Tab5 off (its power button turns it back on)
	$(need_tab5)
	@$(PY) -m tools.power --port $(PORT)

clean: ## Remove generated previews, built fonts and caches
	@rm -rf previews device/dash/vlw .pytest_cache
	@find . -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +
	@echo "Removed previews, built fonts and caches."
