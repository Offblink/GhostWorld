"""End-to-end: real socket, real frame loop, the shipped client.

The two exercises here are the ones that decide whether the channel is worth
anything: is a parked waiter *pushed* the player's line, and do the legacy files
still behave for everything already built on them.
"""
import asyncio
import contextlib
import json
import os
import shutil
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaverse.channel_client import ChannelClient, ChannelTimeout
from metaverse.channel_server import close_channel, open_channel
from metaverse.server import _tick_loop_sync, handle_message, init_server

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
MAP_A = os.path.join(FIXTURES, "_test_A.json")
TICK = 0.02
WAKE = {"wake"}


class _Harness:
    """A world, a channel and a 20Hz frame loop — driven the way the game does."""

    def __init__(self, tmp_path) -> None:
        self.map_path = str(tmp_path / "_test_A.json")
        self.channel_path = str(tmp_path / ".channel.json")
        self.cursor_path = str(tmp_path / ".wait_cursor.json")

    async def __aenter__(self):
        shutil.copyfile(MAP_A, self.map_path)
        self.ws, self.ctx, _state = init_server(self.map_path)
        self.server = open_channel(self.ctx.bus, self.ctx.cmd_queue, path=self.channel_path)
        self._stop = threading.Event()
        self._ticker = asyncio.create_task(self._tick())
        # Both avatars exist before any command can arrive: the launcher connects
        # the agent (via local_agent_loop) and the client connects the player.
        handle_message(self.ws, self.ctx.agent_name, {"type": "connect", "owner": "agent"})
        handle_message(self.ws, "player", {"type": "connect", "owner": "human"})
        return self

    async def __aexit__(self, *exc):
        self._stop.set()
        self._ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._ticker
        close_channel(self.server, self.channel_path)

    async def _tick(self):
        while not self._stop.is_set():
            _tick_loop_sync(self.ctx, self.ws)
            await asyncio.sleep(TICK)

    def client(self) -> ChannelClient:
        return ChannelClient.from_file(self.channel_path, cursor_file=self.cursor_path)

    def say(self, message: str) -> None:
        """Exactly what LocalClient does when the player hits Enter."""
        handle_message(self.ws, "player", {"type": "say", "message": message, "channel": "global"})


