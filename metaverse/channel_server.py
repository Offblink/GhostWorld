"""Channel server — loopback line-JSON socket for the agent channel.

Red line (see ``docs/DESIGN-agent-channel.md``): a thread created here may only
touch the ``EventBus`` and the command queue.  It must never read or write
``WorldState`` — commands are executed by the frame loop, which delivers the
response back through the ``PendingCommand`` it was handed.

Protocol (one action per connection, line-delimited JSON over 127.0.0.1)::

    → {"hello": {"token": "...", "role": "wait", "after": 12, "kinds": ["wake"], "timeout": 25}}
    ← {"ok": true, "cursor": 12, "protocol": 1}
      role="wait": one bare event object per line, then the connection closes
                  on the first batch; ← {"timeout": true, "cursor": 12} if nothing came;
                  ← {"gap": true, "oldest": 37, "cursor": 12} when the cursor is too old.
      role="send": → {"cmd": {"cmd": "say", "message": "hi"}}
                  ← {"ack": {...}, "cursor": 13}
"""
from __future__ import annotations

import hmac
import json
import os
import socket
import threading
import time

from .channel import EventBus, PendingCommand

PROTOCOL = 1
HOST = "127.0.0.1"
DEFAULT_WAIT_TIMEOUT = 25.0
ACK_TIMEOUT = 10.0
HELLO_TIMEOUT = 5.0
MAX_LINE = 1 << 20

CHANNEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".channel.json")

__all__ = [
    "ChannelServer", "start", "open_channel", "close_channel",
    "read_channel_file", "write_channel_file", "clear_channel_file", "CHANNEL_FILE", "PROTOCOL",
]


class LineConn:
    """Line-delimited JSON over a socket, without the makefile/timeout trap."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buf = b""

    def read_json(self, timeout: float) -> dict | None:
        """Next JSON value, or None on timeout/EOF/garbage."""
        self.sock.settimeout(timeout)
        while b"\n" not in self._buf:
            try:
                chunk = self.sock.recv(65536)
            except TimeoutError:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            self._buf += chunk
            if len(self._buf) > MAX_LINE:
                raise ValueError("line too long")
        line, self._buf = self._buf.split(b"\n", 1)
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def send(self, obj: dict) -> None:
        self.sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class ChannelServer:
    """Accepts channel clients; routes every action to the bus or the queue."""

    def __init__(self, bus: EventBus, cmd_queue, host: str = HOST, token: str | None = None) -> None:
        self.bus = bus
        self.cmd_queue = cmd_queue
        self.host = host
        self.token = token or os.urandom(16).hex()
        self._sock: socket.socket | None = None
        self._port = 0
        self._stop = threading.Event()
        self._accept_thread: threading.Thread | None = None
        self._conns: set[socket.socket] = set()
        self._conns_lock = threading.Lock()

    # ── lifecycle ────────────────────────────────────────────────────

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> ChannelServer:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, 0))
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        self._port = sock.getsockname()[1]
        self._accept_thread = threading.Thread(target=self._accept_loop, name="ghostworld-channel", daemon=True)
        self._accept_thread.start()
        return self

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self.bus.wake()  # release blocked wait sessions
        with self._conns_lock:
            conns = list(self._conns)
        for sock in conns:
            try:
                sock.close()
            except OSError:
                pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout)
            self._accept_thread = None

    # ── accept loop ──────────────────────────────────────────────────

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                return
            try:
                client, _addr = sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with self._conns_lock:
                self._conns.add(client)
            threading.Thread(target=self._serve, args=(client,), name="ghostworld-channel-conn", daemon=True).start()

    def _serve(self, sock: socket.socket) -> None:
        conn = LineConn(sock)
        try:
            hello = conn.read_json(HELLO_TIMEOUT)
            msg = (hello or {}).get("hello")
            if not isinstance(msg, dict):
                conn.send({"error": "bad hello"})
                return
            if not hmac.compare_digest(str(msg.get("token", "")), str(self.token)):
                conn.send({"error": "bad token"})
                return
            after = msg.get("after")
            conn.send({"ok": True, "cursor": after if isinstance(after, int) else self.bus.cursor(),
                       "protocol": PROTOCOL})
            role = msg.get("role", "wait")
            if role == "wait":
                self._serve_wait(conn, after, msg)
            elif role == "send":
                self._serve_send(conn)
            else:
                conn.send({"error": f"unknown role: {role}"})
        except (OSError, ValueError):
            pass
        finally:
            conn.close()
            with self._conns_lock:
                self._conns.discard(sock)

    # ── roles ────────────────────────────────────────────────────────

    def _serve_wait(self, conn: LineConn, after, msg: dict) -> None:
        timeout = float(msg.get("timeout", DEFAULT_WAIT_TIMEOUT))
        kinds = msg.get("kinds")
        kinds_set = set(kinds) if kinds else None
        deadline = time.monotonic() + timeout
        cursor = after if isinstance(after, int) else self.bus.cursor()
        while not self._stop.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                conn.send({"timeout": True, "cursor": cursor})
                return
            events, cursor, gap = self.bus.wait(cursor, timeout=remaining, kinds=kinds_set)
            if gap:
                # Report the hole first, then whatever is still retrievable.
                conn.send({"gap": True, "oldest": self.bus.oldest, "cursor": cursor})
            if not events:
                continue  # timeout or a plain wake(): re-check the deadline
            for evt in events:
                conn.send(evt)
            return

    def _serve_send(self, conn: LineConn) -> None:
        msg = conn.read_json(HELLO_TIMEOUT)
        cmd = (msg or {}).get("cmd")
        if not isinstance(cmd, dict):
            conn.send({"error": "missing cmd"})
            return
        pending = PendingCommand(cmd, timeout=ACK_TIMEOUT)
        self.cmd_queue.put(pending)
        resp = pending.result()
        cursor = self.bus.cursor()
        if resp is None:
            # Nobody drained the queue — the world is not ticking.
            conn.send({"error": "no ack", "cursor": cursor})
            return
        conn.send({"ack": resp, "cursor": cursor})


def start(bus: EventBus, cmd_queue, token: str | None = None) -> ChannelServer:
    """Listen on a random loopback port and return the running server."""
    return ChannelServer(bus, cmd_queue, token=token).start()


# ── metaverse/.channel.json ──────────────────────────────────────────

def write_channel_file(port: int, token: str, path: str = CHANNEL_FILE, pid: int | None = None) -> dict:
    info = {
        "protocol": PROTOCOL,
        "port": int(port),
        "token": token,
        "pid": int(os.getpid() if pid is None else pid),
        "started": time.time(),
    }
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return info


def read_channel_file(path: str = CHANNEL_FILE) -> dict | None:
    """Channel info of the running game, or None when it is not up."""
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or "port" not in info or "token" not in info:
        return None
    return info


def clear_channel_file(path: str = CHANNEL_FILE, pid: int | None = None) -> None:
    """Remove the file if it is ours (another instance's file is left alone)."""
    info = read_channel_file(path)
    if info is None:
        return
    if pid is not None and info.get("pid") not in (None, pid):
        return
    try:
        os.remove(path)
    except OSError:
        pass


def open_channel(bus: EventBus, cmd_queue, path: str = CHANNEL_FILE) -> ChannelServer:
    """Start the channel and publish where to reach it."""
    server = ChannelServer(bus, cmd_queue).start()
    write_channel_file(server.port, server.token, path=path)
    return server


def close_channel(server: ChannelServer, path: str = CHANNEL_FILE) -> None:
    pid = os.getpid()
    server.stop()
    clear_channel_file(path, pid=pid)
