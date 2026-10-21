"""Read Droid's local request metrics and enrich exact matching imported rows.

This module never sends a request. Trace/span IDs can be reused for a whole
agent turn, so a timing is accepted only after a complete, ordered event chain.
"""

import json
import math
from collections import defaultdict
from concurrent.futures import CancelledError
from dataclasses import dataclass
from datetime import datetime

TABLE = "droid_hook_timings"
FIRST = "chat_client_time_to_first_token"
DURATION = "chat_client_request_duration"
SUCCESS = "droid_chat_client_success_count"


@dataclass(frozen=True)
class RequestTiming:
    session_id: str
    message_id: str
    model: str
    tokens: tuple
    ended_at: float
    latency_ms: int
    first_token_ms: int

    @property
    def evidence_id(self):
        return self.session_id + "/" + self.message_id


def check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise CancelledError()


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0 <= value <= 86400 and math.isfinite(value) else None


def parse_line(line):
    prefix, separator, body = line.partition(" | Context: ")
    if not separator or not prefix.startswith("["):
        return None
    # Ignore unrelated logs before parsing potentially large diagnostic bodies.
    if not any(name in prefix for name in (FIRST, DURATION, SUCCESS, "[Agent] Streaming result")):
        return None
    try:
        stamp = datetime.fromisoformat(prefix[1:prefix.index("]")].replace("Z", "+00:00"))
        event = json.loads(body)
        if stamp.tzinfo is None or not isinstance(event, dict):
            return None
        tags = event.get("tags")
        if not isinstance(tags, dict):
            return None
        key = (
            event.get("factory.process.instance_id"),
            event.get("sessionId") or tags.get("sessionId"),
            tags.get("traceId"), tags.get("spanId"),
        )
        if any(not isinstance(part, str) or not part for part in key):
            return None
        return stamp.timestamp(), key, event
    except (ValueError, OverflowError):
        return None


def read_file(path, cancelled):
    pending = {}
    requests = []
    with path.open(encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            check_cancelled(cancelled)
            if not line.endswith("\n"):
                continue  # The writer has not finished this record yet.
            parsed = parse_line(line)
            if parsed is None:
                continue
            at, key, event = parsed
            metric = event.get("metric")
            if metric == FIRST:
                # A new request resets the prior chain, even on the same span.
                pending.pop(key, None)
                first = seconds(event.get("value"))
                if first is not None:
                    pending[key] = {"first": first, "start": at - first}
                continue
            current = pending.get(key)
            if current is None:
                continue
            if metric == DURATION:
                duration = seconds(event.get("value"))
                if ("end" in current or duration is None or duration <= current["first"]
                        or abs((at - duration) - current["start"]) > 1):
                    pending.pop(key, None)
                    continue
                current.update(duration=duration, end=at, model=event.get("modelId"))
            elif metric == SUCCESS:
                message_id = event.get("assistantMessageId")
                if ("message" in current or "end" not in current
                        or not 0 <= at - current["end"] <= 2
                        or not isinstance(message_id, str) or not message_id
                        or event.get("value") != 1
                        or event.get("retried") or event.get("providerRotated")):
                    pending.pop(key, None)
                    continue
                current.update(message=message_id, success_at=at)
            elif event.get("type") == "message_delta":
                pending.pop(key, None)
                if "message" not in current or not 0 <= at - current["success_at"] <= 2:
                    continue
                counters = (
                    event.get("inputTokens"), event.get("outputTokens"),
                    event.get("cacheReadInputTokens", event.get("cachedTokensRead")),
                    event.get("cachedTokensWritten"),
                )
                if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counters):
                    continue
                latency = round(current["duration"] * 1000)
                first_ms = round(current["first"] * 1000)
                if latency <= first_ms or counters[1] <= 0:
                    continue
                requests.append(RequestTiming(
                    key[1], current["message"], current.get("model") or "",
                    counters, current["end"], latency, first_ms,
                ))
    return requests


