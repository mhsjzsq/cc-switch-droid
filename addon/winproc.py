"""Windows process helpers via ctypes (no console windows, no extra dependencies)."""

import ctypes
import os
import time
import winreg
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
ERROR_ALREADY_EXISTS = 183

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
psapi.EnumProcesses.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))


def single_instance(name):
    """Return a handle if this is the only instance, else None."""
    handle = kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def _filetime_to_epoch(ft):
    value = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
    return value / 1e7 - 11644473600


def find_processes(image_name):
    """Yield (pid, exe_path, start_epoch) for processes with the given image name."""
    image_name = image_name.lower()
    size = 4096
    while True:
        arr = (wintypes.DWORD * size)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
            return []
        if needed.value < ctypes.sizeof(arr):
            break
        size *= 2
    result = []
    for pid in arr[: needed.value // ctypes.sizeof(wintypes.DWORD)]:
        if not pid:
            continue
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                continue
            path = buf.value
            if os.path.basename(path).lower() != image_name:
                continue
            times = [wintypes.FILETIME() for _ in range(4)]
            start = None
            if kernel32.GetProcessTimes(h, *[ctypes.byref(t) for t in times]):
                start = _filetime_to_epoch(times[0])
            result.append((pid, path, start))
        finally:
            kernel32.CloseHandle(h)
    return result


def terminate(pid, wait_s=10):
    h = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not h:
        return False
    try:
        kernel32.TerminateProcess(h, 0)
        kernel32.WaitForSingleObject(h, int(wait_s * 1000))
        return True
    finally:
        kernel32.CloseHandle(h)


POLICY_KEY = r"Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments"


def policy_args(image_name):
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, POLICY_KEY) as k:
                value, _ = winreg.QueryValueEx(k, image_name)
                if value:
                    return str(value)
        except OSError:
            continue
    return ""


def wait_gone(image_name, pids, timeout_s=10):
    end = time.time() + timeout_s
    while time.time() < end:
        alive = {p for p, _, _ in find_processes(image_name)}
        if not (alive & set(pids)):
            return True
        time.sleep(0.3)
    return False
