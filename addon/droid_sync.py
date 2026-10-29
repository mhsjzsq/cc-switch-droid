"""Reconcile cumulative counters against rows in the destination database.

Imported rows are the accounting checkpoint. Attribution metadata and sampling
snapshots commit in the SAME SQLite transaction. sync_state.json is not read.
"""

import json
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from concurrent.futures import CancelledError
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException, InvalidOperation

import droid_timing
import droid_models

APP_TYPE = "droid"
DATA_SOURCE = "droid_session"
PROVIDER_ID = "_droid_session"
FIELDS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens")
TOKEN_COLUMNS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens")
SNAPSHOT_TABLE = "droid_addon_snapshots"
RECORD_TABLE = "droid_addon_records"


@dataclass
class SyncResult:
    inserted: int = 0
    timings_updated: int = 0
    models_updated: int = 0
    costs_updated: int = 0
    warnings: list = field(default_factory=list)


def connect(db_path, readonly=False):
    # Refuse to create a database at a mistaken path.
    uri = db_path.resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    return sqlite3.connect(uri, uri=True, timeout=30)


def _ensure_schema(conn):
    required = {
        "request_id", "provider_id", "app_type", "model", "request_model",
        "pricing_model", *TOKEN_COLUMNS, "input_cost_usd", "output_cost_usd",
        "cache_read_cost_usd", "cache_creation_cost_usd", "total_cost_usd",
        "latency_ms", "status_code", "session_id", "provider_type", "is_streaming",
        "cost_multiplier", "created_at", "data_source", "input_token_semantics",
    }
    present = {r[1] for r in conn.execute("PRAGMA table_info(proxy_request_logs)")}
    if required - present:
        raise ValueError("CC Switch 数据库结构不兼容，未写入任何用量")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE} (
        session_id TEXT PRIMARY KEY, totals_json TEXT NOT NULL,
        observed_at REAL NOT NULL
    )""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {RECORD_TABLE} (
        request_id TEXT PRIMARY KEY, time_quality TEXT NOT NULL,
        model_quality TEXT NOT NULL, cost_known INTEGER NOT NULL,
        note TEXT NOT NULL, sample_start REAL, sample_end REAL
    )""")
    record_columns = {r[1] for r in conn.execute(f"PRAGMA table_info({RECORD_TABLE})")}
    for name in ("sample_start", "sample_end"):
        if name not in record_columns:
            conn.execute(f"ALTER TABLE {RECORD_TABLE} ADD COLUMN {name} REAL")
    # Preserve legacy rows verbatim, including unverified timing estimates.
    conn.execute(f"""INSERT INTO {RECORD_TABLE}
        (request_id,time_quality,model_quality,cost_known,note)
        SELECT p.request_id, 'legacy', 'unknown', 0, '旧版导入：日期、模型、费用与估算速度未经核实'
        FROM proxy_request_logs p
        WHERE p.data_source = ? AND NOT EXISTS (
            SELECT 1 FROM {RECORD_TABLE} m WHERE m.request_id = p.request_id
        )""", (DATA_SOURCE,))
    conn.execute(f"""DELETE FROM {RECORD_TABLE} WHERE NOT EXISTS (
        SELECT 1 FROM proxy_request_logs p
        WHERE p.request_id = {RECORD_TABLE}.request_id AND p.data_source = ?
    )""", (DATA_SOURCE,))


def _counters(usage):
    if not isinstance(usage, dict) or any(k not in usage for k in FIELDS):
        raise ValueError("tokenUsage 缺少累计字段")
    values = []
    for key in FIELDS:
        value = usage[key]
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise ValueError(f"{key} 必须是 SQLite 可存储的非负整数")
        values.append(value)
    return tuple(values)


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise CancelledError()


def _read_sources(sessions_dir, result, cancelled):
    sources = {}
    seen = set()
    duplicates = set()
    for path in sessions_dir.rglob("*.settings.json"):
        _check_cancelled(cancelled)
        sid = path.name[:-len(".settings.json")]
        # A second file is ambiguous even if it is incomplete or unreadable.
        # Detect identity collisions before parsing either copy's counters.
        if sid in seen:
            duplicates.add(sid)
        seen.add(sid)
        try:
            before = path.stat()
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            after = path.stat()
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                continue
            if not isinstance(data, dict):
                raise ValueError("会话设置必须是 JSON 对象")
            usage = data.get("tokenUsage")
            if not usage:
                continue
            totals = _counters(usage)
        except (OSError, ValueError) as e:
            result.warnings.append(f"跳过会话 {sid}：{e}")
            continue
        if sid not in sources:
            sources[sid] = (path, totals, time.time())
    for sid in duplicates:
        sources.pop(sid, None)
        result.warnings.append(f"跳过重复会话 ID：{sid}")
    return sources


def _session_model(path, cancelled):
    """Only attribute counters when the entire transcript has one known model.

    Messages may have model IDs without token counts. Splitting cumulative
    counters for a mixed-model session would invent precision we do not have.
    """
    models = set()
    complete = True
    try:
        before = path.stat()
        with path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                _check_cancelled(cancelled)
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        complete = False
                        continue
                    message = record.get("message")
                    if record.get("type") != "message" or not isinstance(message, dict):
                        continue
                    if message.get("role") != "assistant":
                        continue
                    model = message.get("modelId")
                    if (isinstance(model, str) and model.strip()
                            and model.strip().lower() not in {"auto", "unknown", "default"}):
                        models.add(model.strip())
                    else:
                        complete = False
                except ValueError:
                    complete = False
        after = path.stat()
        complete = complete and (before.st_mtime_ns, before.st_size) == (
            after.st_mtime_ns, after.st_size
        )
    except (OSError, UnicodeError):
        complete = False
    if len(models) > 1:
        return "Droid 混合模型", "mixed"
    # The configured model is a current preference and may change after these
    # messages were produced. A complete transcript is the stronger evidence.
    if complete and len(models) == 1:
        return next(iter(models)), "single"
    return "Droid 未知模型", "unknown"


def load_pricing(conn):
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_pricing'"
    ).fetchone():
        return {}
    rows = conn.execute(
        "SELECT model_id, input_cost_per_million, output_cost_per_million,"
        " cache_read_cost_per_million, cache_creation_cost_per_million FROM model_pricing"
    )
    prices = {}
    for row in rows:
        try:
            values = tuple(Decimal(str(v)) for v in row[1:])
            if all(v.is_finite() and v >= 0 and math.isfinite(float(v)) for v in values):
                prices[row[0]] = values
        except InvalidOperation:
            continue
    return prices


def find_price(pricing, model):
    # A prefix match could select the price of another version/model.
    return pricing.get(model)


def _estimate_costs(counts, price):
    if price is None:
        return None
    try:
        costs = [Decimal(n) * p / Decimal(1_000_000) for n, p in zip(counts, price)]
        return costs if math.isfinite(float(sum(costs))) else None
    except (DecimalException, ValueError, OverflowError):
        return None


def _repair_costs(conn, prices, cancelled):
    """Reprice unpriced single-model imports when exact pricing becomes available."""
    rows = conn.execute(f"""SELECT p.request_id,p.request_model,p.model,
        p.input_tokens,p.output_tokens,p.cache_read_tokens,p.cache_creation_tokens,m.note
        FROM proxy_request_logs p JOIN {RECORD_TABLE} m USING(request_id)
        WHERE p.data_source=? AND m.model_quality='single' AND m.cost_known=0
    """, (DATA_SOURCE,)).fetchall()
    count = 0
    for request_id, model, label, inp, out, cr, cc, note in rows:
        _check_cancelled(cancelled)
        counts = (inp, out, cr, cc)
        if any(type(n) is not int or n < 0 for n in counts):
            continue
        costs = _estimate_costs(counts, find_price(prices, model))
        if costs is None:
            continue
        conn.execute("""UPDATE proxy_request_logs SET model=?,pricing_model=?,
            input_cost_usd=?,output_cost_usd=?,cache_read_cost_usd=?,cache_creation_cost_usd=?,
            total_cost_usd=? WHERE request_id=?""", (
                label.removesuffix(" [费用未知]"), model,
                *(format(c, "f") for c in costs), format(sum(costs), "f"), request_id,
            ))
        conn.execute(f"UPDATE {RECORD_TABLE} SET cost_known=1,note=? WHERE request_id=?", (
            note.replace("费用未知；原生统计中的 0 仅为数据库占位值", "费用已按当前数据库精确匹配单价补算"),
            request_id,
        ))
        count += 1
    return count


def _previous_snapshot(row, accounted):
    if row is None:
        return None
    try:
        totals, observed = row
        if (isinstance(observed, bool) or not isinstance(observed, (int, float))
                or not math.isfinite(observed) or observed <= 0):
            return None
        datetime.fromtimestamp(observed)  # Reject timestamps unsupported on this platform.
        values = json.loads(totals)
        if (not isinstance(values, list) or len(values) != len(FIELDS)
                or any(type(n) is not int or n < 0 for n in values)):
            return None
        return observed if tuple(values) == accounted else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _insert(conn, sid, delta, model, model_quality, time_quality, prices, now, sample_start):
    price = find_price(prices, model) if model_quality == "single" else None
    costs = _estimate_costs(delta, price)
    known = costs is not None
    if costs is None:
        costs = [Decimal(0)] * 4
    notes = []
    if time_quality == "unallocated":
        notes.append("历史/补录汇总，日期未分配；记录时间为导入时间")
    else:
        notes.append("两次本地采样之间的增量，按采样日期统计")
    if not known:
        notes.append("费用未知；原生统计中的 0 仅为数据库占位值")
    label = model
    if time_quality == "unallocated":
        label += " [日期未分配]"
    if not known:
        label += " [费用未知]"
    request_id = f"{DATA_SOURCE}:v2:{uuid.uuid4()}"
    conn.execute(
        "INSERT INTO proxy_request_logs ("
        "request_id,provider_id,app_type,model,request_model,pricing_model,"
        "input_tokens,output_tokens,cache_read_tokens,cache_creation_tokens,"
        "input_cost_usd,output_cost_usd,cache_read_cost_usd,cache_creation_cost_usd,"
        "total_cost_usd,latency_ms,status_code,session_id,provider_type,"
        "is_streaming,cost_multiplier,created_at,data_source,input_token_semantics"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (request_id, PROVIDER_ID, APP_TYPE, label, model, model if known else "",
         *delta, *(format(c, "f") for c in costs), format(sum(costs), "f"),
         0, 200, sid, DATA_SOURCE, 0, "1.0", int(now), DATA_SOURCE, 0),
    )
    conn.execute(
        f"INSERT INTO {RECORD_TABLE} "
        "(request_id,time_quality,model_quality,cost_known,note,sample_start,sample_end) "
        "VALUES (?,?,?,?,?,?,?)",
        (request_id, time_quality, model_quality, int(known), "；".join(notes), sample_start, now),
    )


def _imported_totals(conn, cancelled=None):
    # SQLite SUM can overflow on duplicated/corrupt historic counters. Accumulate
    # Python integers, and quarantine invalid sessions without blocking others.
    totals = {}
    for sid, *counts in conn.execute(
        f"SELECT session_id,{','.join(TOKEN_COLUMNS)} FROM proxy_request_logs WHERE data_source=?",
        (DATA_SOURCE,),
    ):
        _check_cancelled(cancelled)
        old = totals.get(sid, (0, 0, 0, 0))
        if old is None or any(type(n) is not int or n < 0 for n in counts):
            totals[sid] = None
        else:
            totals[sid] = tuple(a + b for a, b in zip(old, counts))
    return totals


def sync(sessions_dir, db_path, *, cancelled=None, timings=(), model_requests=()):
    _check_cancelled(cancelled)
    result = SyncResult()
    if not sessions_dir.is_dir():
        result.warnings.append(f"Droid 会话目录不存在：{sessions_dir}")
        return result
    if not db_path.is_file():
        result.warnings.append(f"CC Switch 数据库不存在：{db_path}")
        return result
    sources = _read_sources(sessions_dir, result, cancelled)
    conn = connect(db_path)
    try:
        # Read large transcripts before taking SQLite's writer lock.
        preliminary = _imported_totals(conn, cancelled)
        models = {}
        for sid, (path, totals, sampled_at) in sources.items():
            _check_cancelled(cancelled)
            old = preliminary.get(sid, (0, 0, 0, 0))
            if old is not None and all(cur >= recorded for cur, recorded in zip(totals, old)) and totals != old:
                models[sid] = _session_model(path.with_name(sid + ".jsonl"), cancelled)
        _check_cancelled(cancelled)
        conn.execute("BEGIN IMMEDIATE")
        _check_cancelled(cancelled)
        _ensure_schema(conn)
        # Re-read while holding the lock: another writer may have changed rows.
        imported = _imported_totals(conn, cancelled)
        snapshots = {
            r[0]: r[1:] for r in conn.execute(
                f"SELECT session_id,totals_json,observed_at FROM {SNAPSHOT_TABLE}"
            )
        }
        prices = load_pricing(conn)
        for sid, (path, totals, sampled_at) in sources.items():
            _check_cancelled(cancelled)
            accounted = imported.get(sid, (0, 0, 0, 0))
            if accounted is None:
                result.warnings.append(f"会话 {sid} 的已导入 Token 数据无效，保留原记录并跳过该会话")
                continue
            if any(cur < old for cur, old in zip(totals, accounted)):
                result.warnings.append(
                    f"会话 {sid} 的累计值低于已导入值，可能回滚或旧版重复；保留原记录，等待核对"
                )
                continue
            previous = _previous_snapshot(snapshots.get(sid), accounted)
            delta = tuple(cur - old for cur, old in zip(totals, accounted))
            if any(delta):
                bounded_today = (
                    previous is not None and previous <= sampled_at
                    and datetime.fromtimestamp(previous).date() == datetime.fromtimestamp(sampled_at).date()
                )
                quality = "observed" if bounded_today else "unallocated"
                model, model_quality = models.get(sid, ("Droid 未知模型", "unknown"))
                runtime_models = {
                    r.model for r in model_requests if r.session_id == sid
                    and r.ended_at <= sampled_at
                    and (previous is None or previous < r.ended_at)
                }
                # Auxiliary calls can be billed without a transcript message.
                # Never charge their aggregate entirely to the main model.
                if len(runtime_models | ({model} if model_quality == "single" else set())) > 1:
                    model, model_quality = "Droid 混合模型", "mixed"
                _insert(conn, sid, delta, model, model_quality, quality, prices, sampled_at,
                        previous if previous is not None and previous <= sampled_at else None)
                result.inserted += 1
            conn.execute(
                f"INSERT INTO {SNAPSHOT_TABLE} VALUES (?,?,?) ON CONFLICT(session_id)"
                " DO UPDATE SET totals_json=excluded.totals_json,observed_at=excluded.observed_at",
                (sid, json.dumps(totals), sampled_at),
            )
        result.models_updated = droid_models.repair(
            conn, [r for r in model_requests if r.session_id in sources], RECORD_TABLE, cancelled,
        )
        result.costs_updated = _repair_costs(conn, prices, cancelled)
        result.timings_updated, timing_warnings = droid_timing.enrich(
            conn, [r for r in timings if r.session_id in sources], cancelled,
            record_table=RECORD_TABLE,
        )
        result.warnings.extend(timing_warnings)
        _check_cancelled(cancelled)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return result


def today_usage(db_path):
    day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    conn = connect(db_path, readonly=True)
    try:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (RECORD_TABLE,)
        ).fetchone():
            return {"available": False, "error": "等待首次同步完成，旧版统计尚未核对"}
        row = conn.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(p.input_tokens),0),
                COALESCE(SUM(p.output_tokens),0), COALESCE(SUM(p.cache_read_tokens),0),
                COALESCE(SUM(p.cache_creation_tokens),0),
                COALESCE(SUM(CASE WHEN m.cost_known=1 THEN CAST(p.total_cost_usd AS REAL) ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN m.cost_known=0 THEN 1 ELSE 0 END),0)
            FROM proxy_request_logs p JOIN {RECORD_TABLE} m USING(request_id)
            WHERE p.data_source=? AND m.time_quality='observed'
                AND p.created_at>=? AND p.created_at<?
        """, (DATA_SOURCE, start, end)).fetchone()
        unpriced = conn.execute(f"""
            SELECT m.model_quality,p.request_model,COUNT(*)
            FROM proxy_request_logs p JOIN {RECORD_TABLE} m USING(request_id)
            WHERE p.data_source=? AND m.time_quality='observed' AND m.cost_known=0
                AND p.created_at>=? AND p.created_at<?
            GROUP BY m.model_quality,p.request_model
        """, (DATA_SOURCE, start, end)).fetchall()
        prices = load_pricing(conn) if any(r[0] == "single" for r in unpriced) else {}
        excluded = conn.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(p.input_tokens+p.output_tokens+
                p.cache_read_tokens+p.cache_creation_tokens),0)
            FROM proxy_request_logs p LEFT JOIN {RECORD_TABLE} m USING(request_id)
            WHERE p.data_source=? AND (m.time_quality IS NULL OR m.time_quality<>'observed')
        """, (DATA_SOURCE,)).fetchone()
    finally:
        conn.close()
    records, inp, out, cr, cc, cost, unknown = row
    valid_cost = math.isfinite(cost)
    reasons = []
    for quality, model, count in unpriced:
        reason = {
            "inferred": f"{model} 仅推定了模型，缺少逐请求 Token 证据",
            "mixed": "多个模型共用累计 Token，无法可靠拆分费用",
            "unknown": "未识别出实际模型，缺少完整对话或可匹配的请求日志",
        }.get(quality)
        if reason is None:
            reason = (
                f"{model} 缺少有效的精确匹配价格"
                if find_price(prices, model) is None else f"{model} 费用计算超出可显示范围"
            )
        reasons.append({"reason": reason, "records": count})
    return {
        "available": True, "date": day.date().isoformat(), "records": records, "input": inp, "output": out,
        "cacheRead": cr, "cacheCreation": cc, "tokens": inp + out + cr + cc,
        "cost": round(cost, 6) if unknown == 0 and valid_cost else None,
        "knownCost": round(cost, 6) if valid_cost else None, "unknownCostRecords": unknown,
        "knownCostRecords": records - unknown, "unknownCostReasons": reasons,
        "costError": None if valid_cost else "历史费用汇总超出可显示范围，请检查原版数据库记录",
        "unallocatedRecords": excluded[0], "unallocatedTokens": excluded[1],
    }


def remove_imported(db_path):
    """Remove records and their checkpoints together from exactly one database."""
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "DELETE FROM proxy_request_logs WHERE data_source=?", (DATA_SOURCE,)
        ).rowcount
        for table in (SNAPSHOT_TABLE, RECORD_TABLE, droid_timing.TABLE, droid_models.TABLE):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        return count
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
