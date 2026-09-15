"""Metaverse launcher — one command to start everything.

Usage:
    python -m metaverse.launch                    # start human client + agent
    python -m metaverse.launch <map.json>         # specify map
    python -m metaverse.launch --help             # show options
"""
from __future__ import annotations
import sys as _sys; _sys.dont_write_bytecode = True
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import asyncio
import json
import os

from metaverse._paths import (
    examples_dir,
    launch_config_file,
    lock_file,
    runtime_dir,
    seed_examples,
)




LOCK_FILE = str(lock_file())


def _process_identity(pid: int) -> tuple[str, float] | None:
    """(image, creation time) of a live process, or None if it is gone.

    A pid is not an identity: the OS hands the same number out again, and that
    is how a stale lock file used to end up killing an unrelated program. The
    creation time is the part that does not come back.
    """
    if _sys.platform != "win32":
        # /proc field 22 = start time in clock ticks since boot (comm may hold spaces).
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                fields = f.read().rsplit(b")", 1)[1].split()
            return "proc", float(fields[19])
        except (OSError, IndexError, ValueError):
            return None
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if not k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        created = times[0]
        return buf.value, ((created.dwHighDateTime << 32) | created.dwLowDateTime) / 1e7
    finally:
        k.CloseHandle(handle)


def _read_lock() -> tuple[int, float | None] | None:
    """(pid, creation time) — locks written before 2026-09-15 hold only a pid."""
    try:
        with open(LOCK_FILE) as f:
            parts = f.read().split()
        return int(parts[0]), (float(parts[1]) if len(parts) > 1 else None)
    except (OSError, ValueError, IndexError):
        return None


def _stale_owner(pid: int, created: float | None) -> bool:
    """Still the instance that wrote the lock? Only a verifiable yes counts.

    A lock with no recorded creation time cannot be verified, so nothing is
    killed on its word: an unrelated program must never die for a stale file.
    """
    if created is None:
        return False
    identity = _process_identity(pid)
    return identity is not None and abs(identity[1] - created) < 0.5


def _end_instance(pid: int) -> None:
    if _sys.platform == "win32":
        import subprocess
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        import signal
        try:
            _os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def _acquire_lock() -> bool:
    """Singleton lock: end our own old instance, then claim the file.

    The pid is written together with the process's creation time, which is what
    makes the next launch able to tell "our old instance" from "some other
    program that happens to hold that pid now".
    """
    old = _read_lock()
    if old is not None and old[0] != _os.getpid() and _stale_owner(*old):
        _end_instance(old[0])
    mine = _process_identity(_os.getpid())
    with open(LOCK_FILE, "w") as f:
        f.write(f"{_os.getpid()} {mine[1]:.6f}" if mine else str(_os.getpid()))
    return True


def _resolve_map(path: str) -> str:
    if os.path.isabs(path):
        return path
    # Relative map paths — and `examples/...` in particular — resolve against the
    # directory that holds `examples/`: the checkout root, or the app directory
    # of a frozen build where the maps were seeded.
    return os.path.join(str(examples_dir().parent), path)


DEMO_MAP_NAME = "demo_metaverse.json"


def default_map() -> str:
    """The map to open when none was named: the last one used, else the demo.

    Seeding happens here rather than at import: it writes the user's directory,
    and importing a module must not.
    """
    examples = seed_examples()
    try:
        chosen = (examples / ".last_map").read_text(encoding="utf-8").strip()
        if chosen and os.path.isfile(chosen):
            return chosen
    except OSError:
        pass
    return str(examples / DEMO_MAP_NAME)

def _write_builtin_maps() -> str:
    """The maps compiled into the code, written out when the named one is gone.

    They go to the runtime directory, not a temp directory: the game saves
    `states/` beside a map, and a temp directory is wiped between runs — the
    world would reset and the maps would be re-created every launch.
    """
    import json

    from ghostengine._default_map import DEFAULT_MAP
    from ghostengine._default_map2 import DEFAULT_MAP2

    out = runtime_dir() / "builtin_maps"
    out.mkdir(parents=True, exist_ok=True)
    mp = out / "_default_map.json"
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_MAP, f, indent=2, ensure_ascii=False)
    with open(out / "_default_map2.json", "w", encoding="utf-8") as f:
        json.dump(DEFAULT_MAP2, f, indent=2, ensure_ascii=False)
    print("[launcher] Using default demo maps")
    print("[launcher] Tip: ghostworld-editor to create your own maps!")
    return str(mp)


