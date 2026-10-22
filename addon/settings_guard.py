"""Preserve native settings before launch; never repair or overwrite them.

CC Switch 4.0.12 reads device settings from ~/.cc-switch/settings.json,
independently of the usage database path. Invalid JSON makes it load defaults.
This guard catches JSON damage, not every native settings schema constraint.
"""

import json
import uuid
from datetime import datetime, timezone

import config


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON 对象含重复字段")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("JSON 含非标准数值")


def preserve_before_launch(directory):
    path = config.native_settings_path()
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None  # A first installation has no settings to preserve.
    except OSError as error:
        raise RuntimeError(f"无法读取原版设置，未启动 CC Switch：{path}") from error

    problem = None
    try:
        settings = json.loads(
            content.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(settings, dict):
            raise ValueError("设置内容必须是 JSON 对象")
    except json.JSONDecodeError as error:
        problem = f"JSON 格式错误（第 {error.lineno} 行，第 {error.colno} 列）"
    except UnicodeError:
        problem = "设置文件不是有效的 UTF-8 文本"
    except ValueError as error:
        problem = str(error)

    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    kind = "invalid" if problem else "before-launch"
    backup = directory / f"{kind}-{stamp}-{uuid.uuid4().hex[:8]}.json"
    with backup.open("xb") as stream:
        stream.write(content)
    if problem:
        raise RuntimeError(
            f"原版设置损坏，已阻止本次启动，避免原版使用默认设置覆盖旧内容。\n"
            f"{problem}\n原文件保持不变：{path}\n已保存副本：{backup}\n"
            "请先检查或恢复有效设置；Hook 不会自动恢复或重置。"
        )
    return backup
