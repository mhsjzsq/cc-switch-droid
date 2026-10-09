"""Copy Droid (Factory) session token usage into the CC Switch usage database.

Droid only stores cumulative per-session totals in
~/.factory/sessions/<project>/<session>.settings.json, so each run records the
difference since the previous run as one row in proxy_request_logs.
"""

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

APP_TYPE = "droid"
DATA_SOURCE = "droid_session"
PROVIDER_ID = "_droid_session"
FIELDS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens")


def load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sessions": {}}


def save_state(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def parse_ts_ms(ts):
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except (AttributeError, ValueError):
        return None


def scan_transcript(jsonl_path, after_ms):
    """Return (newest record ms, model generation ms after after_ms, newest assistant ms).

    Generation time of an assistant message is measured from the preceding
    message (user prompt or tool result) to the assistant message, so tool
    execution time is excluded.
    """
    last_ms = None
    gen_ms = 0
    last_asst_ms = after_ms
    prev_ms = None
    try:
        with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                ts = parse_ts_ms(rec.get("timestamp"))
                if ts is None:
                    continue
                last_ms = ts
                if rec.get("type") != "message":
                    continue
                role = (rec.get("message") or {}).get("role")
                if role == "assistant" and ts > after_ms:
                    if prev_ms is not None and ts >= prev_ms:
                        gen_ms += ts - prev_ms
                    last_asst_ms = max(last_asst_ms, ts)
                prev_ms = ts
    except OSError:
        pass
    return last_ms, gen_ms, last_asst_ms


def load_pricing(conn):
    rows = conn.execute(
        "SELECT model_id, input_cost_per_million, output_cost_per_million,"
        " cache_read_cost_per_million, cache_creation_cost_per_million FROM model_pricing"
    ).fetchall()
    return {r[0]: tuple(float(x or 0) for x in r[1:]) for r in rows}


def find_price(pricing, model):
    if model in pricing:
        return pricing[model]
    for key, price in pricing.items():
        if key.startswith(model + "-"):
            return price
    return None


def fmt(x):
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s or "0"


def sync(sessions_dir, db_path, state_path):
    """Run one sync pass. Returns the number of inserted rows."""
    if not sessions_dir.is_dir() or not db_path.is_file():
        return 0

    state = load_state(state_path)
    sessions = state.setdefault("sessions", {})
    pending = []

    for settings_path in sessions_dir.rglob("*.settings.json"):
        sid = settings_path.name[: -len(".settings.json")]
        try:
            mtime = settings_path.stat().st_mtime
        except OSError:
            continue
        prev = sessions.get(sid)
        if prev and prev.get("mtime") == mtime:
            continue
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # possibly mid-write; retry next run

        # tokenUsage excludes subagent sessions, which have their own files.
        usage = data.get("tokenUsage") or {}
        cur = {k: int(usage.get(k) or 0) for k in FIELDS}
        last = (prev or {}).get("totals", {})
        delta = {k: max(0, cur[k] - int(last.get(k, 0))) for k in FIELDS}
        seq = (prev or {}).get("seq", 0)
        gen_after = (prev or {}).get("gen_after_ms", 0)
        new_entry = {"mtime": mtime, "totals": cur, "seq": seq, "gen_after_ms": gen_after}

        if any(delta.values()):
            last_ms, gen_ms, last_asst_ms = scan_transcript(
                settings_path.with_name(sid + ".jsonl"), gen_after
            )
            created_at = last_ms // 1000 if last_ms else int(mtime)
            if prev and prev.get("created_at") and created_at < prev["created_at"]:
                created_at = int(time.time())
            new_entry["seq"] = seq + 1
            new_entry["created_at"] = created_at
            new_entry["gen_after_ms"] = last_asst_ms
            pending.append((sid, data.get("model") or "unknown", delta, created_at, seq + 1, gen_ms))
        elif prev:
            new_entry["created_at"] = prev.get("created_at")
        sessions[sid] = new_entry

    if pending:
        conn = sqlite3.connect(str(db_path), timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            pricing = load_pricing(conn)
            with conn:
                for sid, model, d, created_at, seq, gen_ms in pending:
                    price = find_price(pricing, model) or (0.0, 0.0, 0.0, 0.0)
                    costs = [
                        d["inputTokens"] * price[0] / 1e6,
                        d["outputTokens"] * price[1] / 1e6,
                        d["cacheReadTokens"] * price[2] / 1e6,
                        d["cacheCreationTokens"] * price[3] / 1e6,
                    ]
                    conn.execute(
                        "INSERT OR IGNORE INTO proxy_request_logs ("
                        " request_id, provider_id, app_type, model, request_model, pricing_model,"
                        " input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,"
                        " input_cost_usd, output_cost_usd, cache_read_cost_usd, cache_creation_cost_usd,"
                        " total_cost_usd, latency_ms, status_code, session_id, provider_type,"
                        " is_streaming, cost_multiplier, created_at, data_source, input_token_semantics"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            f"{DATA_SOURCE}:{sid}:{seq}", PROVIDER_ID, APP_TYPE, model, model, "",
                            d["inputTokens"], d["outputTokens"], d["cacheReadTokens"], d["cacheCreationTokens"],
                            fmt(costs[0]), fmt(costs[1]), fmt(costs[2]), fmt(costs[3]),
                            fmt(sum(costs)), gen_ms, 200, sid, DATA_SOURCE,
                            1, "1.0", created_at, DATA_SOURCE, 0,
                        ),
                    )
        finally:
            conn.close()

    save_state(state_path, state)
    return len(pending)


def today_usage(db_path):
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0),"
            " COALESCE(SUM(cache_read_tokens),0), COALESCE(SUM(cache_creation_tokens),0),"
            " COALESCE(SUM(CAST(total_cost_usd AS REAL)),0)"
            " FROM proxy_request_logs WHERE data_source = ? AND created_at >= ?",
            (DATA_SOURCE, int(start)),
        ).fetchone()
    finally:
        conn.close()
    records, inp, out, cr, cc, cost = row
    return {
        "records": records, "input": inp, "output": out, "cacheRead": cr,
        "cacheCreation": cc, "tokens": inp + out + cr + cc, "cost": round(cost, 6),
    }
