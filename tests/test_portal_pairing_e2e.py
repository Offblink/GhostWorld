"""Integration test: portal pairing end-to-end via headless agent."""
import sys, os, asyncio, json

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)


def _la():
    """The legacy file channel lives in module globals — read them, don't copy them.

    They used to point at the repo's own `metaverse/agent_*.jsonl`, which is
    shared with any *running* game: its local agent polls the same command file
    every 0.3s and ate this test's goto (2026-09-15, the test failed only while
    a game was up). The fixture below redirects both to a temp dir.
    """
    import metaverse.local_agent as la
    return la


def write_cmd(cmd: dict):
    with open(_la().CMD_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps(cmd) + "\n")

def read_log():
    path = _la().LOG_FILE
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

async def _async_test_portal_pairing():
    map_path = os.path.join(ROOT, "tests", "fixtures", "_test_portal_A.json")
    print(f"[TEST] Loading map: {map_path}")

    from metaverse.server import init_server, _tick_loop_sync, _resolve_portal_target
    ws, ctx, state_path = init_server(map_path)
    print(f"[TEST] Maps: {list(ws.maps.keys())}")
    assert "_test_portal_B.json" in ws.maps, "Map B not preloaded!"

    from metaverse.local_agent import local_agent_loop
    agent_task = asyncio.create_task(local_agent_loop("omp", ws, ""))
    await asyncio.sleep(1)

    # Step 1: Verify portal resolution works
    for iid, item in ws.items.items():
        if item.kind == "portal":
            resolved = _resolve_portal_target(item.portal_target, ws)
            print(f"[TEST] Portal {item.id}: target={item.portal_target} → resolved={resolved}")
            assert resolved is not None, f"Portal resolution failed for {item.id}!"
            assert resolved["map"] == "_test_portal_B.json", f"Wrong target map: {resolved}"
            assert resolved["x"] == 1.5 and resolved["y"] == 4.5, f"Wrong target coords: {resolved}"

    # Step 2: Goto portal position
    write_cmd({"cmd": "goto", "x": 8.5, "y": 5.5})

    # Advance ticks until portal triggers or timeout. The frame loop drains the
    # command queue of the *server's* context (that is the one commands are
    # posted to), exactly as LocalClient does with init_server's ctx.
    teleported = False
    for i in range(120):
        _tick_loop_sync(ctx, ws)
        await asyncio.sleep(0.03)
        av = ws.avatars.get("omp")
        if av and av.current_map == "_test_portal_B.json":
            teleported = True
            print(f"[TEST] ✅ Teleported to map B at tick {i}! pos=({av.x:.1f}, {av.y:.1f})")
            break

    if not teleported:
        av = ws.avatars.get("omp")
        print(f"[TEST] ❌ No teleport. Avatar: ({av.x:.1f}, {av.y:.1f}), map={av.current_map}, goto_path={len(av.goto_path) if av.goto_path else 0} points left")
        sys.exit(1)

    # Step 3: Verify arrived near target portal
    av = ws.avatars.get("omp")
    dist = ((av.x - 1.5) ** 2 + (av.y - 4.5) ** 2) ** 0.5
    assert dist < 2.0, f"Too far from target portal: dist={dist:.1f}, pos=({av.x:.1f}, {av.y:.1f})"
    print(f"[TEST] ✅ Near target portal (dist={dist:.1f})")

    agent_task.cancel()
    print("[TEST] All checks passed!")

def test_portal_pairing(tmp_path, monkeypatch):
    la = _la()
    monkeypatch.setattr(la, "CMD_FILE", str(tmp_path / "agent_commands.jsonl"))
    monkeypatch.setattr(la, "LOG_FILE", str(tmp_path / "agent_output.jsonl"))
    asyncio.run(_async_test_portal_pairing())

if __name__ == "__main__":
    test_portal_pairing()
