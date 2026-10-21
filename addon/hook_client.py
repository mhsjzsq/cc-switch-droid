"""Launch the unmodified CC Switch and host hooks only for that child process."""

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import settings_guard  # noqa: E402
import windows  # noqa: E402
from renderer import RendererHooks  # noqa: E402
from run_state import RunState  # noqa: E402
from service import DataService  # noqa: E402


def launch_environment(port):
    env = dict(os.environ)
    arguments = env.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    arguments = re.sub(
        r'(?<!\S)--remote-debugging-(?:port|address)(?:=|\s+)(?:"[^"]*"|\S+)',
        "", arguments, flags=re.IGNORECASE,
    )
    arguments = re.sub(r"(?<!\S)--remote-debugging-pipe(?!\S)", "", arguments, flags=re.IGNORECASE)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        arguments.strip() + f" --remote-debugging-address=127.0.0.1 --remote-debugging-port={port}"
    ).strip()
    return env


def run(state):
    cfg = config.load()
    executable = config.executable(cfg)
    with windows.SessionLease():
        state.owns_session = True
        windows.require_no_client()
        backup = settings_guard.preserve_before_launch(config.ROOT / "data" / "settings-backups")
        if backup is not None:
            state.log("native_settings_preserved", file=str(backup))
        if windows.has_debugging_policy(executable):
            raise RuntimeError(
                "检测到已有 WebView2 调试策略，可能覆盖本次动态端口。"
                "请先撤销旧插件的调试端口策略，再使用新入口；新项目不会修改注册表。"
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        # There is a small OS handoff gap after releasing the reserved port.
        # RendererHooks checks the listener PID and child ancestry before use.
        child = subprocess.Popen(
            [str(executable), *cfg["ccSwitchArguments"]],
            cwd=str(executable.parent), env=launch_environment(port),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True,
        )
        state.update("starting", clientPid=child.pid, executable=str(executable), debugPort=port)
        state.log("client_started", clientPid=child.pid, debugPort=port)
        service = None
        hooks = None
        try:
            service = DataService(cfg, state, lambda: child.poll() is None)
            hooks = RendererHooks(port, child, state)
            deadline = time.monotonic() + cfg["startupTimeoutSeconds"]
            while child.poll() is None:
                try:
                    commands = hooks.update(service.payload())
                except (OSError, ValueError) as error:
                    hooks.last_failure = str(error)[:240]
                    commands = {"ready": False, "sync": False, "quota": False}
                if commands["ready"]:
                    if state.data["state"] != "attached":
                        state.update("attached", reason=None, everAttached=True)
                        state.log("hook_attached", clientPid=child.pid)
                    service.request(sync=commands["sync"], quota=commands["quota"])
                elif hooks.ever_ready:
                    if state.data["state"] != "reconnecting":
                        state.update("reconnecting", reason=hooks.last_failure)
                    if time.monotonic() - hooks.last_ready_at > 15:
                        raise RuntimeError("Hook 连接已中断超过 15 秒；原版窗口保留，请完整退出后重新使用启动入口")
                elif time.monotonic() > deadline:
                    raise RuntimeError(
                        "未能在限定时间内连接并加载 Droid Hook，可能是 WebView2 接口或页面不兼容。"
                        "原版窗口保留；详情见 data/hook.log。"
                        + (f"（{hooks.last_failure}）" if hooks.last_failure else "")
                    )
                # Do not write usage or request quota until the owned window is attached.
                if hooks.ever_ready and child.poll() is None:
                    service.tick()
                time.sleep(0.75)
            if not hooks.ever_ready:
                raise RuntimeError(
                    "本次启动的 CC Switch 在 Hook 加载前已退出；"
                    "它可能把启动请求交给了另一个实例。请完整退出后重试。"
                )
            state.update("stopping", clientExitCode=child.returncode)
        finally:
            if hooks is not None:
                hooks.close()
            if service is not None:
                service.close()
        state.update("stopped")
        state.log("session_stopped")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{32}", args.launch_id):
        parser.error("invalid launch id")
    state = RunState(args.launch_id)
    state.update()
    try:
        return run(state)
    except Exception as error:
        with suppress(OSError):
            state.update("error", reason=str(error))
        with suppress(OSError):
            state.log("hook_failed", reason=str(error))
        if state.data.get("everAttached"):
            windows.show_error(
                f"Droid Hook 已停止：{error}\n\n"
                "原版 CC Switch 窗口会保留。请完整退出后重新运行 Open-Hook.cmd。\n"
                f"日志：{config.ROOT / 'data' / 'hook.log'}"
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
