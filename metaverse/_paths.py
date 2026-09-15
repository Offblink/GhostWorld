"""Where this copy lives, and which files the game writes while it runs.

`pip show ghostworld` answers "where did the files go"; nothing answers "which
directory will the game write into" — and that is the one that decides whether
an install works at all (a site-packages under Program Files is read-only, and
the channel discovery file has to be created next to the code).

`python -m metaverse.launch --where` prints this; the launcher prints the short
form on every start. Stdlib only: a diagnostics question must not need pygame,
a display, or the network.
"""
from __future__ import annotations

import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent


def version_string() -> str:
    try:
        return version("ghostworld")
    except PackageNotFoundError:
        return "unknown (not installed — a source checkout?)"


def runtime_paths() -> dict[str, Path]:
    """Every file the running game writes, named the way its owner module does.

    Keep these in step with the code: `.channel.json` is
    `channel_server.CHANNEL_FILE` (the file an external agent reads to find the
    game), the cursor and the two legacy jsonl files sit next to it, and the
    `snapshot` command saves PNGs one directory up.
    """
    return {
        "channel": PACKAGE_DIR / ".channel.json",
        "cursor": PACKAGE_DIR / ".wait_cursor.json",
        "commands": PACKAGE_DIR / "agent_commands.jsonl",
        "log": PACKAGE_DIR / "agent_output.jsonl",
        "snapshots": ROOT_DIR / "snapshots",
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
    return "源码检出" if (ROOT_DIR / "pyproject.toml").is_file() else "site-packages 安装"


def brief() -> str:
    """One line for the launcher banner: where the code is, and whether it can write."""
    paths = runtime_paths()
    ok = all(_writable(path) for path in paths.values())
    return f"代码 {PACKAGE_DIR} · 运行时写入 {PACKAGE_DIR} ({'可写' if ok else '不可写 —— 见 --where'})"


def describe() -> list[str]:
    """The full answer to "where did it go", for `--where`."""
    examples = ROOT_DIR / "examples"
    maps = sorted(examples.glob("*.json")) if examples.is_dir() else []
    lines = [
        f"GhostWorld {version_string()}",
        f"Python     {sys.version.split()[0]}  ({sys.executable})",
        f"代码目录   {PACKAGE_DIR}",
        f"安装根     {ROOT_DIR}   [{installed_layout()}]",
        f"示例地图   {len(maps)} 张" + ("" if maps else "   ← 包里没有 examples/，启动会用代码里的内建地图"),
        "运行时写入：",
    ]
    for name, path in runtime_paths().items():
        ok = _writable(path)
        lines.append(f"  {'✓' if ok else '✗'} {name:<9} {path}" + ("" if ok else "   ← 不可写！换用户级安装，别装在 Program Files"))
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


def main() -> int:
    print("\n".join(describe()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
