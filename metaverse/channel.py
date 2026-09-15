"""Event bus — the only object a channel thread is allowed to touch.

Pure logic, zero IO: a monotonic sequence number, a bounded buffer, and a
``threading.Condition`` so a waiter blocks until something happens instead of
polling.  Nothing in this module reads or writes ``WorldState`` — the world stays
single-threaded and is only mutated by the frame loop.

Vocabulary (seq / cursor / gap) is the one described in
``docs/DESIGN-agent-channel.md``: every event carries ``seq`` (monotonic),
``ts`` (epoch seconds) and ``kind`` (``wake`` for player speech, ``observation``
for everything else).
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque

DEFAULT_CAPACITY = 1000
KIND_WAKE = "wake"
KIND_OBSERVATION = "observation"

__all__ = ["EventBus", "FileSink", "PendingCommand", "KIND_WAKE", "KIND_OBSERVATION"]


class EventBus:
    """Monotonic-seq event buffer with blocking waits.

    Producers call :meth:`publish`; consumers call :meth:`wait` with the cursor
    they last saw.  A consumer whose cursor is older than the retained window is
    told ``gap=True`` rather than silently missing events.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._capacity = max(0, int(capacity))
        self._events: deque[dict] = deque(maxlen=self._capacity)
        self._seq = 0
        self._wake_gen = 0
        self._cond = threading.Condition()

    # ── producer side ────────────────────────────────────────────────

    def publish(self, evt: dict) -> int:
        """Append an event, wake waiters, return its seq."""
        with self._cond:
            self._seq += 1
            event = dict(evt)
            event["seq"] = self._seq
            event.setdefault("ts", time.time())
            event.setdefault("kind", KIND_OBSERVATION)
            self._events.append(event)
            self._cond.notify_all()
            return self._seq

    def wake(self) -> None:
        """Release waiters without publishing anything (timeout / shutdown).

        A plain notify is not enough: the wait loop re-blocks when no matching
        event arrived, so the release is tracked by a generation counter.
        """
        with self._cond:
            self._wake_gen += 1
            self._cond.notify_all()

    # ── consumer side ────────────────────────────────────────────────

    def cursor(self) -> int:
        """Latest published seq."""
        with self._cond:
            return self._seq

    @property
    def oldest(self) -> int:
        """Earliest seq still retrievable (the next seq, if the buffer is empty)."""
        with self._cond:
            return self._lost_upto() + 1

    def wait(
        self,
        after: int | None = None,
        timeout: float | None = None,
        kinds: set[str] | None = None,
    ) -> tuple[list[dict], int, bool]:
        """Block until an event newer than ``after`` exists.

        Parameters
        ----------
        after:
            Last seq the caller has seen; ``None`` means "only what is published
            from now on".
        timeout:
            Seconds to block, ``None`` blocks forever.
        kinds:
            When given, only return events whose ``kind`` is in this set.  The
            returned cursor still advances past the filtered-out events.

        Returns
        -------
        (events, cursor, gap)
            ``gap`` is True when events newer than ``after`` were already
            evicted — the caller must not assume it has seen everything.
            ``cursor`` is the position the caller is now caught up to: the latest
            seq when events came back, otherwise the (gap-adjusted) ``after``,
            so a timeout never consumes anything.
        """
        with self._cond:
            if after is None:
                after = self._seq
            gap = False
            start_gen = self._wake_gen
            deadline = None if timeout is None else time.monotonic() + timeout
            while True:
                lost_upto = self._lost_upto()
                if after < lost_upto:
                    gap = True
                    after = lost_upto
                pending = [
                    e for e in self._events
                    if e["seq"] > after and (kinds is None or e["kind"] in kinds)
                ]
                if pending:
                    return pending, self._seq, gap
                if gap:
                    return [], after, True
                if self._wake_gen != start_gen:
                    return [], after, False
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return [], after, False
                    self._cond.wait(remaining)

    def _lost_upto(self) -> int:
        """Newest seq that can no longer be retrieved. Caller holds the lock."""
        return self._seq if not self._events else self._events[0]["seq"] - 1


class PendingCommand:
    """A command posted by a channel thread, executed by the frame loop.

    The posting thread blocks in :meth:`result` and never touches ``WorldState``.
    """

    __slots__ = ("cmd", "_done", "_resp", "_timeout")

    def __init__(self, cmd: dict, timeout: float = 10.0) -> None:
        self.cmd = cmd
        self._done = threading.Event()
        self._resp: dict | None = None
        self._timeout = timeout

    def deliver(self, resp: dict | None) -> None:
        """Called by the frame loop once the command has been executed."""
        self._resp = resp
        self._done.set()

    def result(self, timeout: float | None = None) -> dict | None:
        """Block until the frame loop delivers a response. None on timeout."""
        if not self._done.wait(self._timeout if timeout is None else timeout):
            return None
        return self._resp


class FileSink:
    """Append bus events to a JSONL file — the legacy ``agent_output.jsonl``.

    A subscriber, not a producer: the file is a projection of the bus, so events
    published anywhere (including the server's ``heard``) land in it.  Writing is
    best-effort — a file error must never stop the world.
    """

    def __init__(self, bus: EventBus, path: str, max_lines: int = 2000, echo: bool = False):
        self.bus = bus
        self.path = path
        self.max_lines = max_lines
        self.echo = echo
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cursor = 0
        self._written = 0

    def start(self) -> None:
        """Begin a new log generation and start appending bus events."""
        # Start from the oldest retained event, not from "now": the sink may be
        # created after the events it is supposed to record (e.g. the launcher's
        # config_read line) were published.
        self._cursor = self.bus.oldest - 1
        try:
            with open(self.path, "w", encoding="utf-8"):
                pass
        except OSError:
            pass
        self._written = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ghostworld-log-sink", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self.bus.wake()  # release the blocking wait
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            events, cursor, _gap = self.bus.wait(self._cursor, timeout=None, kinds=None)
            self._cursor = cursor
            for evt in events:
                self._write(evt)

    def _write(self, evt: dict) -> None:
        line = json.dumps(evt, ensure_ascii=False)
        if self.echo:
            print(line, flush=True)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._written += 1
        except OSError:
            return
        if self.max_lines and self._written > self.max_lines:
            try:
                self._rotate()
            except OSError:
                # A reader holding the file open on Windows can refuse the swap;
                # the file is append-only, so retry after another batch.
                self._written = self.max_lines - 100

    def _rotate(self) -> None:
        """Keep the newest half of the log (rotation by seq boundary, not line index)."""
        keep = max(1, self.max_lines // 2)
        with open(self.path, encoding="utf-8") as f:
            lines = f.readlines()
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(lines[-keep:])
            os.replace(tmp, self.path)
        except OSError:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            raise
        self._written = min(len(lines), keep)
