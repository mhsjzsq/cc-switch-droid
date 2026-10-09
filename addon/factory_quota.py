"""Fetch Droid plan limits from the Factory API (same endpoints the Factory web app uses)."""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.factory.ai"
APP = "https://app.factory.ai"


class QuotaError(Exception):
    pass


def resolve_api_key(configured):
    key = (configured or "").strip()
    if key:
        return key
    key = os.environ.get("FACTORY_API_KEY", "").strip()
    if key:
        return key
    env_file = Path.home() / ".factory" / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*(?:export\s+)?FACTORY_API_KEY\s*=\s*(.*?)\s*$", line)
            if m:
                value = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("'\"")
                if value:
                    return value
    except OSError:
        pass
    return ""


def _get(base, route, key, timeout=12):
    req = urllib.request.Request(
        base + route,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Origin": APP,
            "Referer": APP + "/",
            "x-factory-client": "web-app",
            "User-Agent": "CC-Switch-Droid-Addon",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise QuotaError("API key 无效或没有权限（HTTP %d）" % e.code) from None
        if e.code == 429:
            raise QuotaError("Factory 接口限流（HTTP 429），稍后会自动重试") from None
        raise QuotaError("Factory 接口返回 HTTP %d" % e.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise QuotaError("连接 Factory 失败：%s" % getattr(e, "reason", e)) from None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _window(entry, label, now_ms):
    used = _num((entry or {}).get("usedPercent"))
    if used is None:
        return None
    resets = None
    secs = _num(entry.get("secondsRemaining"))
    if secs is not None and secs > 0:
        resets = int(now_ms + secs * 1000)
    else:
        end = entry.get("windowEnd")
        end_num = _num(end)
        if end_num is not None:
            resets = int(end_num if end_num > 1e12 else end_num * 1000)
        elif isinstance(end, str):
            from datetime import datetime
            try:
                resets = int(datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp() * 1000)
            except ValueError:
                resets = None
        if resets is not None and resets <= now_ms:
            used, resets = 0.0, None
    return {"label": label, "usedPercent": max(0.0, min(100.0, used)), "resetsAt": resets}


def _parse_limits(body, now_ms):
    if not body or body.get("usesTokenRateLimitsBilling") is not True:
        return None
    limits = body.get("limits") or {}
    windows = []
    for pool_name, prefix, optional in (("standard", "", False), ("core", "Core ", True)):
        pool = limits.get(pool_name)
        if not isinstance(pool, dict):
            continue
        if optional and not any(
            (_num((pool.get(f) or {}).get("usedPercent")) or 0) > 0
            or (pool.get(f) or {}).get("windowEnd") is not None
            for f in ("fiveHour", "weekly", "monthly")
        ):
            continue
        for field, label in (("fiveHour", "5 小时"), ("weekly", "每周"), ("monthly", "每月")):
            w = _window(pool.get(field), prefix + label, now_ms)
            if w:
                windows.append(w)
    cents = _num(body.get("extraUsageBalanceCents"))
    return {"windows": windows, "balance": max(0.0, cents / 100) if cents is not None else None}


def _parse_legacy(body):
    usage = (body or {}).get("usage") or {}
    windows = []
    for field, label in (("standard", "Standard"), ("premium", "Premium")):
        b = usage.get(field)
        if not isinstance(b, dict):
            continue
        ratio = _num(b.get("usedRatio"))
        used = _num(b.get("userTokens"))
        allowance = _num(b.get("totalAllowance"))
        if ratio is not None and 0 <= ratio <= 1.001:
            pct = ratio * 100
        elif used is not None and allowance:
            pct = used / allowance * 100
        else:
            continue
        windows.append({"label": label, "usedPercent": max(0.0, min(100.0, pct)), "resetsAt": None})
    return {"windows": windows, "balance": None}


def _plan(auth):
    org = (auth or {}).get("organization") or {}
    sub = org.get("subscription") or {}
    plan = (((sub.get("orbSubscription") or {}).get("plan")) or {}).get("name") or ""
    tier = sub.get("factoryTier") or ""
    plan = plan or tier
    if plan and not plan.lower().startswith("factory"):
        plan = "Factory " + plan
    profile = (auth or {}).get("userProfile") or {}
    email = profile.get("email") or (profile.get("workosUser") or {}).get("email") or ""
    return plan, email


def fetch(key, auth_cache):
    """Return quota dict. auth_cache is a dict reused between calls to avoid refetching identity."""
    now_ms = int(time.time() * 1000)
    if not auth_cache.get("body") or now_ms - auth_cache.get("at", 0) > 30 * 60 * 1000:
        auth_cache["body"] = _get(API, "/api/app/auth/me", key)
        auth_cache["at"] = now_ms
    plan, email = _plan(auth_cache["body"])
    usage = None
    try:
        usage = _parse_limits(_get(API, "/api/billing/limits", key), now_ms)
    except QuotaError:
        usage = None
    if usage is None:
        usage = _parse_legacy(_get(API, "/api/organization/subscription/usage?useCache=true", key))
    return {
        "plan": plan,
        "account": email,
        "windows": usage["windows"],
        "balance": usage["balance"],
        "error": None if usage["windows"] or usage["balance"] is not None else "Factory 没有返回额度数据",
        "updatedAt": now_ms,
    }
