"""Minimal Chrome DevTools Protocol client (stdlib only) for WebView2 pages."""

import base64
import hashlib
import json
import os
import socket
import struct
import time
import urllib.request
from urllib.parse import urlsplit


class CDPError(Exception):
    pass


def list_targets(port, timeout=1.5):
    # System HTTP proxies must not receive local debugging requests.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=timeout) as resp:
        body = json.loads(resp.read(1_048_576).decode("utf-8"))
    if not isinstance(body, list):
        raise CDPError("invalid target list")
    return body


def is_app_page(target):
    if not isinstance(target, dict) or target.get("type") != "page":
        return False
    url = urlsplit(target.get("url") or "")
    return bool(target.get("id") and target.get("webSocketDebuggerUrl")) and (
        url.scheme in ("http", "https") and url.hostname == "tauri.localhost"
        or url.scheme == "tauri" and url.hostname == "localhost"
    )


class Session:
    def __init__(self, ws_url, expected_port, timeout=2):
        url = urlsplit(ws_url)
        if url.scheme != "ws" or url.hostname not in ("127.0.0.1", "localhost") or url.port != expected_port:
            raise CDPError("only this launch's loopback endpoint is accepted")
        if url.username or url.password or not url.path.startswith("/devtools/page/"):
            raise CDPError("invalid page debugging endpoint")
        hostport = f"127.0.0.1:{expected_port}"
        path = url.path + (("?" + url.query) if url.query else "")
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
        self.sock = socket.create_connection(("127.0.0.1", expected_port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        try:
            self.sock.sendall(
                (
                    f"GET {path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                    f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
                ).encode()
            )
            buf = b""
            while b"\r\n\r\n" not in buf:
                self._remaining_timeout()
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise CDPError("handshake closed")
                buf += chunk
                if len(buf) > 65536:
                    raise CDPError("handshake too large")
            head, self.buf = buf.split(b"\r\n\r\n", 1)
            lines = head.split(b"\r\n")
            if b" 101 " not in lines[0]:
                raise CDPError("handshake rejected: " + lines[0].decode(errors="replace"))
            headers = {}
            for line in lines[1:]:
                name, separator, value = line.partition(b":")
                if separator:
                    headers[name.strip().lower()] = value.strip()
            accept = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            if headers.get(b"sec-websocket-accept") != accept:
                raise CDPError("invalid websocket handshake")
        except BaseException:
            self.close()
            raise
        self.next_id = 0

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _read(self, n):
        while len(self.buf) < n:
            self._remaining_timeout()
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CDPError("connection closed")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def _remaining_timeout(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CDPError("CDP command timed out")
        self.sock.settimeout(remaining)

    def _send_frame(self, opcode, payload):
        self._remaining_timeout()
        n = len(payload)
        header = bytearray([0x80 | opcode])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        if n:
            full = (mask * (n // 4 + 1))[:n]
            payload = (int.from_bytes(payload, "big") ^ int.from_bytes(full, "big")).to_bytes(n, "big")
        self.sock.sendall(bytes(header) + payload)

    def _recv_message(self):
        parts = []
        total = 0
        while True:
            b1, b2 = self._read(2)
            fin, opcode = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            total += n
            if total > 16 * 1024 * 1024:
                raise CDPError("CDP response too large")
            if b2 & 0x80:
                mask = self._read(4)
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(self._read(n)))
            else:
                data = self._read(n)
            if opcode == 0x8:
                raise CDPError("connection closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, data)
                continue
            if opcode == 0xA:
                continue
            parts.append(data)
            if fin:
                return b"".join(parts).decode("utf-8", errors="replace")

    def call(self, method, params=None):
        self.deadline = time.monotonic() + self.timeout
        self.next_id += 1
        mid = self.next_id
        self._send_frame(0x1, json.dumps({"id": mid, "method": method, "params": params or {}}).encode())
        while True:
            msg = json.loads(self._recv_message())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError(str(msg["error"]))
                return msg.get("result") or {}

    def evaluate(self, expression):
        res = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if res.get("exceptionDetails"):
            raise CDPError("page exception: " + json.dumps(res["exceptionDetails"])[:400])
        return (res.get("result") or {}).get("value")
