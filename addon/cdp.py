"""Minimal Chrome DevTools Protocol client (stdlib only) for WebView2 pages."""

import base64
import json
import os
import socket
import struct
import urllib.request


class CDPError(Exception):
    pass


def list_targets(port, timeout=1.5):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_page(port):
    for t in list_targets(port):
        url = t.get("url") or ""
        if t.get("type") == "page" and "tauri.localhost" in url and t.get("webSocketDebuggerUrl"):
            return t
    return None


class Session:
    def __init__(self, ws_url, timeout=10):
        rest = ws_url.split("://", 1)[1]
        hostport, path = rest.split("/", 1)
        host, port = hostport.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("handshake closed")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise CDPError("handshake rejected: " + head.split(b"\r\n", 1)[0].decode(errors="ignore"))
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
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CDPError("connection closed")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def _send_frame(self, opcode, payload):
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
        while True:
            b1, b2 = self._read(2)
            fin, opcode = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
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
