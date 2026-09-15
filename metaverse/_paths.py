"""Where this copy lives, and which files the game writes while it runs.

`pip show ghostworld` answers "where did the files go"; nothing answers "which
directory will the game write into" — and that is the one that decides whether
an install works at all (a site-packages under Program Files is read-only, and
the channel discovery file has to be created next to the code).

`python -m metaverse.launch --where` prints this; every entry point shows
`startup_lines()` on start. Stdlib only: a diagnostics question must not need pygame,
a display, or the network.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
APP_DIR_NAME = "GhostWorld"          # %LOCALAPPDATA%\GhostWorld in a frozen build
CLI_EXE = "GhostWorldCLI.exe"        # the console companion a frozen build ships


def is_frozen() -> bool:
    """True inside a PyInstaller build — one file or one folder, same answer."""
    return bool(getattr(sys, "frozen", False))


def runtime_dir() -> Path:
    """Where the running copy writes.

    A checkout writes beside the code: the channel file has to be where its
    readers look, and a checkout is writable by definition. A frozen build
    cannot — its code sits in an install directory that may be read-only
    (Program Files) or, for a one-file build, in a temporary unpack directory
    that is deleted on exit. So every writable file moves under the user's own
    directory, where it also survives an upgrade.
    """
    if not is_frozen():
        return PACKAGE_DIR
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_DIR_NAME


def examples_dir() -> Path:
    """The maps to open: the checkout's `examples/`, or the frozen user copy."""
    return runtime_dir() / "examples" if is_frozen() else ROOT_DIR / "examples"


def app_dir() -> Path:
    """The directory a user would call the install root: the exe's, or the checkout's.

    `ROOT_DIR` is where the *code* sits, which inside a frozen build is the
    unpacked bundle (`_internal/`), not the folder the exe lives in. Anything
    that hands a path to a human or to another program wants this one.
    """
    return Path(sys.executable).parent if is_frozen() else ROOT_DIR


def seed_examples() -> Path:
    """The writable examples directory, filled from the bundle on first run.

    Maps are data the user edits, and the game writes `states/` beside them, so
    a frozen build cannot open the copies it ships. It copies them out once and
    never overwrites a file that is already there.
    """
    target = examples_dir()
    if not is_frozen():
        return target
    target.mkdir(parents=True, exist_ok=True)
    bundled = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "examples"
    if bundled.is_dir() and bundled.resolve() != target.resolve():
        for src in sorted(bundled.glob("*.json")):
            dst = target / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
    return target


def launch_config_file() -> Path:
    """Written by the GUI launcher, read by the game — one location for both."""
    return runtime_dir() / "launch_config.json"


def lock_file() -> Path:
    """The single-instance lock (see `launch._acquire_lock`)."""
    return runtime_dir() / ".instance.lock"


def _source_version() -> str | None:
    """The version this copy declares, if the declaration is beside it.

    The installed metadata lags until the next `pip install`, and this line
    exists to say which copy is running — so it must not lag with it. A frozen
    build carries `pyproject.toml` inside itself for the same reason: the exe
    reports the version it was built from, not whatever pip saw last.
    """
    pyproject = ROOT_DIR / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else None


def version_string() -> str:
    source = _source_version()
    try:
        installed = version("ghostworld")
    except PackageNotFoundError:
        return source or "unknown (not installed — a source checkout?)"
    return source or installed


def runtime_paths() -> dict[str, Path]:
    """Every file the running game writes, named the way its owner module does.

    Keep these in step with the code: `.channel.json` is
    `channel_server.CHANNEL_FILE` (the file an external agent reads to find the
    game), the cursor and the two legacy jsonl files sit next to it, and the
    `snapshot` command saves PNGs in `snapshots/` — beside the code in a
    checkout (which is where its readers look), under the app directory when
    frozen, where the install cannot be read-only.
    """
    base = runtime_dir()
    snapshots = base / "snapshots" if is_frozen() else ROOT_DIR / "snapshots"
    return {
        "channel": base / ".channel.json",
        "cursor": base / ".wait_cursor.json",
        "commands": base / "agent_commands.jsonl",
        "log": base / "agent_output.jsonl",
        "snapshots": snapshots,
    }


def _writable(target: Path) -> bool:
    """Writable now, probed rather than guessed.

    `os.access(dir, W_OK)` answers True even where a write is denied — measured
    on Windows with a deny-ACE on the package directory — and that is exactly
    the install this report exists for (a site-packages under Program Files).
    So try it for real: create and remove a probe file in the directory the
    path needs, walking up when that directory does not exist yet.
    """
    directory = target if target.is_dir() else target.parent
    while not directory.exists() and directory != directory.parent:
        directory = directory.parent
    probe = directory / f".ghostworld-write-probe-{os.getpid()}"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError:
        return False
    try:
        probe.unlink()
    except OSError:
        pass
    return True


