"""listen.py cursors: rotation and restart must not lose or replay events."""
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LISTEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "metaverse", "tools", "listen.py")


def _load():
    """metaverse/tools is not a package — load the tool by path."""
    spec = importlib.util.spec_from_file_location("gw_listen_under_test", LISTEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_log(path, seqs, heard_at=None, from_="player"):
    """Write a log where every seq in `seqs` has a line; `heard_at` is a player message."""
    with open(path, "w", encoding="utf-8") as f:
        for seq in seqs:
            if seq == heard_at:
                evt = {"event": "heard", "from": from_, "message": f"m{seq}", "kind": "wake", "seq": seq}
            else:
                evt = {"event": "see", "kind": "observation", "seq": seq}
            f.write(json.dumps(evt) + "\n")


def test_poll_advances_by_seq_without_replaying(tmp_path, monkeypatch):
    listen = _load()
    log = str(tmp_path / "agent_output.jsonl")
    monkeypatch.setattr(listen, "OUTPUT_FILE", log)
    monkeypatch.setattr(listen, "CURSOR_FILE", str(tmp_path / "listen_cursor.json"))

    _write_log(log, [1, 2, 3], heard_at=2)
    assert listen.poll() == ["m2"]
    assert json.loads(open(listen.CURSOR_FILE, encoding="utf-8").read()) == {"seq": 3}
    # the whole file is still there, and nothing is delivered twice
    assert listen.poll() == []

    _write_log(log, [1, 2, 3, 4], heard_at=4)
    assert listen.poll() == ["m4"]
    assert listen.poll() == []


def test_poll_reports_rotation_instead_of_replaying(tmp_path, monkeypatch, capsys):
    listen = _load()
    log = str(tmp_path / "agent_output.jsonl")
    cursor = str(tmp_path / "listen_cursor.json")
    monkeypatch.setattr(listen, "OUTPUT_FILE", log)
    monkeypatch.setattr(listen, "CURSOR_FILE", cursor)

    _write_log(log, [1, 2, 3], heard_at=1)
    assert listen.poll() == ["m1"]

    # the sink rotated the log: the newest lines survive, the head is gone
    _write_log(log, [20, 21, 22], heard_at=21)
    assert listen.poll() == ["m21"], "events after the cursor must still arrive"
    assert "rotated away" in capsys.readouterr().err
    assert json.loads(open(cursor, encoding="utf-8").read()) == {"seq": 22}
    assert listen.poll() == [], "rotated lines must not be replayed"


def test_poll_survives_a_restart_without_replaying(tmp_path, monkeypatch, capsys):
    listen = _load()
    log = str(tmp_path / "agent_output.jsonl")
    cursor = str(tmp_path / "listen_cursor.json")
    monkeypatch.setattr(listen, "OUTPUT_FILE", log)
    monkeypatch.setattr(listen, "CURSOR_FILE", cursor)

    _write_log(log, [40, 41, 42], heard_at=42)
    assert listen.poll() == ["m42"]

    # a new game process starts the log over: seq restarts at 1
    _write_log(log, [1, 2], heard_at=2)
    assert listen.poll() == ["m2"], "a fresh log must be read, not skipped"
    assert "newer run" in capsys.readouterr().err
    assert json.loads(open(cursor, encoding="utf-8").read()) == {"seq": 2}
    assert listen.poll() == [], "the restart must not be replayed"


def test_agent_speech_is_not_reported_as_player_chat(tmp_path, monkeypatch):
    listen = _load()
    log = str(tmp_path / "agent_output.jsonl")
    monkeypatch.setattr(listen, "OUTPUT_FILE", log)
    monkeypatch.setattr(listen, "CURSOR_FILE", str(tmp_path / "listen_cursor.json"))

    _write_log(log, [1], heard_at=1, from_="omp")
    assert listen.poll() == []
