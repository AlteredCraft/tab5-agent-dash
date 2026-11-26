import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from collector import claude_usage, pricing
from collector.claude_usage import TranscriptStore, parse_line, summarize

TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 11, 26, 15, 30, tzinfo=timezone.utc)  # 07:30 local


def assistant(
    msg_id,
    ts,
    model="claude-fable-5-2",
    cwd="/Users/x/Products/alpha",
    session="s1",
    input=0,
    output=0,
    cache_read=0,
    write_5m=0,
    write_1h=0,
    speed="standard",
):
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": cwd,
        "sessionId": session,
        "uuid": f"uuid-{msg_id}",
        "message": {
            "id": msg_id,
            "model": model,
            "usage": {
                "input_tokens": input,
                "output_tokens": output,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": write_5m + write_1h,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": write_5m,
                    "ephemeral_1h_input_tokens": write_1h,
                },
                "speed": speed,
            },
        },
    }


def write_jsonl(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for entry in entries:
            f.write((entry if isinstance(entry, str) else json.dumps(entry)) + "\n")


def test_parse_line_extracts_usage():
    record = parse_line(
        json.dumps(
            assistant(
                "m1",
                "2026-11-26T15:00:00.000Z",
                input=10,
                output=20,
                cache_read=30,
                write_5m=40,
                write_1h=50,
            )
        )
    )
    assert record.message_id == "m1"
    assert record.project == "alpha"
    assert record.session == "s1"
    assert (record.input, record.output, record.cache_read) == (10, 20, 30)
    assert (record.cache_write_5m, record.cache_write_1h) == (40, 50)
    assert record.ts == datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)


def test_parse_line_without_cache_breakdown_counts_writes_as_5m():
    entry = assistant("m1", "2026-11-26T15:00:00Z", write_5m=70)
    del entry["message"]["usage"]["cache_creation"]
    record = parse_line(json.dumps(entry))
    assert (record.cache_write_5m, record.cache_write_1h) == (70, 0)


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        json.dumps(assistant("m1", "2026-11-26T15:00:00Z", model="<synthetic>")),
        json.dumps({"type": "assistant", "timestamp": "2026-11-26T15:00:00Z", "message": {}}),
        json.dumps([1, 2]),
    ],
)
def test_parse_line_skips_unusable_lines(line):
    assert parse_line(line) is None


def test_store_deduplicates_across_files_keeping_largest_output(tmp_path):
    write_jsonl(
        tmp_path / "proj" / "a.jsonl",
        [
            assistant("m1", "2026-11-26T15:00:00Z", output=5),
            assistant("m1", "2026-11-26T15:00:01Z", output=50),
            assistant("m2", "2026-11-26T15:00:02Z", output=7),
        ],
    )
    write_jsonl(
        tmp_path / "proj" / "sess" / "subagents" / "agent-1.jsonl",
        [
            assistant("m1", "2026-11-26T15:00:00Z", output=5),
            assistant("m3", "2026-11-26T15:00:03Z", output=9),
        ],
    )
    records = TranscriptStore(tmp_path).records()
    assert sorted((r.message_id, r.output) for r in records) == [("m1", 50), ("m2", 7), ("m3", 9)]


def test_store_reparses_only_changed_files(tmp_path, monkeypatch):
    a = tmp_path / "p" / "a.jsonl"
    b = tmp_path / "p" / "b.jsonl"
    write_jsonl(a, [assistant("m1", "2026-11-26T15:00:00Z", output=1)])
    write_jsonl(b, [assistant("m2", "2026-11-26T15:00:00Z", output=2)])
    parsed = []
    real = claude_usage.parse_file
    monkeypatch.setattr(claude_usage, "parse_file", lambda p: parsed.append(p.name) or real(p))

    store = TranscriptStore(tmp_path)
    store.records()
    assert sorted(parsed) == ["a.jsonl", "b.jsonl"]

    parsed.clear()
    write_jsonl(a, [assistant("m3", "2026-11-26T15:01:00Z", output=3)])
    records = store.records()
    assert parsed == ["a.jsonl"]
    assert sorted(r.message_id for r in records) == ["m1", "m2", "m3"]


def test_cost_uses_per_model_rates():
    million = 1_000_000
    record = parse_line(
        json.dumps(
            assistant(
                "m1",
                "2026-11-26T15:00:00Z",
                model="claude-fable-5-2",
                input=million,
                output=million,
                cache_read=million,
                write_5m=million,
                write_1h=million,
            )
        )
    )
    assert pricing.cost_usd(record) == pytest.approx(8 + 40 + 0.20 + 10 + 16)


def test_cost_prefers_longest_model_prefix_and_handles_unknown():
    def cost(model):
        return pricing.cost_usd(
            parse_line(json.dumps(assistant("m", "2026-11-26T15:00:00Z", model=model, input=1_000_000)))
        )

    assert cost("claude-opus-5-5") == pytest.approx(4)
    assert cost("claude-opus-5") == pytest.approx(5)
    assert cost("claude-opus-5-5-20260901") == pytest.approx(4)
    assert cost("some-other-model") is None


