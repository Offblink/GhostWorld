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


def test_startup_lines_carry_the_paths_the_windows_show():
    """Every entry point shows these on start — GUI ones have no console."""
    lines = _paths.startup_lines({"项目": Path("X:/proj")})
    text = "\n".join(lines)
    assert str(_paths.PACKAGE_DIR) in text and str(_paths.ROOT_DIR) in text
    for name, path in _paths.runtime_paths().items():
        assert name in text and str(path) in text, f"{name} missing from the startup block"
    assert "项目" in text, "an entry point's own path must show up too"


def test_the_launcher_prints_the_paths_on_every_start(capsys):
    from metaverse import launch

    launch._print_startup_paths()

    out = capsys.readouterr().out
    assert str(_paths.PACKAGE_DIR) in out
    assert str(_paths.ROOT_DIR) in out
    assert out.count("[launcher]") >= 4, "the block is printed line by line, prefixed"


def test_the_editor_window_shows_the_paths_without_asking(tmp_path):
    """The editor is a .pyw — no console — so the paths go into the window."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from editor.window import EditorWindow

    app = QApplication.instance() or QApplication([])
    win = EditorWindow(project_dir=str(tmp_path))
    try:
        shown = win._paths_label.text()
        assert str(tmp_path) in shown, "the project directory must be visible"
        assert str(_paths.PACKAGE_DIR) in shown, "which copy is running must be visible"
        tooltip = win._paths_label.toolTip()
        assert str(_paths.ROOT_DIR) in tooltip and "运行时写入" in tooltip
    finally:
        win.close()
        app.processEvents()


def test_the_startup_block_is_only_paths():
    """Whatever the user installed is where it is — no labels, no advice."""
    text = "\n".join(_paths.startup_lines({"项目": Path(".")}))
    assert "pip install" not in text and "源码检出" not in text and "不可写" not in text
    assert text.count(str(_paths.PACKAGE_DIR)) >= 1


def test_the_reported_version_is_the_one_this_checkout_declares():
    """The banner says which copy runs, so it cannot report stale metadata."""
    import re as _re

    declared = _re.search(r'^version\s*=\s*"([^"]+)"',
                          (_paths.ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"), _re.M).group(1)
    assert _paths.version_string().startswith(declared)
    assert declared in "\n".join(_paths.startup_lines())


