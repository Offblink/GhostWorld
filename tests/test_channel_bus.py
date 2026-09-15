"""EventBus unit tests — cursor, capacity, concurrency, wakeup, filtering."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaverse.channel import KIND_OBSERVATION, KIND_WAKE, EventBus


def test_seq_is_monotonic():
    bus = EventBus()
    seqs = [bus.publish({"event": "x"}) for _ in range(5)]
    assert seqs == [1, 2, 3, 4, 5]
    assert bus.cursor() == 5
    assert all("ts" in e for e in bus.wait(0, timeout=0)[0])


def test_eviction_reports_gap():
    bus = EventBus(capacity=3)
    for i in range(5):
        bus.publish({"event": "e", "i": i})
    events, cursor, gap = bus.wait(0, timeout=0)
    assert gap is True, "cursor older than the retained window must report a gap"
    assert [e["seq"] for e in events] == [3, 4, 5]
    assert cursor == 5
    assert bus.oldest == 3
    # Re-waiting from the returned cursor reports no second gap for the same loss.
    assert bus.wait(cursor, timeout=0) == ([], 5, False)


def test_events_are_append_only_and_ordered():
    bus = EventBus(capacity=10)
    for i in range(4):
        bus.publish({"event": "e", "i": i})
    first, cursor, gap = bus.wait(0, timeout=0)
    assert [(e["seq"], e["i"]) for e in first] == [(1, 0), (2, 1), (3, 2), (4, 3)]
    assert gap is False
    # Nothing new: the same cursor must not replay anything.
    assert bus.wait(cursor, timeout=0)[0] == []
    bus.publish({"event": "e", "i": 4})
    tail, cursor2, _ = bus.wait(cursor, timeout=0)
    assert [(e["seq"], e["i"]) for e in tail] == [(5, 4)]
    assert cursor2 == 5


def test_concurrent_publish_assigns_unique_seqs():
    bus = EventBus(capacity=2000)
    per_thread = 250
    threads = [
        threading.Thread(target=lambda tag=n: [bus.publish({"event": "e", "t": tag}) for _ in range(per_thread)])
        for n in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events, cursor, gap = bus.wait(0, timeout=0)
    seqs = [e["seq"] for e in events]
    assert len(seqs) == 4 * per_thread
    assert len(set(seqs)) == 4 * per_thread, "seq must be unique under concurrent publish"
    assert seqs == sorted(seqs)
    assert seqs == list(range(1, 4 * per_thread + 1))
    assert cursor == 4 * per_thread
    assert gap is False


def test_wait_is_woken_by_publish():
    bus = EventBus()
    result = {}

    def waiter():
        events, cursor, gap = bus.wait(None, timeout=5.0)
        result["woke_at"] = time.monotonic()
        result["events"] = events
        result["cursor"] = cursor
        result["gap"] = gap

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.1)
    assert t.is_alive(), "wait must block while nothing is published"
    published_at = time.monotonic()
    bus.publish({"event": "heard", "kind": KIND_WAKE, "message": "hi"})
    t.join(5.0)
    assert not t.is_alive()
    latency = result["woke_at"] - published_at
    assert latency < 0.05, f"publish must wake the waiter, took {latency:.4f}s"
    assert [e["message"] for e in result["events"]] == ["hi"]
    assert result["gap"] is False


def test_wake_releases_waiter_without_events():
    bus = EventBus()
    result = {}

    def waiter():
        returned = bus.wait(None, timeout=5.0)
        result["woke_at"] = time.monotonic()
        result["returned"] = returned

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.1)
    woken_at = time.monotonic()
    bus.wake()
    t.join(5.0)
    assert not t.is_alive(), "wake() must release a waiter"
    assert result["woke_at"] - woken_at < 0.05
    assert result["returned"] == ([], 0, False)


def test_kinds_filter_keeps_observations_in_buffer():
    bus = EventBus(capacity=10)
    bus.publish({"event": "see", "kind": KIND_OBSERVATION})
    bus.publish({"event": "heard", "kind": KIND_WAKE, "message": "yo"})
    bus.publish({"event": "goto_done", "kind": KIND_OBSERVATION})

    events, cursor, gap = bus.wait(0, timeout=0, kinds={KIND_WAKE})
    assert [e["event"] for e in events] == ["heard"]
    assert cursor == 3, "cursor must advance past filtered-out events"
    assert gap is False
    assert [e["event"] for e in bus.wait(0, timeout=0, kinds={KIND_OBSERVATION})[0]] == ["see", "goto_done"]
    assert [e["event"] for e in bus.wait(0, timeout=0)[0]] == ["see", "heard", "goto_done"]


def test_capacity_zero_is_live_only():
    bus = EventBus(capacity=0)
    for i in range(3):
        bus.publish({"event": "e", "i": i})
    events, cursor, gap = bus.wait(0, timeout=0)
    assert events == [], "capacity 0 keeps nothing"
    assert gap is True
    assert cursor == 3
    assert bus.oldest == 4
    # Nothing is retained, so even a wait started at the live cursor can only
    # report the loss — capacity 0 is a degeneracy guard, not a delivery mode.
    result = {}

    def waiter():
        result["returned"] = bus.wait(3, timeout=5.0)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.1)
    assert t.is_alive()
    bus.publish({"event": "e", "i": 3})
    t.join(5.0)
    events, cursor, gap = result["returned"]
    assert events == []
    assert (cursor, gap) == (4, True)


def test_capacity_one_keeps_the_newest():
    bus = EventBus(capacity=1)
    bus.publish({"event": "e", "i": 0})
    bus.publish({"event": "e", "i": 1})
    events, _cursor, gap = bus.wait(0, timeout=0)
    assert [(e["seq"], e["i"]) for e in events] == [(2, 1)]
    assert gap is True, "seq 1 was evicted before the caller saw it"
    assert bus.oldest == 2
    # A caller that already saw seq 1 lost nothing.
    events, cursor, gap = bus.wait(1, timeout=0)
    assert [(e["seq"], e["i"]) for e in events] == [(2, 1)]
    assert (cursor, gap) == (2, False)
    assert bus.wait(2, timeout=0) == ([], 2, False)
    # Cursor 0 never saw seq 1, which is gone: that is a gap.
    assert bus.wait(0, timeout=0)[1:] == (2, True)


def test_timeout_returns_unchanged_cursor():
    bus = EventBus()
    bus.publish({"event": "e"})
    started = time.monotonic()
    events, cursor, gap = bus.wait(1, timeout=0.05)
    assert time.monotonic() - started >= 0.04
    assert events == []
    assert cursor == 1, "a timeout must not consume anything"
    assert gap is False
