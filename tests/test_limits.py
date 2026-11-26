import io
import json
from datetime import datetime, timezone

from collector import limits

NOW = datetime(2026, 11, 26, 15, 30, tzinfo=timezone.utc)
FUTURE = int(datetime(2026, 11, 26, 18, 0, tzinfo=timezone.utc).timestamp())
PAST = int(datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc).timestamp())


def statusline_input(**windows):
    return {"model": {"display_name": "Fable 5.2"}, "rate_limits": windows}


def test_capture_then_read_round_trip(tmp_path):
    path = tmp_path / "state" / "limits.json"
    limits.capture(
        statusline_input(
            five_hour={"used_percentage": 23.4, "resets_at": FUTURE},
            seven_day={"used_percentage": 41, "resets_at": "2026-11-30T00:00:00Z"},
        ),
        path,
        NOW,
    )
    assert limits.read(path, NOW) == {
        "captured_at": "2026-11-26T15:30:00Z",
        "five_hour": {"used_percentage": 23.4, "resets_at": "2026-11-26T18:00:00Z"},
        "seven_day": {"used_percentage": 41, "resets_at": "2026-11-30T00:00:00Z"},
    }


def test_read_omits_windows_that_have_reset(tmp_path):
    path = tmp_path / "limits.json"
    limits.capture(
        statusline_input(
            five_hour={"used_percentage": 90, "resets_at": PAST},
            seven_day={"used_percentage": 41, "resets_at": FUTURE},
        ),
        path,
        NOW,
    )
    result = limits.read(path, NOW)
    assert "five_hour" not in result
    assert result["seven_day"]["used_percentage"] == 41


def test_capture_without_rate_limits_keeps_previous_file(tmp_path):
    path = tmp_path / "limits.json"
    limits.capture(statusline_input(five_hour={"used_percentage": 5, "resets_at": FUTURE}), path, NOW)
    limits.capture({"model": {"display_name": "Fable 5.2"}}, path, NOW)
    limits.capture({"rate_limits": None}, path, NOW)
    assert limits.read(path, NOW)["five_hour"]["used_percentage"] == 5


def test_read_missing_or_corrupt_file(tmp_path):
    assert limits.read(tmp_path / "nope.json", NOW) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    assert limits.read(bad, NOW) is None


def test_status_text():
    text = limits.status_text(
        statusline_input(
            five_hour={"used_percentage": 23.4, "resets_at": FUTURE},
            seven_day={"used_percentage": 41, "resets_at": FUTURE},
        )
    )
    assert text == "Fable 5.2 · 5h 23% · 7d 41%"
    assert limits.status_text({"model": {"display_name": "Fable 5.2"}}) == "Fable 5.2"
    assert limits.status_text({}) == ""


def test_main_reads_stdin_and_writes_state(tmp_path, monkeypatch, capsys):
    path = tmp_path / "limits.json"
    monkeypatch.setattr(limits, "DEFAULT_PATH", path)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps(statusline_input(five_hour={"used_percentage": 12, "resets_at": FUTURE}))),
    )
    limits.main()
    assert capsys.readouterr().out.strip() == "Fable 5.2 · 5h 12%"
    assert json.loads(path.read_text())["rate_limits"]["five_hour"]["used_percentage"] == 12


def test_main_survives_bad_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(limits, "DEFAULT_PATH", tmp_path / "limits.json")
    monkeypatch.setattr("sys.stdin", io.StringIO("garbage"))
    limits.main()
    assert capsys.readouterr().out.strip() == ""
