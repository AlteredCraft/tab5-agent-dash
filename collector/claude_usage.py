"""Token usage from Claude Code session transcripts (~/.claude/projects/**/*.jsonl)."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import pricing

DEFAULT_ROOT = Path("~/.claude/projects").expanduser()
DAILY_DAYS = 30
HOURLY_HOURS = 24


@dataclass(frozen=True)
class Record:
    message_id: str
    ts: datetime
    model: str
    project: str
    session: str
    input: int
    output: int
    cache_read: int
    cache_write_5m: int
    cache_write_1h: int
    fast: bool

    @property
    def cache_write(self):
        return self.cache_write_5m + self.cache_write_1h

    @property
    def total(self):
        return self.input + self.output + self.cache_read + self.cache_write


def parse_line(line):
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    message = entry.get("message") or {}
    usage = message.get("usage")
    model = message.get("model")
    if not usage or not model or model == "<synthetic>":
        return None
    try:
        ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
    except (KeyError, AttributeError, ValueError):
        return None
    message_id = message.get("id") or entry.get("uuid")
    if not message_id:
        return None

    write_total = usage.get("cache_creation_input_tokens") or 0
    breakdown = usage.get("cache_creation")
    if isinstance(breakdown, dict):
        write_1h = breakdown.get("ephemeral_1h_input_tokens") or 0
        write_5m = breakdown.get("ephemeral_5m_input_tokens") or 0
    else:
        write_1h, write_5m = 0, write_total

    return Record(
        message_id=message_id,
        ts=ts,
        model=model,
        project=Path(entry.get("cwd") or "unknown").name or "unknown",
        session=entry.get("sessionId") or "",
        input=usage.get("input_tokens") or 0,
        output=usage.get("output_tokens") or 0,
        cache_read=usage.get("cache_read_input_tokens") or 0,
        cache_write_5m=write_5m,
        cache_write_1h=write_1h,
        fast=usage.get("speed") == "fast",
    )


def parse_file(path):
    records = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                record = parse_line(line)
                if record:
                    records.append(record)
    except OSError:
        pass
    return records


class TranscriptStore:
    """Reads every transcript under a root, re-parsing only files that changed."""

    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root)
        self._cache = {}

    def records(self):
        # A transcript line is rewritten as a response streams, and resumed or
        # forked sessions copy earlier lines, so the same message id recurs.
        by_id = {}
        seen_paths = set()
        for path in self.root.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            seen_paths.add(path)
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = self._cache.get(path)
            if cached is None or cached[0] != signature:
                cached = (signature, parse_file(path))
                self._cache[path] = cached
            for record in cached[1]:
                previous = by_id.get(record.message_id)
                if previous is None or record.output > previous.output:
                    by_id[record.message_id] = record
        for path in set(self._cache) - seen_paths:
            del self._cache[path]
        return list(by_id.values())


class _Totals:
    def __init__(self):
        self.input = self.output = self.cache_read = self.cache_write = self.messages = 0
        self.cost = 0.0

    def add(self, record, cost):
        self.input += record.input
        self.output += record.output
        self.cache_read += record.cache_read
        self.cache_write += record.cache_write
        self.messages += 1
        self.cost += cost

    @property
    def total(self):
        return self.input + self.output + self.cache_read + self.cache_write

    def full(self):
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "total": self.total,
            "cost_usd": round(self.cost, 4),
            "messages": self.messages,
        }

    def brief(self):
        return {"cost_usd": round(self.cost, 4), "output": self.output, "total": self.total}


def _ranked(groups):
    rows = [{"name": name, **totals.brief()} for name, totals in groups.items()]
    return sorted(rows, key=lambda row: (-row["cost_usd"], row["name"]))


def _iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarize(records, now, tz=None):
    """Aggregate records for the dashboard. Days and hours follow `tz` (system local when None)."""
    local_now = now.astimezone(tz)
    today = local_now.date()
    current_hour = local_now.replace(minute=0, second=0, microsecond=0)

    windows = {"today": _Totals(), "last_7d": _Totals(), "last_30d": _Totals()}
    daily = [_Totals() for _ in range(DAILY_DAYS)]
    hourly = [_Totals() for _ in range(HOURLY_HOURS)]
    models_today, models_7d, projects_7d = {}, {}, {}
    unpriced = set()
    recent_output = 0
    recent_cost = 0.0
    active_sessions = set()
    last_activity = None

    for record in records:
        if record.ts > now:
            continue
        cost = pricing.cost_usd(record)
        if cost is None:
            unpriced.add(record.model)
            cost = 0.0
        local_ts = record.ts.astimezone(tz)
        days_ago = (today - local_ts.date()).days

        if last_activity is None or record.ts > last_activity:
            last_activity = record.ts
        if days_ago < DAILY_DAYS:
            windows["last_30d"].add(record, cost)
            daily[DAILY_DAYS - 1 - days_ago].add(record, cost)
        if days_ago < 7:
            windows["last_7d"].add(record, cost)
            models_7d.setdefault(record.model, _Totals()).add(record, cost)
            projects_7d.setdefault(record.project, _Totals()).add(record, cost)
        if days_ago == 0:
            windows["today"].add(record, cost)
            models_today.setdefault(record.model, _Totals()).add(record, cost)

        hours_ago = int((current_hour - local_ts.replace(minute=0, second=0, microsecond=0)) / timedelta(hours=1))
        if 0 <= hours_ago < HOURLY_HOURS:
            hourly[HOURLY_HOURS - 1 - hours_ago].add(record, cost)

        age = now - record.ts
        if age < timedelta(minutes=60):
            recent_cost += cost
        if age < timedelta(minutes=15):
            recent_output += record.output
        if age < timedelta(minutes=5):
            active_sessions.add(record.session)

    return {
        **{name: totals.full() for name, totals in windows.items()},
        "daily": [
            {"date": (today - timedelta(days=DAILY_DAYS - 1 - i)).isoformat(), **totals.brief()}
            for i, totals in enumerate(daily)
        ],
        "hourly": [
            {
                "start": (current_hour - timedelta(hours=HOURLY_HOURS - 1 - i)).isoformat(),
                **totals.brief(),
            }
            for i, totals in enumerate(hourly)
        ],
        "by_model_today": _ranked(models_today),
        "by_model_7d": _ranked(models_7d),
        "by_project_7d": _ranked(projects_7d),
        "unpriced_models": sorted(unpriced),
        "burn": {
            "output_tokens_per_min": round(recent_output / 15, 1),
            "cost_per_hour": round(recent_cost, 4),
        },
        "active_sessions": len(active_sessions),
        "last_activity_at": _iso_utc(last_activity) if last_activity else None,
    }
