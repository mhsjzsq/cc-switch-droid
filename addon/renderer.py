"""Persistent hooks for the WebView pages owned by one launched application."""

import json
import time

import cdp
import config
import windows

VERSION = "2.2.8"
KEY = "__ccSwitchDroidHook"


class PageHook:
    def __init__(self, target, port):
        self.ws_url = target["webSocketDebuggerUrl"]
        self.port = port
        self.connection = None
        self.script_id = None
        self.registration_attempted = False
        self.last_payload = None
        self.instance_id = None
        self.ready = False
        self.failures = 0
        self.last_commands = None

    def connect(self):
        if self.connection is None:
            self.connection = cdp.Session(self.ws_url, self.port)

    def update(self, source, payload):
        self.connect()
        if not self.registration_attempted:
            self.connection.call("Page.enable")
            # A timeout after sending registration has an unknown outcome.
            # Do not accumulate duplicate reload scripts by retrying it.
            self.registration_attempted = True
            result = self.connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})
            self.script_id = result["identifier"]
        info = self.connection.evaluate(
            f"typeof window.{KEY}?.poll === 'function' ? window.{KEY}.poll() : null"
        )
        if not isinstance(info, dict) or info.get("version") != VERSION:
            # Also handles a reload that raced the initial injection.
            self.connection.evaluate(source)
            self.last_payload = None
            self.ready = False
            return {}
        commands = (info.get("instanceId"), info.get("syncNow", 0), info.get("refresh", 0))
        previous = self.last_commands
        new_refresh = bool(commands[2]) and (
            previous is None or (commands[0], commands[2]) != (previous[0], previous[2])
        )
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if (serialized != self.last_payload or new_refresh or not self.ready
                or info.get("instanceId") != self.instance_id):
            self.connection.evaluate(f"window.{KEY} && window.{KEY}.setData({serialized})")
            self.last_payload = serialized
            self.instance_id = info.get("instanceId")
        self.ready = bool(info.get("ready")) and info.get("version") == VERSION
        self.failures = 0
        # poll() is non-destructive: a timeout during setData must not lose a
        # user's request. Only acknowledge counters after a successful update.
        output = dict(info)
        output["syncNow"] = bool(commands[1]) and (previous is None or commands[:2] != previous[:2])
        output["refresh"] = new_refresh
        if self.ready:
            self.last_commands = commands
        else:
            output["syncNow"] = output["refresh"] = False
        return output

    def disconnect(self):
        # A receive timeout can interrupt a WebSocket frame. Drop the transport
        # but keep the page's installed hook and reload-script identity intact.
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.ready = False

    def close(self, restore=False):
        # These commands are independent: a destroyed execution context must
        # not prevent removal of the registered reload script.
        try:
            if restore:
                try:
                    self.connect()
                except Exception:
                    return
                if self.script_id:
                    try:
                        self.connection.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier": self.script_id})
                    except Exception:
                        pass
                try:
                    self.connection.evaluate(f"window.{KEY} && window.{KEY}.destroy()")
                except Exception:
                    pass
        finally:
            self.disconnect()


class RendererHooks:
    def __init__(self, port, child, state):
        self.port = port
        self.child = child
        self.state = state
        self.pages = {}
        self.ever_ready = False
        self.last_ready_at = time.monotonic()
        self.last_failure = None
        self.retry_after = {}
        raw = "\n".join(
            (config.ROOT / "addon" / name).read_text(encoding="utf-8-sig")
            for name in ("native_usage.js", "inject.js")
        )
        raw = raw.replace("__ADDON_VERSION__", VERSION)
        self.source = (
            "(()=>{const install=()=>{"
            "if(!(['http:','https:'].includes(location.protocol)&&location.hostname==='tauri.localhost'"
            "||location.protocol==='tauri:'&&location.hostname==='localhost'))return;"
            + raw + "};"
            "if(document.readyState==='loading'){"
            "document.addEventListener('DOMContentLoaded',install,{once:true});"
            "}else{install();}})();"
        )

    def update(self, payload):
        if self.child.poll() is not None:
            return {"ready": False, "sync": False, "quota": False}
        # Revalidate port ownership before discovering/operating any renderer.
        if not windows.owns_debug_port(self.port, self.child.pid):
            return {"ready": False, "sync": False, "quota": False}
        targets = [target for target in cdp.list_targets(self.port) if cdp.is_app_page(target)]
        current = {t["id"] for t in targets}
        for target_id in list(self.pages):
            if target_id not in current:
                self.pages.pop(target_id).close()
                self.retry_after.pop(target_id, None)
        commands = {"ready": False, "sync": False, "quota": False}
        for target in targets:
            target_id = target["id"]
            if self.child.poll() is not None:
                break
            if time.monotonic() < self.retry_after.get(target_id, 0):
                continue
            try:
                if target_id not in self.pages:
                    self.pages[target_id] = PageHook(target, self.port)
                page = self.pages[target_id]
                info = page.update(self.source, payload)
                commands["sync"] |= bool(info.get("syncNow"))
                commands["quota"] |= bool(info.get("refresh"))
                commands["ready"] |= page.ready
                self.retry_after.pop(target_id, None)
            except Exception as error:
                delay = 2
                if target_id in self.pages:
                    page = self.pages[target_id]
                    page.disconnect()
                    page.failures += 1
                    delay = min(8, 2 ** min(page.failures, 3))
                # A busy native renderer is not evidence that the hook must be
                # destroyed/reinstalled. Recovery first polls the existing hook.
                self.retry_after[target_id] = time.monotonic() + delay
                message = str(error)[:240]
                if message != self.last_failure:
                    self.state.log("page_attach_failed", reason=message)
                self.last_failure = message
        if commands["ready"]:
            self.ever_ready = True
            self.last_ready_at = time.monotonic()
        return commands

    def close(self):
        try:
            restore = self.child.poll() is None and windows.owns_debug_port(self.port, self.child.pid)
        except (OSError, RuntimeError):
            restore = False
        for page in self.pages.values():
            page.close(restore=restore)
        self.pages.clear()
