"""Headless metaverse — server + agent only, no GUI. For testing agent commands.

Runs the frame loop itself (no client), so the channel works here too:
`ghostworld-send '{"cmd":"pos"}'` gets an ack without a window being open.
"""
import sys, os, asyncio
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

TICK_INTERVAL = 0.05   # 20Hz — same cadence the GUI client ticks at


async def main():
    map_path = sys.argv[1] if len(sys.argv) > 1 else "examples/new_test_map.json"
    mp = map_path
    if not os.path.isabs(mp):
        mp = os.path.join(ROOT, mp)
    if not os.path.isfile(mp):
        mp = os.path.join(ROOT, "examples", os.path.basename(map_path))
    print(f"[headless] Loading map: {mp}")

    from metaverse.server import _tick_loop_sync, init_server
    ws, ctx, state_path = init_server(mp)
    print(f"[headless] Server ready. {len(ws.items)} items loaded.")

    from metaverse.channel_server import close_channel, open_channel
    channel = open_channel(ctx.bus, ctx.cmd_queue)
    print(f"[headless] Channel on 127.0.0.1:{channel.port}")
    print("[headless]   send: ghostworld-send '{\"cmd\":\"pos\"}'")
    print("[headless]   wait: ghostworld-wait --timeout 25")

    from metaverse.local_agent import local_agent_loop
    agent_task = asyncio.create_task(local_agent_loop("omp", ws, "", ctx=ctx))
    print("[headless] Agent 'omp' started.")
    print("[headless] Press Ctrl+C to stop.")

    try:
        while True:
            _tick_loop_sync(ctx, ws)
            await asyncio.sleep(TICK_INTERVAL)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        agent_task.cancel()
        close_channel(channel)
    print("[headless] Goodbye.")


if __name__ == "__main__":
    asyncio.run(main())
