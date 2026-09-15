"""Headless game with a player — the harness for wiring an external agent to a character.

Runs the server + the channel and connects two avatars: the agent's (commands from
the channel act as it) and a human-owned `player` that can speak. That is what a
GUI client does for real, minus the window — so a channel client (ghostworld-wait /
ghostworld-send, or another program speaking the protocol) can be exercised end to
end without opening anything.

    python headless_player.py examples/demo_metaverse.json
    python headless_player.py examples/demo_metaverse.json --say 你好 --after 3

`--after` waits before speaking so a watcher has time to attach — though it does not
have to: player speech is buffered with a cursor, so a watcher that connects later
still receives it.
"""
import asyncio
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TICK_INTERVAL = 0.05  # 20Hz, same cadence the GUI client ticks at


def _args() -> tuple[str, str, float]:
    argv = sys.argv[1:]
    map_path, say, after = "examples/demo_metaverse.json", "", 3.0
    i = 0
    while i < len(argv):
        if argv[i] == "--say" and i + 1 < len(argv):
            i += 1
            say = argv[i]
        elif argv[i] == "--after" and i + 1 < len(argv):
            i += 1
            after = float(argv[i])
        elif not argv[i].startswith("-"):
            map_path = argv[i]
        i += 1
    return map_path, say, after


async def main():
    map_path, say, after = _args()
    mp = map_path if os.path.isabs(map_path) else os.path.join(ROOT, map_path)
    if not os.path.isfile(mp):
        mp = os.path.join(ROOT, "examples", os.path.basename(map_path))
    print(f"[player] Loading map: {mp}")

    from metaverse.channel_server import close_channel, open_channel
    from metaverse.server import _tick_loop_sync, handle_message, init_server

    ws, ctx, _state = init_server(mp)
    channel = open_channel(ctx.bus, ctx.cmd_queue)
    handle_message(ws, ctx.agent_name, {"type": "connect", "owner": "agent", "texture": ""})
    handle_message(ws, "player", {"type": "connect", "owner": "human", "texture": ""})
    print(f"[player] Channel on 127.0.0.1:{channel.port} — agent '{ctx.agent_name}' + player connected")
    if say:
        print(f"[player] will say {say!r} after {after:g}s")
    print("[player] Press Ctrl+C to stop.")

    async def tick():
        while True:
            _tick_loop_sync(ctx, ws)  # so a command from the channel gets its ack
            await asyncio.sleep(TICK_INTERVAL)

    ticker = asyncio.create_task(tick())
    try:
        if say:
            await asyncio.sleep(after)
            handle_message(ws, "player", {"type": "say", "message": say, "channel": "global"})
            print(f"[player] said: {say}")
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        ticker.cancel()
        close_channel(channel)
    print("[player] Goodbye.")


if __name__ == "__main__":
    asyncio.run(main())
