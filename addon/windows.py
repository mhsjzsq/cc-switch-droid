"""Read-only Windows process/network inspection and a session mutex.

There is deliberately no API here for killing or restarting applications.
"""

import ctypes
import socket
import struct
import winreg
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class TcpRow(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "state", "local_address", "local_port", "remote_address", "remote_port", "pid"
    )]


kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
iphlpapi.GetExtendedTcpTable.argtypes = (
    wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
    wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
)
iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD


def show_error(message):
    """Report failures after the short-lived PowerShell launcher has exited."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    user32.MessageBoxW.restype = ctypes.c_int
    user32.MessageBoxW(None, message, "CC Switch Droid Hook", 0x10)


class SessionLease:
    def __enter__(self):
        # The old add-on uses this name too. Never let the two controllers run together.
        self.handle = kernel32.CreateMutexW(None, False, r"Local\CCSwitchDroidAddon")
        error = ctypes.get_last_error()
        if not self.handle:
            raise ctypes.WinError(error)
        if error == 183:
            kernel32.CloseHandle(self.handle)
            self.handle = None
            raise RuntimeError(
                "已有 Droid 助手或 Hook 正在运行。请先退出旧助手并停用其开机启动项；"
                "如果本次 Hook 已启动，请使用已有窗口。"
            )
        return self

    def __exit__(self, *_):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def process_tree():
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        processes = {}
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        while ok:
            processes[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return processes
    finally:
        kernel32.CloseHandle(snapshot)


def require_no_client():
    if any(name.lower() == "cc-switch.exe" for _, name in process_tree().values()):
        raise RuntimeError("请先从托盘完整退出 CC Switch，再使用 Open-Hook.cmd。启动器不会结束现有窗口。")


def has_debugging_policy(executable):
    key = r"Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key) as handle:
                for name in ("cc-switch.exe", str(executable), "*"):
                    try:
                        value, _ = winreg.QueryValueEx(handle, name)
                    except FileNotFoundError:
                        continue
                    if "--remote-debugging" in str(value).lower():
                        return True
        except FileNotFoundError:
            continue
    return False


def _listener_rows():
    size = wintypes.DWORD()
    result = iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 3, 0)
    if result not in (0, 122):  # AF_INET, TCP_TABLE_OWNER_PID_LISTENER
        raise OSError(result, "无法读取本机调试端口归属")
    for _ in range(3):
        buffer = ctypes.create_string_buffer(max(size.value, 4))
        result = iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), False, 2, 3, 0)
        if result == 122:
            continue
        if result:
            raise OSError(result, "无法读取本机调试端口归属")
        count = wintypes.DWORD.from_buffer_copy(buffer.raw[:4]).value
        if 4 + count * ctypes.sizeof(TcpRow) > len(buffer):
            raise RuntimeError("本机端口列表长度无效")
        return [
            TcpRow.from_buffer_copy(buffer, 4 + i * ctypes.sizeof(TcpRow))
            for i in range(count)
        ]
    raise RuntimeError("本机端口列表变化过快，稍后重试")


def owns_debug_port(port, client_pid):
    rows = [
        row for row in _listener_rows()
        if struct.unpack("!H", struct.pack("=I", row.local_port)[:2])[0] == port
    ]
    if not rows:
        return False
    processes = process_tree()
    for row in rows:
        address = socket.inet_ntoa(struct.pack("=I", row.local_address))
        if address != "127.0.0.1":
            raise RuntimeError("调试端口没有限定在本机回环地址，已停止加载 Hook")
        pid = row.pid
        visited = set()
        while pid and pid != client_pid and pid not in visited:
            visited.add(pid)
            pid = processes.get(pid, (0, ""))[0]
        if pid != client_pid:
            raise RuntimeError("调试端口不属于本次启动的 CC Switch，已拒绝连接")
    return True
