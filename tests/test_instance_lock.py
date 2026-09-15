"""The instance lock may only end a process it can recognise.

A stale lock file plus a reused pid used to mean `taskkill /F` on whatever had
inherited that number — the one way simply starting the game could hurt an
unrelated program on the machine. These tests pin the decision, not the OS
calls: every branch that says "kill" or "don't" is exercised with a fake pid
table, so nothing real is ever terminated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaverse import launch


def _fake_identity(monkeypatch, table):
    """table: pid -> (image, creation) or None."""
    monkeypatch.setattr(launch, "_process_identity", lambda pid: table.get(pid))


def test_a_reused_pid_is_not_our_instance(monkeypatch):
    """Same number, different creation time: that is somebody else's program."""
    _fake_identity(monkeypatch, {4242: ("C:/x/python.exe", 999.0)})
    assert launch._stale_owner(4242, 111.0) is False


def test_the_same_creation_time_is_our_old_instance(monkeypatch):
    _fake_identity(monkeypatch, {4242: ("C:/x/python.exe", 111.0)})
    assert launch._stale_owner(4242, 111.0) is True


def test_a_dead_pid_is_not_killed(monkeypatch):
    _fake_identity(monkeypatch, {})
    assert launch._stale_owner(4242, 111.0) is False


def test_a_lock_without_a_creation_time_is_never_trusted(monkeypatch):
    """Old-format lock: unverifiable, so it buys nothing."""
    looked = []
    monkeypatch.setattr(
        launch, "_process_identity", lambda pid: looked.append(pid) or ("C:/x/python.exe", 5.0)
    )
    assert launch._stale_owner(4242, None) is False
    assert looked == [], "not even worth looking: the file alone is not evidence"


def test_acquiring_ends_a_verified_old_instance_only(tmp_path, monkeypatch):
    lock = tmp_path / ".instance.lock"
    lock.write_text("4242 111.000000")
    monkeypatch.setattr(launch, "LOCK_FILE", str(lock))
    ended = []
    monkeypatch.setattr(launch, "_end_instance", ended.append)
    _fake_identity(monkeypatch, {4242: ("C:/x/python.exe", 111.0), os.getpid(): ("C:/x/python.exe", 7.5)})

    launch._acquire_lock()

    assert ended == [4242], "the instance we can recognise goes"
    assert launch._read_lock() == (os.getpid(), 7.5), "the file now names us, with our creation time"


def test_acquiring_spares_a_foreign_owner(tmp_path, monkeypatch):
    lock = tmp_path / ".instance.lock"
    lock.write_text("4242 111.000000")
    monkeypatch.setattr(launch, "LOCK_FILE", str(lock))
    ended = []
    monkeypatch.setattr(launch, "_end_instance", ended.append)
    _fake_identity(monkeypatch, {4242: ("C:/Windows/explorer.exe", 555.0), os.getpid(): ("C:/x/python.exe", 7.5)})

    launch._acquire_lock()

    assert ended == [], "a stale lock naming someone else's pid must not kill them"
    assert launch._read_lock()[0] == os.getpid()


def test_a_legacy_lock_file_still_reads(tmp_path, monkeypatch):
    lock = tmp_path / ".instance.lock"
    lock.write_text("4242")
    monkeypatch.setattr(launch, "LOCK_FILE", str(lock))
    assert launch._read_lock() == (4242, None)
