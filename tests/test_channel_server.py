"""Channel server tests — wire protocol, thread boundary, cmd queue hand-off."""
import json
import os
import queue
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metaverse.channel_server as channel_server
from metaverse.channel import KIND_OBSERVATION, KIND_WAKE, EventBus
from metaverse.channel_server import HOST, start


class RawClient:
    """Speaks the documented wire protocol by hand — no client code involved."""

    def __init__(self, port: int, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection((HOST, port), timeout=timeout)
        self._buf = b""

    def send(self, obj: dict) -> None:
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def read(self, timeout: float = 5.0) -> dict | None:
        self.sock.settimeout(timeout)
        while b"\n" not in self._buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def read_all(self, timeout: float = 2.0) -> list[dict]:
        """Every reply line until the server closes or goes quiet."""
        out: list[dict] = []
        while True:
            try:
                value = self.read(timeout)
            except (TimeoutError, OSError):
                break
            if value is None:
                break
            out.append(value)
        return out

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@pytest.fixture
def server():
    srv = start(EventBus(), queue.Queue())
    yield srv
    srv.stop()


def test_bad_token_is_rejected(server):
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": "not-the-token", "role": "wait"}})
        assert client.read() == {"error": "bad token"}
        assert client.read(timeout=1.0) is None, "connection must be closed"
    finally:
        client.close()


def test_send_hands_the_command_to_the_queue_and_relays_the_ack(server):
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": server.token, "role": "send"}})
        assert client.read() == {"ok": True, "cursor": 0, "protocol": channel_server.PROTOCOL}
        client.send({"cmd": {"cmd": "pos"}})
        pending = server.cmd_queue.get(timeout=2.0)
        assert pending.cmd == {"cmd": "pos"}, "the channel thread must post the raw command"
        assert server.bus.cursor() == 0, "posting a command publishes nothing"
        pending.deliver({"type": "position", "x": 1.5, "y": 2.5})
        assert client.read() == {"ack": {"type": "position", "x": 1.5, "y": 2.5}, "cursor": 0}
    finally:
        client.close()


def test_send_without_a_frame_loop_reports_no_ack(server, monkeypatch):
    monkeypatch.setattr(channel_server, "ACK_TIMEOUT", 0.2)
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": server.token, "role": "send"}})
        client.read()
        client.send({"cmd": {"cmd": "pos"}})
        assert server.cmd_queue.get(timeout=2.0).cmd == {"cmd": "pos"}
        assert client.read(timeout=2.0) == {"error": "no ack", "cursor": 0}
    finally:
        client.close()


def test_wait_pushes_an_event_line_without_polling(server):
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": server.token, "role": "wait", "after": 0, "timeout": 5.0}})
        assert client.read() == {"ok": True, "cursor": 0, "protocol": channel_server.PROTOCOL}
        time.sleep(0.1)
        published_at = time.monotonic()
        server.bus.publish({"event": "heard", "kind": KIND_WAKE, "from": "player", "message": "hi"})
        line = client.read(timeout=2.0)
        latency = time.monotonic() - published_at
        assert line is not None
        assert line["event"] == "heard" and line["message"] == "hi" and line["seq"] == 1
        assert latency < 0.05, f"the event line must be pushed, took {latency:.4f}s"
    finally:
        client.close()


def test_wait_timeout_reply(server):
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": server.token, "role": "wait", "after": 0, "timeout": 0.2}})
        client.read()
        started = time.monotonic()
        assert client.read(timeout=2.0) == {"timeout": True, "cursor": 0}
        assert time.monotonic() - started < 1.0
    finally:
        client.close()


def test_wait_reports_gap_then_delivers_what_is_left():
    bus = EventBus(capacity=1)
    srv = start(bus, queue.Queue())
    try:
        bus.publish({"event": "a"})
        bus.publish({"event": "b"})
        client = RawClient(srv.port)
        try:
            client.send({"hello": {"token": srv.token, "role": "wait", "after": 0, "timeout": 5.0}})
            client.read()
            replies = client.read_all()
            # The hole is reported first; event 2 is delivered in the same call.
            assert replies[0] == {"gap": True, "oldest": 2, "cursor": 2}
            assert replies[1]["event"] == "b" and replies[1]["seq"] == 2
        finally:
            client.close()
    finally:
        srv.stop()


def test_wait_kinds_filter_skips_observations(server):
    client = RawClient(server.port)
    try:
        client.send({"hello": {"token": server.token, "role": "wait", "after": 0,
                               "timeout": 0.5, "kinds": [KIND_WAKE]}})
        client.read()
        server.bus.publish({"event": "see", "kind": KIND_OBSERVATION})
        started = time.monotonic()
        assert client.read(timeout=2.0) == {"timeout": True, "cursor": 0}, "a timeout consumes nothing"
        assert time.monotonic() - started >= 0.4, "an observation must not release a wake waiter"
    finally:
        client.close()


class _BoomTouched(RuntimeError):
    pass


class _Boom:
    """Stands in for WorldState: touching it at all is a boundary violation."""

    def __getattr__(self, name):
        raise _BoomTouched(f"channel code reached the world: .{name}")

    def __call__(self, *args, **kwargs):
        raise _BoomTouched("channel code called the world")


def test_channel_threads_never_touch_the_world(monkeypatch):
    """Full hello/send/wait flow while every world handle is booby-trapped."""
    import metaverse.server as server_module

    monkeypatch.setattr(server_module, "_current_ws", _Boom(), raising=False)
    monkeypatch.setattr(server_module, "_current_ctx", _Boom(), raising=False)
    errors: list[BaseException] = []
    previous_hook = threading.excepthook
    threading.excepthook = lambda args: errors.append(args.exc_value)
    srv = start(EventBus(), queue.Queue())
    try:
        client = RawClient(srv.port)
        try:
            client.send({"hello": {"token": srv.token, "role": "wait", "after": 0, "timeout": 0.1}})
            client.read()
            assert client.read(timeout=2.0) == {"timeout": True, "cursor": 0}
        finally:
            client.close()

        client = RawClient(srv.port)
        try:
            client.send({"hello": {"token": srv.token, "role": "send"}})
            client.read()
            client.send({"cmd": {"cmd": "pos"}})
            # The channel must not answer by itself: only the frame loop can.
            pending = srv.cmd_queue.get(timeout=2.0)
            assert pending.cmd == {"cmd": "pos"}
            assert srv.bus.cursor() == 0
            pending.deliver({"type": "position", "x": 3.5, "y": 4.5})
            assert client.read(timeout=2.0)["ack"] == {"type": "position", "x": 3.5, "y": 4.5}
        finally:
            client.close()
    finally:
        srv.stop()
        threading.excepthook = previous_hook

    assert errors == [], f"a channel thread touched the world: {errors}"


def test_channel_file_roundtrip(tmp_path):
    path = str(tmp_path / ".channel.json")
    assert channel_server.read_channel_file(path) is None
    info = channel_server.write_channel_file(51234, "deadbeef", path=path, pid=os.getpid())
    assert channel_server.read_channel_file(path) == info
    assert info["protocol"] == channel_server.PROTOCOL and info["port"] == 51234
    channel_server.clear_channel_file(path, pid=os.getpid() + 1)
    assert channel_server.read_channel_file(path) is not None, "another instance's file must survive"
    channel_server.clear_channel_file(path, pid=os.getpid())
    assert channel_server.read_channel_file(path) is None
