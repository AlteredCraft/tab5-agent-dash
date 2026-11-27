import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest

from collector import server
from collector.claude_usage import TranscriptStore

from .test_claude_usage import assistant, write_jsonl

NOW = datetime(2026, 11, 26, 15, 30, tzinfo=timezone.utc)


def test_load_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nOPENROUTER_API_KEY=abc\nexport OTHER='quoted value'\n\nBROKEN\n")
    assert server.load_env_file(env) == {"OPENROUTER_API_KEY": "abc", "OTHER": "quoted value"}


def test_cached_reuses_value_within_ttl_and_keeps_last_good_value():
    clock = [0.0]
    calls = []

    def produce():
        calls.append(1)
        if len(calls) == 2:
            raise OSError("network down")
        return {"n": len(calls)}

    cached = server.Cached(produce, ttl=60, clock=lambda: clock[0])
    assert cached.get() == {"n": 1}
    assert cached.get() == {"n": 1}
    assert len(calls) == 1

    clock[0] = 61
    assert cached.get() == {"n": 1, "stale": True, "error": "network down"}

    clock[0] = 200
    assert cached.get() == {"n": 3}


def test_cached_reports_error_when_there_is_no_previous_value():
    def fail():
        raise OSError("boom")

    assert server.Cached(fail, ttl=60).get() == {"error": "boom"}


def test_build_payload(tmp_path):
    write_jsonl(tmp_path / "p" / "a.jsonl", [assistant("m1", "2026-11-26T15:00:00Z", output=100)])
    payload = server.build_payload(
        TranscriptStore(tmp_path),
        limits_path=tmp_path / "missing.json",
        openrouter=lambda: {"credits": {"total": 1, "used": 0, "remaining": 1}},
        now=NOW,
    )
    assert payload["generated_at"] == "2026-11-26T15:30:00Z"
    assert payload["claude_code"]["today"]["output"] == 100
    assert payload["claude_code"]["limits"] is None
    assert payload["openrouter"]["credits"]["total"] == 1


@pytest.fixture
def running_server(tmp_path):
    write_jsonl(tmp_path / "p" / "a.jsonl", [assistant("m1", "2026-11-26T15:00:00Z", output=100)])
    httpd = server.make_server(
        "127.0.0.1",
        0,
        TranscriptStore(tmp_path),
        limits_path=tmp_path / "missing.json",
        openrouter=lambda: None,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_server_serves_usage_json(running_server):
    with urllib.request.urlopen(f"{running_server}/usage.json", timeout=5) as response:
        assert response.headers["Content-Type"] == "application/json"
        payload = json.loads(response.read())
    assert set(payload) == {"generated_at", "claude_code", "openrouter", "control"}
    assert payload["openrouter"] is None


def test_server_returns_404_for_other_paths(running_server):
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(f"{running_server}/etc/passwd", timeout=5)
    assert error.value.code == 404


def test_server_reports_when_each_client_last_asked(running_server):
    with urllib.request.urlopen(f"{running_server}/status.json", timeout=5) as response:
        assert json.loads(response.read()) == {"seconds_since_request": {}}
    urllib.request.urlopen(f"{running_server}/usage.json", timeout=5).close()
    with urllib.request.urlopen(f"{running_server}/status.json", timeout=5) as response:
        seen = json.loads(response.read())["seconds_since_request"]
    assert list(seen) == ["127.0.0.1"] and 0 <= seen["127.0.0.1"] < 5


def test_main_explains_a_port_already_in_use(running_server, monkeypatch, tmp_path):
    port = running_server.rsplit(":", 1)[1]
    monkeypatch.setattr("sys.argv", ["server", "--host", "127.0.0.1", "--port", port, "--claude-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as stopped:
        server.main()
    assert "already in use" in str(stopped.value) and "make stop" in str(stopped.value)


def test_main_explains_a_missing_key_file(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["server", "--once", "--env", str(tmp_path / "nope.env")])
    with pytest.raises(SystemExit) as stopped:
        server.main()
    assert "nope.env not found" in str(stopped.value)


def test_control_requests_reach_the_device_through_the_payload(running_server):
    with urllib.request.urlopen(f"{running_server}/usage.json", timeout=5) as response:
        assert json.loads(response.read())["control"] == {"restart": 0, "off": 0}

    request = urllib.request.Request(f"{running_server}/control/restart", method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        requested = json.loads(response.read())["restart"]
    assert requested > 0

    with urllib.request.urlopen(f"{running_server}/usage.json", timeout=5) as response:
        assert json.loads(response.read())["control"] == {"restart": requested, "off": 0}


def test_unknown_control_request_is_rejected(running_server):
    request = urllib.request.Request(f"{running_server}/control/explode", method="POST")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=5)
    assert error.value.code == 404
