"""Atomic, per-launch status plus bounded local diagnostic logging."""

import json
import os
import time
from datetime import datetime, timezone

import config


class RunState:
    def __init__(self, launch_id):
        self.directory = config.ROOT / "data"
        self.directory.mkdir(exist_ok=True)
        launches = self.directory / "launches"
        launches.mkdir(exist_ok=True)
        self.path = launches / f"{launch_id}.json"
        self.owns_session = False
        self.data = {
            "version": "2.2.8", "launchId": launch_id, "helperPid": os.getpid(),
            "state": "starting", "startedAt": self.now(),
        }

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _write(path, data):
        temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            for attempt in range(5):
                try:
                    os.replace(temp, path)
                    return
                except PermissionError:
                    # PowerShell/antivirus readers can briefly deny replacement
                    # on Windows. Keep the old complete status during the retry.
                    if attempt == 4:
                        raise
                    time.sleep(0.02)
        finally:
            temp.unlink(missing_ok=True)

    def update(self, state=None, **detail):
        if state:
            self.data["state"] = state
        self.data.update(detail, updatedAt=self.now())
        self._write(self.path, self.data)
        if self.owns_session:
            self._write(self.directory / "status.json", self.data)

    def log(self, event, **detail):
        path = self.directory / "hook.log"
        if path.exists() and path.stat().st_size > 1_000_000:
            os.replace(path, self.directory / "hook.previous.log")
        record = {"time": self.now(), "event": event, "launchId": self.data["launchId"], **detail}
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
