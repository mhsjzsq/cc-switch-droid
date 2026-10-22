"""Model evidence from completed local requests, including auxiliary calls.

Session titles are billed in cumulative counters but need not appear as
assistant transcript messages. Runtime-only attribution remains explicitly
inferred: these metrics do not contain the four per-request token counters.
"""

from dataclasses import dataclass

import droid_timing

TABLE = "droid_hook_models"
UNKNOWN = "Droid 未知模型"


@dataclass(frozen=True)
class ModelRequest:
    session_id: str
    message_id: str
    model: str
    started_at: float
    ended_at: float
    call_type: str

    @property
    def evidence_id(self):
        return self.session_id + "/" + self.message_id


def read_file(path, cancelled):
    pending = {}
    requests = []
    with path.open(encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            droid_timing.check_cancelled(cancelled)
            if not line.endswith("\n"):
                continue
            parsed = droid_timing.parse_line(line)
            if parsed is None:
                continue
            at, trace, event = parsed
            model = event.get("modelId")
            # tags.modelId describes the parent agent, not an auxiliary model.
            if not isinstance(model, str) or not model.strip():
                continue
            model = model.strip()
            if model.lower() in {"auto", "unknown", "default"}:
                continue
            key = (*trace, model)
            metric = event.get("metric")
            if metric == droid_timing.DURATION:
                duration = droid_timing.seconds(event.get("value"))
                if duration is not None and duration > 0 and not event.get("usedFallback"):
                    call_type = event.get("messageCallType")
                    pending[key] = (at, at - duration, call_type if isinstance(call_type, str) else "")
                else:
                    pending.pop(key, None)
            elif metric == droid_timing.SUCCESS:
                duration = pending.pop(key, None)
                message = event.get("assistantMessageId")
                if (duration is None or not 0 <= at - duration[0] <= 2
                        or event.get("value") != 1 or event.get("retried") or event.get("providerRotated")
                        or not isinstance(message, str) or not message):
                    continue
                requests.append(ModelRequest(trace[1], message, model, duration[1], at, duration[2]))
    return requests


class ModelReader(droid_timing.TimingReader):
    def __init__(self):
        super().__init__(parser=read_file, label="模型")


def repair(conn, requests, record_table, cancelled=None):
    """Annotate uniquely owned, bounded unknown rows without changing accounting."""
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        request_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL UNIQUE,
        model TEXT NOT NULL, completed_at REAL NOT NULL, call_type TEXT NOT NULL
    )""")
    conn.execute(f"""DELETE FROM {TABLE} WHERE NOT EXISTS (
        SELECT 1 FROM proxy_request_logs p WHERE p.request_id={TABLE}.request_id
            AND p.data_source='droid_session'
    )""")
    used = {row[0] for row in conn.execute(f"SELECT evidence_id FROM {TABLE}")}
    # Include known rows in ownership checks: one request must not explain a
    # second, overlapping aggregate just because its model is still unknown.
    rows = conn.execute(f"""SELECT p.request_id,p.session_id,p.request_model,p.model,
        m.time_quality,m.model_quality,m.sample_start,m.sample_end
        FROM proxy_request_logs p JOIN {record_table} m USING(request_id)
        WHERE p.data_source='droid_session'""").fetchall()
    by_session = {}
    for request in requests:
        by_session.setdefault(request.session_id, []).append(request)
    matches, owners = {}, {}
    for row in rows:
        droid_timing.check_cancelled(cancelled)
        candidates = [r for r in by_session.get(row[1], ())
                      if droid_timing.within_sample(r, row[6], row[7])]
        for candidate in candidates:
            owners.setdefault(candidate.evidence_id, set()).add(row[0])
        if (row[2] == UNKNOWN and row[5] == "unknown" and row[4] == "observed"
                and len(candidates) == 1 and candidates[0].started_at >= row[6]
                and candidates[0].evidence_id not in used):
            matches[row[0]] = (row, candidates[0])
    count = 0
    for request_id, (row, request) in matches.items():
        droid_timing.check_cancelled(cancelled)
        if len(owners[request.evidence_id]) != 1:
            continue
        # Keep date/cost suffixes, token counts, money, IDs and timing untouched.
        label = row[3].replace(UNKNOWN, request.model + " [模型推定]", 1)
        conn.execute("UPDATE proxy_request_logs SET model=?,request_model=? WHERE request_id=?",
                     (label, request.model, request_id))
        note = "模型推定：同一采样区间唯一完整成功请求，依据顶层 modelId；无逐请求 Token 证据，费用与耗时不回填"
        if request.call_type == "session-title-generation":
            note += "；请求用途为会话标题生成"
        conn.execute(f"UPDATE {record_table} SET model_quality='inferred',note=note || '；' || ? WHERE request_id=?",
                     (note, request_id))
        conn.execute(f"INSERT INTO {TABLE} VALUES (?,?,?,?,?)", (
            request_id, request.evidence_id, request.model, request.ended_at, request.call_type,
        ))
        count += 1
    return count
