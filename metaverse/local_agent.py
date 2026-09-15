"""Local agent — same-process, no WebSocket, no polling of the chat log.

The agent is a *subscriber*: everything it produces goes onto the channel's
``EventBus``, and the ``FileSink`` below turns that stream back into the legacy
``agent_output.jsonl`` (Mnemenet and the old greps keep working, with ``seq``
added so a reader can tell truth from replay).

Player speech is no longer detected here — the server publishes the ``heard``
wake when the message arrives, so a message that scrolls out of ``chat_log``
while the agent is busy is still delivered.
"""
from __future__ import annotations

import asyncio
import json
import os

from .channel import FileSink, PendingCommand
from ._paths import runtime_paths

_PATHS = runtime_paths()
CMD_FILE = str(_PATHS["commands"])
LOG_FILE = str(_PATHS["log"])
POLL_INTERVAL = 0.3


def read_commands(on_error=None) -> list[dict]:
    """Drain the legacy command file.

    The file is moved aside before it is read: the old read-then-delete could
    lose a command that a writer had only half flushed, or lose the whole file
    when parsing blew up.  Unparsable lines are reported instead of vanishing.
    """
    if not os.path.exists(CMD_FILE):
        return []
    staging = CMD_FILE + ".processing"
    try:
        os.replace(CMD_FILE, staging)
    except OSError:
        return []
    cmds: list[dict] = []
    bad: list[str] = []
    try:
        with open(staging, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    cmds.append(json.loads(line))
                except ValueError:
                    bad.append(line)
    except OSError:
        pass
    finally:
        try:
            os.remove(staging)
        except OSError:
            pass
    if bad and on_error:
        on_error({"event": "read_err", "error": f"{len(bad)} unparsable command line(s)", "lines": bad[:5]})
    return cmds


def _clear_legacy_files() -> None:
    for path in (CMD_FILE, CMD_FILE + ".processing"):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


async def local_agent_loop(name, ws, texture="", ctx=None):
    """Run the agent locally, sharing WorldState.

    Commands are posted to ``ctx.cmd_queue`` and executed by the frame loop —
    this task never calls ``process_agent_command`` itself.
    """
    from metaverse.server import _build_snapshot, handle_message
    if ctx is None:
        import metaverse.server as srv
        ctx = srv._current_ctx
    bus = ctx.bus
    sink = FileSink(bus, LOG_FILE, echo=True)
    sink.start()
    try:
        token = f"token_{name}"
        resp = handle_message(ws, name, {"type": "connect", "token": token, "owner": "agent", "texture": texture})
        _clear_legacy_files()
        bus.publish({"event": "connected", "pos": [resp.get("x", 0), resp.get("y", 0)]})
        print(f"[{name}] connected locally")

        last_seen: dict = {}
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL)

                # other avatars — only published when their position changes
                snap = _build_snapshot(ws)
                others = {k: [round(v["x"], 1), round(v["y"], 1)]
                          for k, v in snap.get("avatars", {}).items() if k != name}
                if others and others != last_seen:
                    bus.publish({"event": "see", "avatars": others})
                    last_seen = dict(others)

                av = ws.avatars.get(name)
                if av and av.goto_done:
                    av.goto_done = False
                    bus.publish({"event": "goto_done", "x": av.x, "y": av.y,
                                 "map": av.current_map or os.path.basename(ws.map_path)})

                # legacy file channel: still accepted, but executed by the frame loop
                for cmd in read_commands(on_error=lambda evt: bus.publish(evt)):
                    ctx.cmd_queue.put(PendingCommand(cmd))
            except asyncio.CancelledError:
                raise
            except Exception as e:  # one bad tick must not end the agent
                bus.publish({"event": "loop_crash", "error": str(e)})
    finally:
        sink.stop()