class TimingReader:
    """Cache parsed rotations by file metadata; keep no prompts or credentials."""

    def __init__(self):
        self.files = {}

    def read(self, directory, cancelled=None):
        check_cancelled(cancelled)
        try:
            if not directory.is_dir():
                self.files.clear()
                return [], ["Droid 速度数据不可用：本地运行日志目录不存在"]
            paths = sorted(path for path in directory.glob("droid-log-single.log*") if path.is_file())
        except OSError:
            self.files.clear()
            return [], ["Droid 速度数据暂不可用：本地运行日志目录无法读取"]
        self.files = {path: entry for path, entry in self.files.items() if path in paths}
        requests = {}
        conflicts = set()
        warnings = []
        for path in paths:
            check_cancelled(cancelled)
            try:
                stat = path.stat()
                signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
                cached = self.files.get(path)
                if cached is None or cached[0] != signature:
                    cached = (signature, read_file(path, cancelled))
                    self.files[path] = cached
                for request in cached[1]:
                    old = requests.get(request.evidence_id)
                    if old is not None and old != request:
                        conflicts.add(request.evidence_id)
                    requests[request.evidence_id] = request
            except OSError:
                self.files.pop(path, None)
                warnings.append(f"Droid 速度数据暂不可读：{path.name}")
        return [r for key, r in requests.items() if key not in conflicts], warnings


def within_sample(request, created_at, sample_start, sample_end):
    if sample_start is not None and sample_end is not None:
        # Only consider a request that completed inside this delta's observed
        # interval. Equal token tuples in neighboring intervals are not proof.
        return sample_start < request.ended_at <= sample_end
    # Older rows have only second-resolution import timestamps.
    return -1 < created_at - request.ended_at <= 120


def enrich(conn, requests, cancelled=None, *, record_table):
    """Fill only unknown timings; never change token counts, costs or dates."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(proxy_request_logs)")}
    if not {"latency_ms", "first_token_ms", "duration_ms", "is_streaming"} <= columns:
        return 0, ["当前数据库缺少速度字段，Droid 用量已同步，速度保持未知"]
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        request_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL UNIQUE,
        ended_at REAL NOT NULL, latency_ms INTEGER NOT NULL,
        first_token_ms INTEGER NOT NULL, source TEXT NOT NULL
    )""")
    conn.execute(f"""DELETE FROM {TABLE} WHERE NOT EXISTS (
        SELECT 1 FROM proxy_request_logs p WHERE p.request_id={TABLE}.request_id
        AND p.data_source='droid_session'
    )""")
    used = {row[0] for row in conn.execute(f"SELECT evidence_id FROM {TABLE}")}
    candidates = defaultdict(list)
    for request in requests:
        check_cancelled(cancelled)
        # Used evidence still counts toward ambiguity. Removing it first can
        # make a later duplicate import appear to match a different request.
        candidates[(request.session_id, request.tokens)].append(request)
    # record_table is the sync module's schema constant, never a config value.
    rows = conn.execute(f"""SELECT p.request_id,p.session_id,p.input_tokens,p.output_tokens,
        p.cache_read_tokens,p.cache_creation_tokens,p.created_at,p.request_model,
        m.sample_start,m.sample_end
        FROM proxy_request_logs p LEFT JOIN {record_table} m USING(request_id)
        WHERE p.data_source='droid_session'
        AND COALESCE(p.latency_ms,0)=0 AND COALESCE(p.first_token_ms,0)=0
        AND COALESCE(p.duration_ms,0)=0""").fetchall()
    matches = {}
    owners = defaultdict(list)
    for row in rows:
        check_cancelled(cancelled)
        possible = [request for request in candidates.get((row[1], tuple(row[2:6])), ())
                    if within_sample(request, row[6], row[8], row[9])
                    and (not row[7] or row[7].startswith("Droid ") or row[7] == request.model)]
        if len(possible) == 1 and possible[0].evidence_id not in used:
            matches[row[0]] = possible[0]
            owners[possible[0].evidence_id].append(row[0])
    count = 0
    for request_id, request in matches.items():
        check_cancelled(cancelled)
        if len(owners[request.evidence_id]) != 1:
            continue  # Ambiguous legacy/duplicate imports must remain unknown.
        conn.execute("""UPDATE proxy_request_logs SET latency_ms=?,first_token_ms=?,
            duration_ms=?,is_streaming=1 WHERE request_id=? AND data_source='droid_session'""",
            (request.latency_ms, request.first_token_ms,
             request.latency_ms - request.first_token_ms, request_id))
        conn.execute(f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?)", (
            request_id, request.evidence_id, request.ended_at,
            request.latency_ms, request.first_token_ms, "droid_local_request_metrics",
        ))
        count += 1
    return count, []
