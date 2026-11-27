"""Copy the dashboard app to the Tab5 and (optionally) configure and start it.

    uv run python -m tools.deploy --start                            # sync changed files and restart
    uv run python -m tools.deploy --wifi-env FILE --url URL --start  # also write the device config
    uv run python -m tools.deploy                                    # sync only; leaves the dashboard stopped
"""

import argparse
import ast
import binascii
import json
from pathlib import Path

import serial

from tools.board import Board, BoardError, ask_over_wifi

ROOT = Path(__file__).resolve().parent.parent / "device"
DEVICE_ROOT = "/flash"
DEFAULT_PORT = "/dev/cu.usbmodem101"

LIST_REMOTE = """
import os, binascii
def _crc(path):
    crc = 0
    with open(path, 'rb') as f:
        while True:
            block = f.read(4096)
            if not block:
                return crc
            crc = binascii.crc32(block, crc)
def _walk(d, out):
    for name in os.listdir(d):
        path = d + '/' + name
        if os.stat(path)[0] & 0x4000:
            _walk(path, out)
        else:
            out[path] = _crc(path)
_out = {}
try:
    _walk('%s/dash', _out)
except OSError:
    pass
print(_out)
"""

MAKE_DIRS = """
import os
for _d in %r:
    try:
        os.mkdir(_d)
    except OSError:
        pass
"""

# boot_option 0 makes UIFlow2's boot.py run main.py without its startup menu.
START = """
import esp32, machine
esp32.NVS('uiflow').set_u8('boot_option', 0)
esp32.NVS('uiflow').commit()
machine.reset()
"""


def local_files():
    files = {}
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".vlw") and "__pycache__" not in path.parts:
            files[DEVICE_ROOT + "/" + path.relative_to(ROOT).as_posix()] = path.read_bytes()
    if not any(path.endswith(".vlw") for path in files):
        raise SystemExit("No fonts built yet. Run: uv run python -m tools.build_fonts")
    return files


def read_env(path):
    values = {}
    try:
        text = Path(path).read_text()
    except OSError:
        raise SystemExit("Wi-Fi file %s not found." % path) from None
    for line in text.splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and not name.startswith("#"):
            values[name.strip()] = value.strip().strip("'\"")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--wifi-env", help="env file with WIFI_NAME and WIFI_PASSWORD")
    parser.add_argument("--url", help="collector URL, e.g. http://192.168.0.44:8787/usage.json")
    parser.add_argument("--start", action="store_true", help="run the app at boot and restart the device")
    args = parser.parse_args()

    # Check the input first: connecting stops the running dashboard.
    config = None
    if args.wifi_env or args.url:
        if not (args.wifi_env and args.url):
            parser.error("--wifi-env and --url go together")
        env = read_env(args.wifi_env)
        if not env.get("WIFI_NAME") or "WIFI_PASSWORD" not in env:
            raise SystemExit("%s needs two lines: WIFI_NAME=... and WIFI_PASSWORD=..." % args.wifi_env)
        config = {"wifi_ssid": env["WIFI_NAME"], "wifi_password": env["WIFI_PASSWORD"], "url": args.url}
    files = local_files()

    try:
        sync(args, files, config)
    except BoardError as error:
        raise SystemExit(str(error)) from None
    except (serial.SerialException, OSError) as error:
        raise SystemExit(
            "Lost the USB connection to the Tab5 (%s).\nCheck the cable and run the command again." % error
        ) from None


def connect(port):
    """The Tab5's USB console sometimes stops answering while the dashboard
    runs. A restart with USB connected brings it back, and the collector can
    ask for one over Wi-Fi."""
    try:
        return Board(port, wait=12)
    except BoardError:
        if not ask_over_wifi("restart"):
            raise
    print("The Tab5 is not answering on USB. Asked it to restart over Wi-Fi; waiting...")
    return Board(port, wait=60)


def sync(args, files, config):
    board = connect(args.port)
    remote = ast.literal_eval(board.run(LIST_REMOTE % DEVICE_ROOT, timeout=120).strip())
    directories = sorted({path.rsplit("/", 1)[0] for path in files if path.count("/") > 2})
    board.run(MAKE_DIRS % (directories,))

    for path, data in files.items():
        if remote.get(path) == binascii.crc32(data):
            continue
        print("copy", path, len(data))
        board.write_file(path, data)
    for path in sorted(set(remote) - set(files)):
        if path.endswith((".py", ".vlw")):
            print("remove", path)
            board.run("import os\nos.remove(%r)" % path)

    if config:
        board.write_file(DEVICE_ROOT + "/dash/config.json", json.dumps(config).encode())
        print("wrote device config for network", config["wifi_ssid"], "and collector", config["url"])

    if args.start:
        try:
            board.run(START, timeout=5)
        except Exception:
            pass
        print("Done. The Tab5 is restarting into the dashboard.")
    else:
        board.close()
        print("Done. The dashboard is stopped; run with --start to restart it.")


if __name__ == "__main__":
    main()
