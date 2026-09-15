"""Client for the GhostWorld agent channel.

Deliberately standalone: **stdlib only, no imports from this repo**, so another
program (a Fungi clone, a bot, a test harness) can drive a GhostWorld character
either by shelling out to ``ghostworld-send`` / ``ghostworld-wait`` or by copying
this one file into its own tree and using it in-process.

Shape of the channel (see ``docs/PROTOCOL-agent-channel.md``): line-delimited
JSON over 127.0.0.1, one action per connection, discovery through
``metaverse/.channel.json``.  ``send`` returns an ack; ``wait`` blocks on the
socket until the game pushes an event — there is no polling anywhere.

Failures are exceptions, so callers can map them to whatever they like::

    ChannelUnavailable  — no game running / not our channel        (CLI: 2)
    NoAck               — accepted, but the frame loop never ran it (CLI: 1)
    ChannelTimeout      — nothing happened before the deadline     (CLI: 3)
"""
from __future__ import annotations

import json
import os
import socket

from ._paths import runtime_paths

PROTOCOL = 1
DEFAULT_WAIT_TIMEOUT = 25.0
DEFAULT_ACK_TIMEOUT = 15.0
HANDSHAKE_TIMEOUT = 5.0
MAX_LINE = 1 << 20

# The game writes these where it runs (see `_paths.runtime_dir`): beside the code
# in a checkout, under the user's app directory in a frozen build.
_PATHS = runtime_paths()
DEFAULT_CHANNEL_FILE = str(_PATHS["channel"])
DEFAULT_CURSOR_FILE = str(_PATHS["cursor"])


class ChannelUnavailable(RuntimeError):
    """No channel file, or nothing listening on the advertised port."""


class NoAck(RuntimeError):
    """The command was accepted but the frame loop never answered."""


class ChannelTimeout(RuntimeError):
    """No event arrived before the deadline."""


def read_channel_file(path: str = DEFAULT_CHANNEL_FILE) -> dict | None:
    """Where the running game listens, or None when it is not up."""
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or "port" not in info or "token" not in info:
        return None
    return info


def read_cursor(path: str = DEFAULT_CURSOR_FILE, token: str | None = None) -> int:
    """Stored cursor, or 0 when it belongs to an earlier game instance.

    ``seq`` restarts at 1 in every new game process, so a cursor from another
    instance is not just stale — it is a different numbering.
    """
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return 0
    if not isinstance(state, dict) or state.get("token") != token:
        return 0
    cursor = state.get("cursor")
    return cursor if isinstance(cursor, int) and cursor >= 0 else 0


def write_cursor(cursor: int, path: str = DEFAULT_CURSOR_FILE, token: str | None = None) -> None:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"token": token, "cursor": int(cursor)}, f)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class _LineConn:
    """Line-delimited JSON over a socket (kept standalone on purpose)."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buf = b""

    def read_json(self, timeout: float) -> dict | None:
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
                return None
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


class ChannelClient:
    """Drives one character: commands out, events in."""

    def __init__(self, info: dict, cursor: int = 0, cursor_file: str | None = None) -> None:
        self.info = info
        self.cursor = int(cursor)
        self.cursor_file = cursor_file
        self.last_gap: dict | None = None

    @classmethod
    def from_file(cls, path: str = DEFAULT_CHANNEL_FILE,
                  cursor_file: str | None = DEFAULT_CURSOR_FILE) -> ChannelClient:
        info = read_channel_file(path)
        if info is None:
            raise ChannelUnavailable(f"channel not found ({path}) — 游戏没在跑？")
        cursor = read_cursor(cursor_file, info.get("token")) if cursor_file else 0
        return cls(info, cursor=cursor, cursor_file=cursor_file)

    # ── one action per connection ────────────────────────────────────

    def _open(self) -> _LineConn:
        try:
            sock = socket.create_connection(("127.0.0.1", int(self.info["port"])), timeout=HANDSHAKE_TIMEOUT)
        except (OSError, KeyError, ValueError) as e:
            raise ChannelUnavailable(f"channel unreachable on port {self.info.get('port')}: {e}") from e
        return _LineConn(sock)

    def _handshake(self, conn: _LineConn, role: str, **fields) -> None:
        conn.send({"hello": {"token": self.info.get("token"), "role": role, **fields}})
        reply = conn.read_json(HANDSHAKE_TIMEOUT)
        if reply is None:
            raise ChannelUnavailable("channel handshake failed — 游戏还在跑吗？")
        if not reply.get("ok"):
            raise ChannelUnavailable(f"channel refused the handshake: {reply.get('error')}")

    def send(self, cmd: dict, timeout: float = DEFAULT_ACK_TIMEOUT) -> dict:
        """Run one command; returns the ack. Raises NoAck if nothing answered."""
        conn = self._open()
        try:
            self._handshake(conn, "send")
            conn.send({"cmd": cmd})
            reply = conn.read_json(timeout)
        finally:
            conn.close()
        if reply is None or "ack" not in reply:
            raise NoAck((reply or {}).get("error", "no ack — 帧循环没在跑？"))
        return reply["ack"]

    def wait(self, timeout: float = DEFAULT_WAIT_TIMEOUT, kinds: set[str] | None = None,
             after: int | None = None) -> list[dict]:
        """Block until events arrive. Raises ChannelTimeout when none did.

        The cursor is remembered (and, for :meth:`from_file` clients, persisted),
        so events published while the caller was busy are delivered next time.
        """
        cursor = self.cursor if after is None else after
        conn = self._open()
        try:
            self._handshake(conn, "wait", after=cursor, timeout=timeout,
                            kinds=sorted(kinds) if kinds else None)
            events: list[dict] = []
            self.last_gap = None
            while True:
                msg = conn.read_json(timeout + HANDSHAKE_TIMEOUT)
                if msg is None:
                    break
                if msg.get("timeout"):
                    break
                if msg.get("gap"):
                    self.last_gap = msg
                    continue
                events.append(msg)
        finally:
            conn.close()
        if not events:
            raise ChannelTimeout(f"no events within {timeout:g}s")
        self.cursor = max(int(e.get("seq", 0)) for e in events)
        self._persist()
        return events

    def iter_events(self, timeout: float = DEFAULT_WAIT_TIMEOUT,
                    kinds: set[str] | None = None, stop=None):
        """Yield event batches forever — one long-lived watcher, no polling.

        ``stop`` is an optional zero-argument callable; when it returns True the
        generator ends (also on a channel error).
        """
        while stop is None or not stop():
            try:
                yield self.wait(timeout=timeout, kinds=kinds)
            except ChannelTimeout:
                continue
            except ChannelUnavailable:
                return

    def _persist(self) -> None:
        if self.cursor_file:
            write_cursor(self.cursor, self.cursor_file, self.info.get("token"))
