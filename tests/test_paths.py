"""The layout the launcher reports has to be the layout the code actually uses.

`--where` is only worth anything if it cannot drift: these tests tie every
reported path back to the module that owns it (the channel file an external
agent reads, the legacy jsonl files, the folder the snapshot command writes).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metaverse
from metaverse import _paths, local_agent
from metaverse.channel_client import DEFAULT_CURSOR_FILE
from metaverse.channel_server import CHANNEL_FILE

PACKAGE = Path(metaverse.__file__).resolve().parent


def test_reported_paths_are_the_ones_the_owning_modules_use():
    paths = _paths.runtime_paths()
    assert paths["channel"] == Path(CHANNEL_FILE)
    assert paths["cursor"] == Path(DEFAULT_CURSOR_FILE)
    assert paths["commands"] == Path(local_agent.CMD_FILE)
    assert paths["log"] == Path(local_agent.LOG_FILE)


def test_reported_paths_sit_beside_the_package():
    """The channel file is written next to the code (that is why a read-only
    install cannot run), and snapshots one directory up."""
    paths = _paths.runtime_paths()
    assert paths["channel"].parent == PACKAGE
    assert paths["snapshots"] == PACKAGE.parent / "snapshots"


def test_describe_reports_the_layout_and_flags_an_unwritable_install():
    lines = _paths.describe()
    text = "\n".join(lines)
    assert str(PACKAGE) in text, "the code directory must be in the answer"
    for name, path in _paths.runtime_paths().items():
        assert name in text and str(path) in text, f"{name} missing from --where"
    assert "✓" in text, "every writable path is marked"

    original = _paths._writable
    try:
        _paths._writable = lambda target: False          # a Program Files install
        assert "不可写" in "\n".join(_paths.describe())
        assert "不可写" in _paths.brief()
    finally:
        _paths._writable = original


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="ACLs are the Windows read-only case")
def test_a_directory_that_denies_writes_is_reported_unwritable(tmp_path):
    """The case the report exists for: a read-only install (Program Files).

    `os.access(dir, W_OK)` says True here — verified on this box under a deny
    ACE — so the check has to probe. If this test ever passes with a plain
    access() check, the report is lying to the user.
    """
    target = tmp_path / "site-packages" / "metaverse"
    target.mkdir(parents=True)
    user = os.environ.get("USERNAME", "")
    subprocess.run(["icacls", str(target), "/deny", f"{user}:(W)"], capture_output=True)
    try:
        assert _paths._writable(target / ".channel.json") is False
    finally:
        subprocess.run(["icacls", str(target), "/remove:d", user], capture_output=True)


def test_the_launcher_answers_where_without_touching_the_network(monkeypatch, capsys):
    """`--where` is the first thing a confused user runs: no update check, no
    game, no display — just the answer."""
    from metaverse import _update_check, launch

    def boom():
        raise AssertionError("--where must not reach the update check")

    monkeypatch.setattr(_update_check, "check_update", boom)
    monkeypatch.setattr(sys, "argv", ["ghostworld", "--where"])

    launch.main()

    out = capsys.readouterr().out
    assert str(PACKAGE) in out
    assert "运行时写入" in out
