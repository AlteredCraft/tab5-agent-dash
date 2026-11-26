"""Copy the dashboard app to the Tab5 and (optionally) configure and start it.

    uv run python -m tools.deploy                            # sync changed files
    uv run python -m tools.deploy --wifi-env FILE --url URL  # also write the device config
    uv run python -m tools.deploy --start                    # run main.py at boot and restart
"""

import argparse
import ast
import binascii
import json
from pathlib import Path

from tools.board import Board

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
    for line in Path(path).read_text().splitlines():
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

    board = Board(args.port)
    files = local_files()
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

    if args.wifi_env or args.url:
        if not (args.wifi_env and args.url):
            parser.error("--wifi-env and --url go together")
        env = read_env(args.wifi_env)
        config = {"wifi_ssid": env["WIFI_NAME"], "wifi_password": env["WIFI_PASSWORD"], "url": args.url}
        board.write_file(DEVICE_ROOT + "/dash/config.json", json.dumps(config).encode())
        print("wrote device config for network", env["WIFI_NAME"])

    if args.start:
        try:
            board.run(START, timeout=5)
        except Exception:
            pass
        print("restarting into the dashboard")
    else:
        board.close()


if __name__ == "__main__":
    main()
