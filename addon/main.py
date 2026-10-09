"""CC Switch Droid add-on: background helper.

- Copies Droid session usage into the CC Switch usage database.
- Injects a "Droid" sidebar entry and quota panel into the CC Switch window
  through the WebView2 DevTools port.
- Without the WebView2 policy, restarts a freshly started CC Switch once with
  the DevTools port enabled.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ADDON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADDON_DIR))

import cdp  # noqa: E402
import droid_sync  # noqa: E402
import factory_quota  # noqa: E402
import winproc  # noqa: E402

VERSION = "1.0.0"
ROOT = ADDON_DIR.parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
LOG_PATH = DATA_DIR / "addon.log"
IMAGE = "cc-switch.exe"

DEFAULT_CONFIG = {
    "factoryApiKey": "",
    "debugPort": 9333,
    "quotaRefreshSeconds": 60,
    "autoRestartWithoutPolicy": True,
    "ccSwitchDbPath": "",
    "droidSessionsDir": "",
}

_last_logged = {}


def log(msg, dedupe_s=0):
    now = time.time()
    if dedupe_s and now - _last_logged.get(msg, 0) < dedupe_s:
        return
    _last_logged[msg] = now
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 1_000_000:
            LOG_PATH.replace(LOG_PATH.with_suffix(".old.log"))
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except OSError:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
    except FileNotFoundError:
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    except (OSError, ValueError) as e:
        log(f"config.json 读取失败，使用默认值：{e}", dedupe_s=600)
    return cfg


def process_cmdline(pid):
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
            capture_output=True, text=True, timeout=15, creationflags=0x08000000,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


class Addon:
    def __init__(self):
        self.cfg = load_config()
        self.cfg_loaded_at = time.time()
        self.inject_mtime = None
        self.load_inject()
        self.quota = {}
        self.auth_cache = {}
        self.today = {}
        self.next_sync = 0
        self.next_quota = 0
        self.next_today = 0
        self.pushed = None
        self.last_key = None
        self.seen = {}
        self.handled = set()
        self.restarts = []

    def load_inject(self):
        path = ADDON_DIR / "inject.js"
        mtime = path.stat().st_mtime
        if mtime == self.inject_mtime:
            return
        self.inject_mtime = mtime
        self.inject_version = f"{VERSION}-{int(mtime)}"
        self.inject_src = path.read_text(encoding="utf-8").replace("__ADDON_VERSION__", self.inject_version)

    # paths -----------------------------------------------------------------
    def db_path(self):
        p = self.cfg.get("ccSwitchDbPath")
        return Path(p) if p else Path.home() / ".cc-switch" / "cc-switch.db"

    def sessions_dir(self):
        p = self.cfg.get("droidSessionsDir")
        return Path(p) if p else Path.home() / ".factory" / "sessions"

    def sync_interval(self):
        """Follow CC Switch's usage-page auto refresh setting; 60 s when it is off."""
        try:
            settings = json.loads((self.db_path().parent / "settings.json").read_text(encoding="utf-8-sig"))
            ms = int(settings.get("usageDashboardRefreshIntervalMs") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            ms = 0
        return max(2, ms / 1000) if ms > 0 else 60

    # periodic work ---------------------------------------------------------
    def run_sync(self):
        try:
            n = droid_sync.sync(self.sessions_dir(), self.db_path(), DATA_DIR / "sync_state.json")
            if n:
                log(f"同步 Droid 用量：写入 {n} 条")
                self.next_today = 0
        except Exception as e:
            log(f"同步失败：{e!r}", dedupe_s=600)

    def refresh_today(self):
        try:
            if self.db_path().is_file():
                self.today = droid_sync.today_usage(self.db_path())
        except Exception as e:
            log(f"读取今日用量失败：{e!r}", dedupe_s=600)

    def refresh_quota(self):
        key = factory_quota.resolve_api_key(self.cfg.get("factoryApiKey"))
        if key != self.last_key:
            self.auth_cache = {}
            self.quota = {}
            self.last_key = key
        interval = max(15, int(self.cfg.get("quotaRefreshSeconds") or 60))
        if not key:
            self.next_quota = time.time() + 10
            return
        try:
            self.quota = factory_quota.fetch(key, self.auth_cache)
            self.next_quota = time.time() + interval
        except factory_quota.QuotaError as e:
            self.quota = dict(self.quota, error=str(e), updatedAt=int(time.time() * 1000))
            self.next_quota = time.time() + max(interval, 120)
            log(f"获取额度失败：{e}", dedupe_s=600)

    def payload(self, refreshing=False):
        return json.dumps({
            "configured": bool(self.last_key),
            "configPath": str(CONFIG_PATH),
            "quota": self.quota,
            "today": self.today,
            "refreshing": refreshing,
        }, ensure_ascii=False)

    # CC Switch page ----------------------------------------------------------
    def serve(self, page):
        with cdp.Session(page["webSocketDebuggerUrl"]) as s:
            raw = s.evaluate("window.__droidAddon ? JSON.stringify(window.__droidAddon.poll()) : ''")
            info = json.loads(raw) if raw else {}
            if info.get("version") != self.inject_version:
                s.evaluate(self.inject_src)
                self.pushed = None
                info = json.loads(s.evaluate("JSON.stringify(window.__droidAddon.poll())") or "{}")
                log("已注入 CC Switch 界面", dedupe_s=5)
            now = time.time()
            if info.get("syncNow"):
                self.run_sync()
                self.next_sync = now + self.sync_interval()
                self.next_today = 0
            if info.get("refresh") or now >= self.next_quota:
                self.refresh_quota()
                self.next_today = 0
            if now >= self.next_today:
                self.refresh_today()
                self.next_today = now + 30
            data = self.payload()
            if data != self.pushed or info.get("refresh"):
                s.evaluate(f"window.__droidAddon && window.__droidAddon.setData({data})")
                self.pushed = data

    def maybe_restart(self, procs, port):
        if not self.cfg.get("autoRestartWithoutPolicy", True):
            return
        now = time.time()
        for pid, path, start in procs:
            if pid in self.handled:
                continue
            first = self.seen.setdefault(pid, now)
            if now - first < 15:
                continue
            self.handled.add(pid)
            if f"--remote-debugging-port={port}" in winproc.policy_args(IMAGE):
                log("已写入 WebView2 策略，但 CC Switch 没有开启调试端口，请手动重启一次 CC Switch", dedupe_s=3600)
                continue
            age = now - (start or now)
            if age > 300:
                log("CC Switch 已运行较久且未开启调试端口，不自动重启；下次启动 CC Switch 时会自动处理", dedupe_s=3600)
                continue
            self.restarts = [t for t in self.restarts if now - t < 600]
            if len(self.restarts) >= 2:
                log("10 分钟内已自动重启 2 次仍无法开启调试端口，暂停自动重启", dedupe_s=3600)
                continue
            self.restarts.append(now)
            cmdline = process_cmdline(pid) or f'"{path}"'
            log(f"CC Switch 未开启调试端口，自动重启：{cmdline}")
            winproc.terminate(pid)
            winproc.wait_gone(IMAGE, [pid])
            time.sleep(2)
            env_args = f"--remote-debugging-port={port}"
            env = dict(os.environ)
            existing = env.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
            env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{existing} {env_args}".strip()
            subprocess.Popen(cmdline, cwd=str(Path(path).parent), env=env,
                             creationflags=0x00000008 | 0x00000200, close_fds=True)

    def tick(self):
        now = time.time()
        if now - self.cfg_loaded_at > 10:
            self.load_inject()
            self.cfg = load_config()
            self.cfg_loaded_at = now
            key = factory_quota.resolve_api_key(self.cfg.get("factoryApiKey"))
            if key != self.last_key:
                self.next_quota = 0
        if now >= self.next_sync:
            self.run_sync()
            self.next_sync = now + self.sync_interval()
        procs = winproc.find_processes(IMAGE)
        if not procs:
            self.seen.clear()
            return
        port = int(self.cfg.get("debugPort") or 9333)
        try:
            page = cdp.find_page(port)
        except OSError:
            page = None
        if page:
            for pid, _, _ in procs:
                self.handled.add(pid)
            self.serve(page)
        else:
            self.maybe_restart(procs, port)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    mutex = winproc.single_instance("Local\\CCSwitchDroidAddon")
    if mutex is None:
        return 0
    log(f"启动 v{VERSION}")
    addon = Addon()
    while True:
        try:
            addon.tick()
        except Exception as e:
            log(f"运行出错：{e!r}", dedupe_s=300)
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
