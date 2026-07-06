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
import math
import os
import random




LOCK_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".instance.lock")

def _acquire_lock() -> bool:
    """Singleton lock: kill old instance if running, then claim lock file."""
    import signal
    if _os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if _sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, old_pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    import subprocess
                    subprocess.run(f"taskkill /F /PID {old_pid}", shell=True, capture_output=True)
            else:
                try: _os.kill(old_pid, signal.SIGTERM)
                except: pass
        except: pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(_os.getpid()))
    return True
def _resolve_map(path: str) -> str:
    if os.path.isabs(path):
        return path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, path)




async def _start_client(name: str, map_path: str, texture: str = ""):
    from metaverse.local_client import LocalClient
    import metaverse.server as srv_mod
    print(f"[launcher] Client '{name}' starting...")
    client = LocalClient(srv_mod._current_ws, srv_mod._current_ctx, name, map_path, texture)
    await client.run()



DEMO_MAP = "examples/demo_metaverse.json"
_last_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", ".last_map")
if os.path.isfile(_last_map_path):
    try:
        with open(_last_map_path) as f:
            p = f.read().strip()
            if p and os.path.isfile(p):
                DEMO_MAP = p
    except: pass

async def launch_all(map_path: str):
    mp = _resolve_map(map_path)
    # Initialize world state (same-process, no network)
    from metaverse.server import init_server
    ws, ctx, state_path = init_server(mp)
    # Read GUI launcher config if present
    _cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metaverse", "launch_config.json")
    _cfg = {}
    if os.path.isfile(_cfg_path):
        with open(_cfg_path, "r", encoding="utf-8") as f:
            _cfg = json.load(f)
        with open(os.path.join(os.path.dirname(__file__), "agent_output.jsonl"), "a", encoding="utf-8") as _lf:
            _lf.write(json.dumps({"event":"config_read","agent_name":_cfg.get("agent_name","?"),"agent_tex":_cfg.get("agent_texture","")[:50]}) + "\n")
    else:
        with open(os.path.join(os.path.dirname(__file__), "agent_output.jsonl"), "a", encoding="utf-8") as _lf:
            _lf.write(json.dumps({"event":"config_missing","path":_cfg_path}) + "\n")
    agent_name = _cfg.get("agent_name", "omp")
    agent_tex = _cfg.get("agent_texture", "")
    player_name = _cfg.get("player_name", "player")
    player_tex = _cfg.get("player_texture", "")

    from metaverse.local_agent import local_agent_loop
    agent_task = asyncio.create_task(local_agent_loop(agent_name, ws, agent_tex))
    print(f"[launcher] Agent '{agent_name}' started in-process")
    await _start_client(player_name, mp, player_tex)
    agent_task.cancel()
    print("[launcher] Goodbye.")


def main():
    args = _sys.argv[1:]
    map_path = DEMO_MAP
    for a in args:
        if a.endswith(".json"):
            map_path = a
            break

    if "--help" in args or "-h" in args:
        print(__doc__)
        print("Options:")
        print("  <map.json>       map file (default: examples/demo_metaverse.json)")
        print("  --help, -h       show this help")
        return

    mp = _resolve_map(map_path)
    if not os.path.isfile(mp):
        import json, tempfile
        from ghostengine._default_map import DEFAULT_MAP
        from ghostengine._default_map2 import DEFAULT_MAP2
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(DEFAULT_MAP, tmp, indent=2)
        tmp.close()
        mp = tmp.name
        tmp_dir = os.path.dirname(mp)
        map2_path = os.path.join(tmp_dir, "_default_map2.json")
        if not os.path.isfile(map2_path):
            with open(map2_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_MAP2, f, indent=2, ensure_ascii=False)
        print(f"[launcher] Using default demo maps")
        print("[launcher] Tip: ghostworld-editor to create your own maps!")


if __name__ == "__main__":
    main()
