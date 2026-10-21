"""Configuration for a single launcher-owned CC Switch session."""

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DEFAULTS = {
    "ccSwitchExecutable": "",
    "ccSwitchArguments": [],
    "factoryApiKey": "",
    "quotaRefreshSeconds": 60,
    "ccSwitchDbPath": "",
    "droidSessionsDir": "",
    "droidLogsDir": "",
    "startupTimeoutSeconds": 45,
}


def load():
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("config.json 必须是 JSON 对象")
    cfg = dict(DEFAULTS, **data)
    for name in ("ccSwitchExecutable", "factoryApiKey", "ccSwitchDbPath", "droidSessionsDir", "droidLogsDir"):
        if not isinstance(cfg[name], str):
            raise ValueError(f"{name} 必须是字符串")
        cfg[name] = cfg[name].strip()
        if "\0" in cfg[name]:
            raise ValueError(f"{name} 不能包含空字符")
    if any(c in cfg["factoryApiKey"] for c in "\r\n"):
        raise ValueError("factoryApiKey 不能包含换行")
    for name, minimum, maximum in (
        ("quotaRefreshSeconds", 15, 86400), ("startupTimeoutSeconds", 10, 120)
    ):
        value = cfg[name]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{name} 必须是 {minimum} 到 {maximum} 之间的整数")
    args = cfg["ccSwitchArguments"]
    if not isinstance(args, list) or any(not isinstance(arg, str) or "\0" in arg for arg in args):
        raise ValueError("ccSwitchArguments 必须是字符串数组")
    if any(arg.lower().startswith(("--remote-debugging", "--user-data-dir")) for arg in args):
        raise ValueError("调试参数由启动器管理，不能通过 ccSwitchArguments 覆盖")
    return cfg


def resolve_path(value, default):
    path = Path(os.path.expandvars(value)).expanduser() if value else default
    return (path if path.is_absolute() else ROOT / path).resolve()


def db_path(cfg):
    return resolve_path(cfg["ccSwitchDbPath"], Path.home() / ".cc-switch" / "cc-switch.db")


def sessions_dir(cfg):
    return resolve_path(cfg["droidSessionsDir"], Path.home() / ".factory" / "sessions")


def logs_dir(cfg):
    return resolve_path(cfg["droidLogsDir"], sessions_dir(cfg).parent / "logs")


def executable(cfg):
    configured = cfg["ccSwitchExecutable"]
    if configured:
        candidate = resolve_path(configured, ROOT)
        if not candidate.is_file() or candidate.name.lower() != "cc-switch.exe":
            raise ValueError("ccSwitchExecutable 必须指向原版 cc-switch.exe 文件")
        return candidate
    found = shutil.which("cc-switch.exe")
    if found:
        return Path(found).resolve()
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    candidates = [local / "Programs" / name / "cc-switch.exe" for name in ("CC Switch", "cc-switch")]
    candidates = [p.resolve() for p in candidates if p.is_file()]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("请在 config.json 的 ccSwitchExecutable 填写原版 cc-switch.exe 的完整路径")