def test_cost_doubles_in_fast_mode():
    record = parse_line(
        json.dumps(
            assistant("m", "2026-11-26T15:00:00Z", model="claude-opus-5-5", output=1_000_000, speed="fast")
        )
    )
    assert pricing.cost_usd(record) == pytest.approx(40)


def records_from(entries):
    return [parse_line(json.dumps(e)) for e in entries]


def test_summary_windows_use_local_days():
    records = records_from(
        [
            # 07:00 local today
            assistant("today", "2026-11-26T15:00:00Z", output=100),
            # 23:30 local on the 25th, although the UTC date is the 26th
            assistant("yesterday", "2026-11-26T07:30:00Z", output=10),
            # six local days back: still inside the 7-day window
            assistant("day6", "2026-11-20T20:00:00Z", output=1),
            # seven local days back: outside it
            assistant("day7", "2026-11-19T20:00:00Z", output=1000),
            assistant("old", "2026-10-01T20:00:00Z", output=5000),
        ]
    )
    summary = summarize(records, NOW, TZ)
    assert summary["today"]["output"] == 100
    assert summary["today"]["messages"] == 1
    assert summary["last_7d"]["output"] == 111
    assert summary["last_30d"]["output"] == 1111

    daily = summary["daily"]
    assert len(daily) == 30
    assert daily[-1]["date"] == "2026-11-26"
    assert daily[-1]["output"] == 100
    assert daily[-2]["output"] == 10
    assert daily[0]["date"] == "2026-10-28"


def test_summary_totals_and_cost():
    records = records_from(
        [
            assistant(
                "m1",
                "2026-11-26T15:00:00Z",
                model="claude-opus-5-5",
                input=1_000_000,
                output=500_000,
                cache_read=2_000_000,
                write_1h=100_000,
            )
        ]
    )
    today = summarize(records, NOW, TZ)["today"]
    assert today["input"] == 1_000_000
    assert today["cache_write"] == 100_000
    assert today["total"] == 3_600_000
    assert today["cost_usd"] == pytest.approx(4 + 10 + 0.4 + 0.8)


def test_summary_hourly_covers_last_24_hours():
    records = records_from(
        [
            assistant("now", "2026-11-26T15:10:00Z", output=3),
            assistant("edge", "2026-11-26T15:00:00Z", output=4),
            assistant("prev", "2026-11-26T14:59:59Z", output=5),
            assistant("oldest", "2026-11-25T16:00:00Z", output=6),
            assistant("too-old", "2026-11-25T15:59:59Z", output=7),
        ]
    )
    hourly = summarize(records, NOW, TZ)["hourly"]
    assert len(hourly) == 24
    assert hourly[-1]["output"] == 7
    assert hourly[-2]["output"] == 5
    assert hourly[0]["output"] == 6
    assert hourly[-1]["start"] == "2026-11-26T07:00:00-08:00"


def test_summary_burn_rate_and_activity():
    records = records_from(
        [
            assistant("a", "2026-11-26T15:28:00Z", session="s1", output=1500, model="claude-opus-5-5"),
            assistant("b", "2026-11-26T15:20:00Z", session="s2", output=1500, model="claude-opus-5-5"),
            assistant("c", "2026-11-26T14:40:00Z", session="s3", output=1_000_000, model="claude-opus-5-5"),
            assistant("d", "2026-11-26T14:00:00Z", session="s4", output=1_000_000, model="claude-opus-5-5"),
        ]
    )
    summary = summarize(records, NOW, TZ)
    assert summary["burn"]["output_tokens_per_min"] == pytest.approx(200)
    assert summary["burn"]["cost_per_hour"] == pytest.approx(20 + 0.06)
    assert summary["active_sessions"] == 1
    assert summary["last_activity_at"] == "2026-11-26T15:28:00Z"


def test_summary_groups_by_model_and_project():
    records = records_from(
        [
            assistant("a", "2026-11-26T15:00:00Z", model="claude-opus-5-5", cwd="/w/alpha", output=1_000_000),
            assistant("b", "2026-11-26T15:00:00Z", model="claude-fable-5-2", cwd="/w/beta", output=1_000_000),
            assistant("c", "2026-11-25T15:00:00Z", model="claude-fable-5-2", cwd="/w/beta", output=1_000_000),
            assistant("d", "2026-11-26T15:00:00Z", model="mystery", cwd="/w/gamma", output=10),
        ]
    )
    summary = summarize(records, NOW, TZ)
    assert [(m["name"], m["cost_usd"]) for m in summary["by_model_7d"]] == [
        ("claude-fable-5-2", 80.0),
        ("claude-opus-5-5", 20.0),
        ("mystery", 0.0),
    ]
    assert [m["name"] for m in summary["by_model_today"]] == ["claude-fable-5-2", "claude-opus-5-5", "mystery"]
    assert summary["by_project_7d"][0] == {
        "name": "beta",
        "cost_usd": 80.0,
        "output": 2_000_000,
        "total": 2_000_000,
    }
    assert summary["unpriced_models"] == ["mystery"]


def test_summary_of_nothing():
    summary = summarize([], NOW, TZ)
    assert summary["today"]["total"] == 0
    assert summary["last_activity_at"] is None
    assert summary["burn"] == {"output_tokens_per_min": 0.0, "cost_per_hour": 0.0}