def installed_layout() -> str:
    if is_frozen():
        return "打包 exe"
    return "源码检出" if (ROOT_DIR / "pyproject.toml").is_file() else "site-packages 安装"


def startup_lines(extra: dict[str, Path] | None = None) -> list[str]:
    """The paths every entry point shows on start.

    `--where` answers the question in full, but it has to be asked for; this is
    the part worth seeing without asking: which directories this copy lives in,
    and which files it will write. The GUI entry points have no console
    (`launcher.pyw`, `editor.pyw` are `.pyw`), so they render these lines in the
    window instead of printing them.

    *extra* adds paths an entry point owns rather than the game (the editor's
    project directory).
    """
    extra = extra or {}
    lines = [
        f"GhostWorld {version_string()}",
        f"代码目录   {PACKAGE_DIR}",
        f"安装根     {ROOT_DIR}",
    ]
    for name, path in list(runtime_paths().items()) + list(extra.items()):
        lines.append(f"  {'✓' if _writable(path) else '✗'} {name:<9} {path}")
    return lines


def describe() -> list[str]:
    """The full answer to "where did it go", for `--where`."""
    examples = examples_dir()
    maps = sorted(examples.glob("*.json")) if examples.is_dir() else []
    if not maps and is_frozen():
        bundled = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "examples"
        maps = sorted(bundled.glob("*.json")) if bundled.is_dir() else []
    lines = [
        f"GhostWorld {version_string()}",
        f"Python     {sys.version.split()[0]}  ({sys.executable})",
        f"代码目录   {PACKAGE_DIR}",
        f"安装根     {ROOT_DIR}   [{installed_layout()}]",
    ]
    if is_frozen():
        # The one line that makes a frozen install understandable: the code above
        # is read-only (or temporary), so everything written lives down here.
        lines.append(f"运行时目录 {runtime_dir()}")
    lines += [
        f"示例地图   {len(maps)} 张" + ("" if maps else "   ← 包里没有 examples/，启动会用代码里的内建地图"),
        "运行时写入：",
    ]
    for name, path in runtime_paths().items():
        ok = _writable(path)
        lines.append(f"  {'✓' if ok else '✗'} {name:<9} {path}" + ("" if ok else "   ← 不可写！换用户级安装，别装在 Program Files"))
    if is_frozen():
        # Fungi drives the game through the channel CLI; a frozen build has no
        # `-m metaverse.cli_channel`, so it has to be pointed at the companion exe.
        lines += [
            "",
            "接 Fungi：这是打包版，没有 `python -m metaverse.cli_channel`：",
            f'  "ghostworld_dir": {json.dumps(str(app_dir()), ensure_ascii=False)}',
            f"  通道命令用 {CLI_EXE} send <json> / {CLI_EXE} wait [--timeout N]（参数同 ghostworld-send/wait）。",
        ]
        return lines
    # The one line the user actually needs next: Fungi drives the game by running
    # `python -m metaverse.cli_channel` from that directory, so this is what goes
    # into its config — the install root, not the package directory.
    lines += [
        "",
        "接 Fungi：把下面这一行填进 Fungi 的 config.json（键已存在就替换这一行）",
        f'  "ghostworld_dir": {json.dumps(str(ROOT_DIR), ensure_ascii=False)}',
        "  （就是上面的「安装根」；留空也行，前提是 ghostworld-send 命令在 PATH 上）",
    ]
    return lines


def utf8_stdio() -> None:
    """Pin this process's pipes to UTF-8 — what every consumer assumes.

    A console Python talks UTF-8 to its terminal, but a *piped* child falls back
    to the ANSI code page (cp936 on this box), which turns the player's 你好 into
    U+FFFD and cannot even encode the ✓/✗ this module prints (2026-09-15). Both
    the channel CLI and `--where` are read through pipes by whoever launched
    them, so both fix their own encoding next to owning their own output.

    A windowed frozen build has no streams at all: `sys.stdout is None`, every
    call here is then a no-op.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") == "utf8":
            continue  # already there (a harness that exports PYTHONUTF8) — no work
        with contextlib.suppress(Exception):  # in-process use, or a replaced stream
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    utf8_stdio()
    print("\n".join(describe()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
