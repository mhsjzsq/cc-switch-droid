"""Fetch Droid plan limits from the Factory API (same endpoints the Factory web app uses)."""

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.factory.ai"
APP = "https://app.factory.ai"


class QuotaError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # urllib otherwise copies Authorization even to a different host.
        # These fixed API endpoints must answer directly, including over HTTPS.
        fp.close()
        raise QuotaError("Factory 接口发生重定向，已停止请求以保护 API Key", code)


def _validated_key(value):
    key = value.strip()
    if any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise QuotaError("Factory API Key 格式不正确，请检查空白或非 ASCII 字符")
    return key


def _object(value, name):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise QuotaError(f"Factory 返回的 {name} 格式不正确")
    return value


def resolve_api_key(configured):
    key = (configured or "").strip()
    if key:
        return _validated_key(key)
    key = os.environ.get("FACTORY_API_KEY", "").strip()
    if key:
        return _validated_key(key)
    env_file = Path.home() / ".factory" / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"^\s*(?:export\s+)?FACTORY_API_KEY\s*=\s*(.*?)\s*$", line)
            if m:
                value = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("'\"")
                if value:
                    return _validated_key(value)
    except FileNotFoundError:
        pass
    return ""


def _get(base, route, key, timeout=12):
    key = _validated_key(key)
    req = urllib.request.Request(
        base + route,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Origin": APP,
            "Referer": APP + "/",
            "x-factory-client": "web-app",
            "User-Agent": "CC-Switch-Droid-Hook/2.2.9",
        },
    )
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(req, timeout=timeout) as resp:
            content = resp.read(1_048_577)
            if len(content) > 1_048_576:
                raise QuotaError("Factory 响应过大，已停止读取")
            body = json.loads(content.decode("utf-8"))
            if not isinstance(body, dict):
                raise QuotaError("Factory 返回的内容不是 JSON 对象")
            return body
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in (401, 403):
            raise QuotaError("API key 无效或没有权限（HTTP %d）" % e.code, e.code) from None
        if e.code == 429:
            raise QuotaError("Factory 接口限流（HTTP 429），稍后会自动重试", e.code) from None
        raise QuotaError("Factory 接口返回 HTTP %d" % e.code, e.code) from None
    except (ValueError, UnicodeError):
        raise QuotaError("Factory 返回了无法解析的 JSON 响应") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise QuotaError("连接 Factory 失败：%s" % getattr(e, "reason", e)) from None


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        value = float(v)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _window(entry, label, now_ms):
    entry = _object(entry, label)
    used = _num(entry.get("usedPercent"))
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
    limits = _object(body.get("limits"), "limits")
    windows = []
    for pool_name, prefix, optional in (("standard", "", False), ("core", "Core ", True)):
        pool = _object(limits.get(pool_name), pool_name)
        if not pool:
            continue
        if optional and not any(
            (_num(_object(pool.get(f), f).get("usedPercent")) or 0) > 0
            or _object(pool.get(f), f).get("windowEnd") is not None
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
    usage = _object(body.get("usage"), "usage")
    windows = []
    for field, label in (("standard", "Standard"), ("premium", "Premium")):
        b = _object(usage.get(field), field)
        if not b:
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
    org = _object(auth.get("organization"), "organization")
    sub = _object(org.get("subscription"), "subscription")
    orb = _object(sub.get("orbSubscription"), "orbSubscription")
    plan = _object(orb.get("plan"), "plan").get("name") or ""
    tier = sub.get("factoryTier") or ""
    plan = plan or tier
    if not isinstance(plan, str):
        raise QuotaError("Factory 返回的套餐名称格式不正确")
    if plan and not plan.lower().startswith("factory"):
        plan = "Factory " + plan
    profile = _object(auth.get("userProfile"), "userProfile")
    email = profile.get("email") or _object(profile.get("workosUser"), "workosUser").get("email") or ""
    if not isinstance(email, str):
        raise QuotaError("Factory 返回的账户名称格式不正确")
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
    except QuotaError as e:
        if e.status not in (404, 405, 501):
            raise
        usage = None
    if usage is None:
        usage = _parse_legacy(_get(API, "/api/organization/subscription/usage?useCache=true", key))
    if not usage["windows"] and usage["balance"] is None:
        raise QuotaError("Factory 没有返回额度数据")
    return {
        "plan": plan,
        "account": email,
        "windows": usage["windows"],
        "balance": usage["balance"],
        "error": None,
        "stale": False,
        "updatedAt": int(time.time() * 1000),
    }