def _swallow(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - the assertions in the test do the judging
        return e


def test_channel_end_to_end(tmp_path):
    asyncio.run(_exercise(tmp_path))


async def _exercise(tmp_path):
    async with _Harness(tmp_path) as h:
        client = h.client()

        # 1) a command makes a round trip: posted to the queue, run by the frame
        #    loop, answered over the same connection
        ack = await asyncio.to_thread(client.send, {"cmd": "pos"})
        assert ack["type"] == "position"
        assert isinstance(ack["x"], float) and isinstance(ack["y"], float)

        # 2) an observation alone never releases a wake waiter, and a timeout
        #    consumes nothing
        with pytest.raises(ChannelTimeout):
            await asyncio.to_thread(client.wait, 0.3, WAKE)

        # 3) a parked waiter is pushed the player's line, fast
        result: dict = {}

        def parked():
            result["at"] = time.monotonic()
            result["events"] = _swallow(lambda: client.wait(5.0, WAKE))

        th = threading.Thread(target=parked)
        th.start()
        await asyncio.sleep(0.2)
        assert th.is_alive(), "wait must block while the player is silent"
        said_at = time.monotonic()
        h.say("在吗")
        await asyncio.to_thread(th.join, 5.0)
        assert not th.is_alive()
        events = result["events"]
        assert isinstance(events, list), f"wait failed: {events}"
        latency = result["at"] - said_at
        assert latency < 0.05, f"the wake must be pushed, not polled; took {latency:.4f}s"
        assert (events[0]["event"], events[0]["kind"], events[0]["from"], events[0]["message"]) == (
            "heard", "wake", "player", "在吗")

        # 4) messages said while the agent is busy queue up; the next wait gets
        #    them all in one go (no turn can interrupt another)
        for m in ("一", "二", "三"):
            h.say(m)
        queued = await asyncio.to_thread(client.wait, 5.0, WAKE)
        assert [e["message"] for e in queued] == ["一", "二", "三"]

        # 5) a fresh process resumes from the persisted cursor: nothing replayed
        fresh = h.client()
        assert fresh.cursor == queued[-1]["seq"]
        with pytest.raises(ChannelTimeout):
            await asyncio.to_thread(fresh.wait, 0.3, WAKE)

        # 6) observations are kept and reachable by cursor — filtered out of the
        #    wake stream, not dropped
        seen = h.client()
        observed = await asyncio.to_thread(seen.wait, 5.0, {"observation"}, 0)
        assert any(e["event"] == "position" and "x" in e for e in observed)

        # 7) an observation published while someone is parked does not wake them
        obs_result: dict = {}

        def parked_wake_only():
            obs_result["events"] = _swallow(lambda: fresh.wait(2.0, WAKE))

        th2 = threading.Thread(target=parked_wake_only)
        th2.start()
        await asyncio.sleep(0.2)
        h.ctx.bus.publish({"event": "see", "avatars": {"omp": [1.0, 2.0]}})
        await asyncio.sleep(0.3)
        assert th2.is_alive(), "an observation must not release a wake waiter"
        h.say("醒醒")
        await asyncio.to_thread(th2.join, 5.0)
        assert not th2.is_alive()
        assert [e["message"] for e in obs_result["events"]] == ["醒醒"]

        # 8) parked = one blocking wait, no spin, no CPU
        calls = 0
        real_wait = h.ctx.bus.wait

        def counting(*a, **k):
            nonlocal calls
            calls += 1
            return real_wait(*a, **k)

        h.ctx.bus.wait = counting
        spinner = threading.Thread(target=lambda: _swallow(lambda: fresh.wait(1.5, WAKE)))
        spinner.start()
        await asyncio.sleep(0.5)
        cpu_before = time.process_time()
        await asyncio.sleep(0.5)
        cpu = time.process_time() - cpu_before
        assert spinner.is_alive(), "the waiter should still be parked"
        assert calls == 1, f"a parked waiter must sit in exactly one blocking wait, saw {calls}"
        assert cpu < 0.15, f"a parked channel must not burn CPU, used {cpu:.3f}s"
        await asyncio.to_thread(spinner.join, 5.0)


def test_legacy_files_keep_working(monkeypatch, tmp_path):
    import metaverse.local_agent as la

    monkeypatch.setattr(la, "LOG_FILE", str(tmp_path / "agent_output.jsonl"))
    monkeypatch.setattr(la, "CMD_FILE", str(tmp_path / "agent_commands.jsonl"))
    asyncio.run(_exercise_legacy(la, tmp_path))


async def _wait_for(path, predicate, timeout=5.0):
    """Wait for a line to show up in the legacy log (the sink writes from a thread)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except ValueError:
                        continue
                    if predicate(evt):
                        return evt
        except OSError:
            pass
        await asyncio.sleep(0.05)
    raise AssertionError(f"no matching line in {path} within {timeout}s")


async def _exercise_legacy(la, tmp_path):
    async with _Harness(tmp_path) as h:
        agent = asyncio.create_task(la.local_agent_loop("omp", h.ws, "", ctx=h.ctx))
        log = la.LOG_FILE
        try:
            connected = await _wait_for(log, lambda e: e.get("event") == "connected")
            assert "seq" in connected and connected["kind"] == "observation"

            # player speech reaches the legacy log through the bus, not a poll
            h.say("你好")
            heard = await _wait_for(log, lambda e: e.get("event") == "heard")
            assert (heard["from"], heard["message"], heard["kind"]) == ("player", "你好", "wake")

            # a hand-written legacy command is still executed (by the frame loop)
            with open(la.CMD_FILE, "w", encoding="utf-8") as f:
                f.write(json.dumps({"cmd": "pos"}) + "\n")
            position = await _wait_for(log, lambda e: e.get("event") == "position")
            assert "x" in position and "y" in position
            assert not os.path.exists(la.CMD_FILE), "the legacy file must be consumed"

            # a half-written line is reported, never silently dropped
            with open(la.CMD_FILE, "w", encoding="utf-8") as f:
                f.write('{"cmd":"pos"}\n{"broken\n')
            err = await _wait_for(log, lambda e: e.get("event") == "read_err")
            assert "unparsable" in err["error"]
        finally:
            agent.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await agent


def test_follow_streams_batches_and_survives_silence(tmp_path):
    asyncio.run(_exercise_follow(tmp_path))


async def _exercise_follow(tmp_path):
    """The recommended integration path: one long-lived watcher, zero polling."""
    async with _Harness(tmp_path) as h:
        client = h.client()
        stop = threading.Event()
        batches: list[list[dict]] = []
        errors: list[BaseException] = []

        def follower():
            try:
                for batch in client.iter_events(timeout=0.3, kinds=None, stop=stop.is_set):
                    batches.append(batch)
            except BaseException as e:  # noqa: BLE001 - reported by the assertions below
                errors.append(e)

        th = threading.Thread(target=follower)
        th.start()
        await asyncio.sleep(0.2)
        h.say("一")
        for _ in range(20):
            if batches:
                break
            await asyncio.sleep(0.05)
        assert [e["message"] for e in batches[0]] == ["一"], "the batch must be pushed, not polled"

        # silence must not end the watcher — a timeout just loops
        await asyncio.sleep(0.6)
        assert len(batches) == 1, "an idle timeout must not produce an empty batch"
        assert th.is_alive(), "the watcher must keep waiting after a timeout"

        h.say("二")
        h.say("三")
        for _ in range(20):
            if len(batches) > 1:
                break
            await asyncio.sleep(0.05)
        assert [e["message"] for e in batches[1]] == ["二", "三"], "queued speech arrives as one batch"

        stop.set()
        await asyncio.to_thread(th.join, 5.0)
        assert not th.is_alive(), "stop() must end the watcher"
        assert errors == []


def test_follow_ends_when_the_channel_goes_away(tmp_path):
    asyncio.run(_exercise_follow_exit(tmp_path))


async def _exercise_follow_exit(tmp_path):
    async with _Harness(tmp_path) as h:
        client = h.client()
        seen: list[dict] = []
        finished = threading.Event()

        def follower():
            for batch in client.iter_events(timeout=0.3, kinds=None):
                seen.extend(batch)
            finished.set()

        th = threading.Thread(target=follower)
        th.start()
        await asyncio.sleep(0.3)
        h.say("活着")
        for _ in range(20):
            if seen:
                break
            await asyncio.sleep(0.05)
        assert [e["message"] for e in seen] == ["活着"]

        close_channel(h.server, h.channel_path)  # the game exits
        await asyncio.to_thread(th.join, 5.0)
        assert finished.is_set(), "the watcher must end (not hang) when the game exits"
        assert [e["message"] for e in seen] == ["活着"]
