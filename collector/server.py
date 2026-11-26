"""Serves the dashboard payload at GET /usage.json for the Tab5 to poll."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import claude_usage, limits
from . import openrouter as openrouter_api

OPENROUTER_TTL_SECONDS = 60
CLAUDE_TTL_SECONDS = 2


def load_env_file(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


class Cached:
    """Caches a producer for `ttl` seconds. If a refresh fails, the previous
    value is returned marked stale so the device can keep showing it."""

    def __init__(self, produce, ttl, clock=time.monotonic):
        self._produce = produce
        self._ttl = ttl
        self._clock = clock
        self._attempted_at = None
        self._good = None
        self._current = None

    def get(self):
        now = self._clock()
        if self._attempted_at is not None and now - self._attempted_at < self._ttl:
            return self._current
        self._attempted_at = now
        try:
            self._good = self._current = self._produce()
        except Exception as error:
            failure = {"error": str(error)}
            self._current = {**self._good, "stale": True, **failure} if isinstance(self._good, dict) else failure
        return self._current


def build_payload(store, limits_path, openrouter, now=None, tz=None):
    now = now or datetime.now(timezone.utc)
    claude = claude_usage.summarize(store.records(), now, tz)
    claude["limits"] = limits.read(limits_path, now)
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claude_code": claude,
        "openrouter": openrouter(),
    }


def make_server(host, port, store, limits_path, openrouter):
    payload = Cached(lambda: build_payload(store, limits_path, openrouter), CLAUDE_TTL_SECONDS)
    clients = set()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/usage.json":
                self.send_error(404)
                return
            if self.client_address[0] not in clients:
                clients.add(self.client_address[0])
                print("First request from", self.client_address[0], flush=True)
            body = json.dumps(payload.get(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--claude-dir", type=Path, default=claude_usage.DEFAULT_ROOT)
    parser.add_argument("--limits-file", type=Path, default=limits.DEFAULT_PATH)
    parser.add_argument(
        "--env",
        type=Path,
        action="append",
        default=[],
        help="env file holding OPENROUTER_API_KEY and/or OPENROUTER_MANAGEMENT_KEY (repeatable)",
    )
    parser.add_argument("--once", action="store_true", help="print the payload and exit")
    args = parser.parse_args()

    env = dict(os.environ)
    for path in args.env:
        env.update(load_env_file(path))
    api_key = env.get("OPENROUTER_API_KEY")
    management_key = env.get("OPENROUTER_MANAGEMENT_KEY")

    store = claude_usage.TranscriptStore(args.claude_dir)
    openrouter = Cached(lambda: openrouter_api.fetch(api_key, management_key), OPENROUTER_TTL_SECONDS).get

    if args.once:
        print(json.dumps(build_payload(store, args.limits_file, openrouter), indent=2))
        return

    httpd = make_server(args.host, args.port, store, args.limits_file, openrouter)
    print(f"Serving http://{args.host}:{args.port}/usage.json", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
