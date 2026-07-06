"""Headless metaverse — server + agent only, no GUI. For testing agent commands."""
import sys, os, asyncio
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

async def main():
    map_path = sys.argv[1] if len(sys.argv) > 1 else "examples/new_test_map.json"
    mp = map_path
    if not os.path.isabs(mp):
        mp = os.path.join(ROOT, mp)
    if not os.path.isfile(mp):
        mp = os.path.join(ROOT, "examples", os.path.basename(map_path))
    print(f"[headless] Loading map: {mp}")

    from metaverse.server import init_server
    ws, ctx, state_path = init_server(mp)
    print(f"[headless] Server ready. {len(ws.items)} items loaded.")

    from metaverse.local_agent import local_agent_loop
    agent_task = asyncio.create_task(local_agent_loop("omp", ws, ""))
    print("[headless] Agent 'omp' started.")
    print("[headless] Write commands to metaverse/agent_commands.jsonl")
    print("[headless] Read results from metaverse/agent_output.jsonl")
    print("[headless] Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    agent_task.cancel()
    print("[headless] Goodbye.")

if __name__ == "__main__":
    asyncio.run(main())
