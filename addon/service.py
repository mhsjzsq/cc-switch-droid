"""Usage and quota jobs scoped to one CC Switch launch, independent of the UI."""

import json
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor

import config
import droid_sync
import droid_timing
import factory_quota


class DataService:
    def __init__(self, cfg, state, client_alive):
        self.cfg = cfg
        self.state = state
        self.client_alive = client_alive
        self.stop = threading.Event()
        self.worker = ThreadPoolExecutor(max_workers=2, thread_name_prefix="droid-hook")
        self.sync_job = None
        self.quota_job = None
        self.sync_signature = None
        self.quota_key = None
        self.last_key = None
        self.auth_cache = {}
        self.timing_reader = droid_timing.TimingReader()
        self.quota = {}
        self.today = {}
        self.warnings = []
        self.config_error = None
        self.key_error = None
        self.next_config = time.monotonic() + 10
        self.next_sync = 0
        self.next_quota = 0
        self.sync_requested = False
        self.quota_requested = False
        self.closed = False

    def cancelled(self):
        return self.stop.is_set() or not self.client_alive()

    def signature(self, cfg=None):
        cfg = self.cfg if cfg is None else cfg
        return str(config.db_path(cfg)), str(config.sessions_dir(cfg)), str(config.logs_dir(cfg))

    def sync_interval(self):
        try:
            settings = config.db_path(self.cfg).parent / "settings.json"
            value = json.loads(settings.read_text(encoding="utf-8-sig"))
            milliseconds = int(value.get("usageDashboardRefreshIntervalMs") or 0)
            return max(2, milliseconds / 1000) if milliseconds > 0 else 60
        except (OSError, ValueError, TypeError, AttributeError):
            return 60

    def request(self, *, sync=False, quota=False):
        if sync:
            self.sync_requested = True
        if quota:
            self.quota_requested = True

    def _sync(self, cfg):
        timings, timing_warnings = self.timing_reader.read(config.logs_dir(cfg), self.cancelled)
        result = droid_sync.sync(
            config.sessions_dir(cfg), config.db_path(cfg), cancelled=self.cancelled, timings=timings
        )
        result.warnings.extend(timing_warnings)
        if self.cancelled():
            raise CancelledError()
        today = (
            droid_sync.today_usage(config.db_path(cfg))
            if config.db_path(cfg).is_file()
            else {"available": False, "error": "CC Switch 数据库不存在"}
        )
        return result, today

    def _quota(self, key, cache):
        if self.cancelled():
            raise CancelledError()
        quota = factory_quota.fetch(key, cache)
        if self.cancelled():
            raise CancelledError()
        return quota, cache

    def _reload(self):
        if time.monotonic() < self.next_config:
            return
        self.next_config = time.monotonic() + 10
        try:
            cfg = config.load()
            old_signature = self.signature()
            # Executable and launch arguments are fixed for the current child.
            for name in ("ccSwitchExecutable", "ccSwitchArguments", "startupTimeoutSeconds"):
                cfg[name] = self.cfg[name]
            new_signature = self.signature(cfg)
            self.cfg = cfg
            if new_signature != old_signature:
                self.today = {}
                self.warnings = []
                self.next_sync = 0
            self.config_error = None
        except (OSError, ValueError) as error:
            message = f"配置读取失败，继续使用上次有效配置：{error}"
            if message != self.config_error:
                self.state.log("config_invalid", reason=message)
            self.config_error = message

    def _collect(self):
        if self.sync_job is not None and self.sync_job.done():
            job, signature = self.sync_job, self.sync_signature
            self.sync_job = None
            if signature == self.signature():
                try:
                    result, self.today = job.result()
                    self.warnings = result.warnings
                    if result.inserted:
                        self.state.log("usage_imported", records=result.inserted)
                    if result.timings_updated:
                        self.state.log("usage_timings_updated", records=result.timings_updated)
                except CancelledError:
                    return
                except Exception as error:
                    self.warnings = [f"同步失败：{error}"]
                    self.today = {"available": False, "error": "同步未完成，旧数值暂不展示"}
                    self.state.log("sync_failed", reason=str(error))
                self.next_sync = time.monotonic() + self.sync_interval()
        if self.quota_job is not None and self.quota_job.done():
            job, key = self.quota_job, self.quota_key
            self.quota_job = None
            if key == self.last_key:
                interval = self.cfg["quotaRefreshSeconds"]
                try:
                    self.quota, self.auth_cache = job.result()
                    self.quota["attemptedAt"] = int(time.time() * 1000)
                except CancelledError:
                    return
                except Exception as error:
                    self.quota = dict(
                        self.quota, error=str(error), stale=True,
                        attemptedAt=int(time.time() * 1000),
                    )
                    interval = max(interval, 120)
                    self.state.log("quota_failed", reason=str(error))
                self.next_quota = time.monotonic() + interval

    def tick(self):
        if self.closed or self.cancelled():
            return
        self._reload()
        try:
            key = factory_quota.resolve_api_key(self.cfg["factoryApiKey"])
            self.key_error = None
        except (OSError, ValueError, factory_quota.QuotaError):
            # Credential-file errors must not stop local usage synchronization.
            key = ""
            self.key_error = "Factory 凭据文件读取失败，请检查 ~/.factory/.env 或 config.json"
        if key != self.last_key:
            self.last_key = key
            self.auth_cache = {}
            self.quota = {}
            self.next_quota = 0
        self._collect()
        now = time.monotonic()
        if self.sync_job is None and (self.sync_requested or now >= self.next_sync):
            self.sync_requested = False
            self.sync_signature = self.signature()
            self.sync_job = self.worker.submit(self._sync, dict(self.cfg))
        if self.quota_job is None and (self.quota_requested or now >= self.next_quota):
            self.quota_requested = False
            if key:
                self.quota_key = key
                self.quota_job = self.worker.submit(self._quota, key, dict(self.auth_cache))
            else:
                self.next_quota = now + 10

    def payload(self):
        warnings = list(self.warnings[:10])
        if self.config_error:
            warnings.insert(0, self.config_error)
        if self.key_error:
            warnings.insert(0, self.key_error)
        return {
            "configured": bool(self.last_key), "configPath": str(config.CONFIG_PATH),
            "quota": self.quota, "today": self.today, "syncWarnings": warnings,
            "refreshing": self.quota_job is not None and self.quota_key == self.last_key,
        }

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        # Drain in-flight jobs before releasing the mutex. Sync checks cancellation
        # between files and before commit; urllib requests retain their timeouts.
        self.worker.shutdown(wait=True, cancel_futures=True)