async def _start_client(name: str, map_path: str, texture: str = ""):
    from metaverse.local_client import LocalClient
    import metaverse.server as srv_mod
    print(f"[launcher] Client '{name}' starting...")
    client = LocalClient(srv_mod._current_ws, srv_mod._current_ctx, name, map_path, texture)
    await client.run()


async def launch_all(map_path: str):
    mp = _resolve_map(map_path)
    # Initialize world state (same-process, no network)
    from metaverse.server import init_server
    ws, ctx, state_path = init_server(mp)
    from metaverse.channel_server import close_channel, open_channel
    channel = open_channel(ctx.bus, ctx.cmd_queue)
    print(f"[launcher] Channel on 127.0.0.1:{channel.port} — ghostworld-send / ghostworld-wait")
    agent_task = None
    try:
        # Read GUI launcher config if present
        _cfg_path = str(launch_config_file())
        _cfg = {}
        if os.path.isfile(_cfg_path):
            with open(_cfg_path, encoding="utf-8") as f:
                _cfg = json.load(f)
            ctx.bus.publish({"event": "config_read", "agent_name": _cfg.get("agent_name", "?"),
                             "agent_tex": _cfg.get("agent_texture", "")[:50]})
        else:
            ctx.bus.publish({"event": "config_missing", "path": _cfg_path})
        agent_name = _cfg.get("agent_name", "omp")
        agent_tex = _cfg.get("agent_texture", "")
        player_name = _cfg.get("player_name", "player")
        player_tex = _cfg.get("player_texture", "")
        ctx.agent_name = agent_name

        from metaverse.local_agent import local_agent_loop
        agent_task = asyncio.create_task(local_agent_loop(agent_name, ws, agent_tex, ctx=ctx))
        print(f"[launcher] Agent '{agent_name}' started in-process")
        await _start_client(player_name, mp, player_tex)
    finally:
        if agent_task is not None:
            agent_task.cancel()
        close_channel(channel)
    print("[launcher] Goodbye.")


def main():
    from metaverse._branding import claim_taskbar_identity
    from metaverse._paths import utf8_stdio

    utf8_stdio()               # the startup block prints ✓/✗, pipes are not UTF-8 by default
    claim_taskbar_identity()   # before the pygame window: taskbar grouping
    try:
        _run()
    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        print(f"[ghostworld] 缺少依赖: {missing}")
        print("[ghostworld] 请运行: pip install git+https://github.com/Offblink/GhostWorld.git")
        print("[ghostworld] 如已安装仍报错，检查 Python 版本是否在 3.10–3.13 之间。")
        _sys.exit(1)

def _print_startup_paths() -> None:
    """Every start says which copy this is and where it writes (see _paths)."""
    from metaverse._paths import startup_lines
    for line in startup_lines():
        print(f"[launcher] {line}")


def _run():
    args = _sys.argv[1:]
    if "--where" in args:
        # Handled before check_update: "where did it install" must not need the network.
        from metaverse._paths import main as _where

        _where()
        return
    from metaverse._update_check import check_update
    check_update()
    map_path = default_map()
    for a in args:
        if a.endswith(".json"):
            map_path = a
            break

    if "--help" in args or "-h" in args:
        print(__doc__)
        print("Options:")
        print("  <map.json>       map file (default: the last one played, else the demo map)")
        print("  --where          print where this copy is installed and what it writes")
        print("  --help, -h       show this help")
        return

    mp = _resolve_map(map_path)
    if not os.path.isfile(mp):
        mp = _write_builtin_maps()
    print("[launcher] ⚠ 请切换为英文输入法，点击游戏窗口后再操作！")
    _print_startup_paths()

    _acquire_lock()
    asyncio.run(launch_all(mp))

if __name__ == "__main__":
    main()
