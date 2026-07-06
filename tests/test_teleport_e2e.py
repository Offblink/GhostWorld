"""
End-to-end teleport test: detects state pollution across maps.
Runs without pygame — pure WorldState + server logic.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from metaverse.world import WorldState
from metaverse.server import handle_message, _build_snapshot, _tick_world, ServerContext

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")
MAP_A = os.path.join(EXAMPLES, "_test_A.json")
MAP_B = os.path.join(EXAMPLES, "_test_B.json")
def dump(ws):
    """Return a dict representing full world state for assertions."""
    return {
        "map_path": os.path.basename(ws.map_path) if ws.map_path else "",
        "grid": ws.grid.copy(),
        "items": {k: (v.x, v.y, v.kind) for k, v in ws.items.items()},
        "avatars": {k: (round(v.x,1), round(v.y,1), v.current_map) for k, v in ws.avatars.items()},
        "maps": {k: {"items": {ik: (iv.x, iv.y, iv.kind) for ik, iv in v["items"].items()},
                     "grid_shape": v["grid"].shape}
                 for k, v in ws.maps.items()},
    }

def tick(ws, ctx, n=1):
    """Run _tick_world n times."""
    for _ in range(n):
        _tick_world(ctx, ws)

def assert_grid_unchanged(ws, map_name, original_grid):
    """Verify a map's grid in ws.maps hasn't been polluted."""
    current = ws.maps[map_name]["grid"]
    assert current.shape == original_grid.shape, f"{map_name} grid shape changed: {current.shape} vs {original_grid.shape}"
    assert (current == original_grid).all(), f"{map_name} grid was modified!\nExpected:\n{original_grid}\nGot:\n{current}"

def assert_items_unchanged(ws, map_name, expected_count):
    """Verify map's items count."""
    actual = len(ws.maps[map_name].get("items", {}))
    assert actual == expected_count, f"{map_name} items changed: expected {expected_count}, got {actual}"

def main():
    ws = WorldState(MAP_A)
    ctx = ServerContext()
    
    # Snapshot original data for pollution checks
    orig_grid_A = ws.maps["_test_A.json"]["grid"].copy()
    orig_grid_B = ws.maps["_test_B.json"]["grid"].copy()
    orig_items_A = len(ws.maps["_test_A.json"]["items"])
    orig_items_B = len(ws.maps["_test_B.json"]["items"])
    
    print("=== Initial State ===")
    # Connect
    resp = handle_message(ws, "player", {"type": "connect", "owner": "human"})
    assert resp["type"] == "connected"
    resp = handle_message(ws, "omp", {"type": "connect", "owner": "agent"})
    assert resp["type"] == "connected"
    
    s = dump(ws)
    print(f"map_path: {s['map_path']}")
    print(f"avatars: {s['avatars']}")
    print(f"items: {s['items']}")
    
    # Verify both on Map A
    assert ws.avatars["player"].current_map == "_test_A.json"
    assert ws.avatars["omp"].current_map == "_test_A.json"
    print("✓ Both avatars on Map A")
    
    # --- Agent teleports to Map B ---
    print("\n=== Agent walks to portal on Map A ===")
    # Move agent to portal position
    ws.avatars["omp"].x = 4.5
    ws.avatars["omp"].y = 1.5
    ws.avatars["omp"].facing = 0.0
    # Tick: portal should trigger
    tick(ws, ctx, n=1)
    
    s = dump(ws)
    print(f"After tick: omp cur_map={ws.avatars['omp'].current_map!r} pos=({ws.avatars['omp'].x},{ws.avatars['omp'].y})")
    
    # Agent should now be on Map B
    assert ws.avatars["omp"].current_map == "_test_B.json", f"Expected _test_B.json, got {ws.avatars['omp'].current_map!r}"
    print("✓ Agent teleported to Map B")
    
    # Check snapshot: agent should be remote from player's view
    snap = _build_snapshot(ws)
    assert "player" in snap["avatars"], "player should be in avatars"
    assert "omp" not in snap["avatars"], "omp should NOT be in avatars (different map)"
    assert "omp" in snap["remote_avatars"], "omp should be in remote_avatars"
    print("✓ Snapshot: agent in remote_avatars, player in avatars")
    
    # Check state pollution: Map A and Map B grids should be unchanged
    assert_grid_unchanged(ws, "_test_A.json", orig_grid_A)
    assert_grid_unchanged(ws, "_test_B.json", orig_grid_B)
    assert_items_unchanged(ws, "_test_A.json", orig_items_A)
    assert_items_unchanged(ws, "_test_B.json", orig_items_B)
    print("✓ No state pollution: both map grids/items unchanged")
    
    # --- Player follows to Map B ---
    print("\n=== Player follows to Map B ===")
    # Player moves to portal
    ws.avatars["player"].x = 4.5
    ws.avatars["player"].y = 1.5
    tick(ws, ctx, n=1)
    
    assert ws.avatars["player"].current_map == "_test_B.json", f"Player should be on Map B, got {ws.avatars['player'].current_map!r}"
    print("✓ Player portal triggered, current_map set to _test_B.json")
    
    # Simulate client map switch
    old_name = os.path.basename(ws.map_path)
    target = ws.avatars["player"].current_map
    if old_name in ws.maps and target in ws.maps:
        ws.maps[old_name]["items"] = dict(ws.items)
        ws.maps[old_name]["grid"] = ws.grid.copy()
        ws.maps[old_name]["colors"] = dict(ws.colors)
        m = ws.maps[target]
        ws.grid = m["grid"]
        ws.items = dict(m["items"])
        ws.colors = m["colors"]
        ws.map_path = target
        ws.avatars["player"].current_map = target
    
    s = dump(ws)
    print(f"After switch: ws.map_path={s['map_path']}")
    print(f"avatars: {s['avatars']}")
    
    # Now both should be on Map B
    snap = _build_snapshot(ws)
    assert "player" in snap["avatars"]
    assert "omp" in snap["avatars"], f"omp should be in avatars now, got avatars={list(snap['avatars'].keys())} remote={list(snap['remote_avatars'].keys())}"
    assert len(snap["remote_avatars"]) == 0
    print("✓ Snapshot: both on Map B in avatars")
    
    # Check state pollution again
    assert_grid_unchanged(ws, "_test_A.json", orig_grid_A)
    assert_grid_unchanged(ws, "_test_B.json", orig_grid_B)
    print("✓ Still no state pollution after player switch")
    
    # --- Agent returns to Map A ---
    print("\n=== Agent returns to Map A ===")
    ws.avatars["omp"].x = 4.5
    ws.avatars["omp"].y = 4.5
    tick(ws, ctx, n=1)
    
    assert ws.avatars["omp"].current_map == "_test_A.json", f"Agent should be on Map A, got {ws.avatars['omp'].current_map!r}"
    print("✓ Agent returned to Map A")
    
    snap = _build_snapshot(ws)
    assert "player" in snap["avatars"]
    assert "omp" not in snap["avatars"], "omp should NOT be in avatars (back on Map A)"
    assert "omp" in snap["remote_avatars"]
    print("✓ Snapshot: agent back in remote_avatars")
    
    # Final pollution check
    assert_grid_unchanged(ws, "_test_A.json", orig_grid_A)
    assert_grid_unchanged(ws, "_test_B.json", orig_grid_B)
    print("✓ Final: no state pollution")
    
    print("\n=== ALL CHECKS PASSED ===")
def test_concurrent_ticks():
    """Simulate interleaved server + client ticks (the real run condition)."""
    ws = WorldState(MAP_A)
    ctx = ServerContext()
    handle_message(ws, "player", {"type": "connect", "owner": "human"})
    handle_message(ws, "omp", {"type": "connect", "owner": "agent"})
    
    orig_grid_A = ws.maps["_test_A.json"]["grid"].copy()
    orig_grid_B = ws.maps["_test_B.json"]["grid"].copy()
    
    print("\n=== Concurrent Tick Simulation ===")
    
    for iteration in range(20):
        # Server tick (runs at 20Hz async)
        _tick_world(ctx, ws)
        
        # Client tick (runs every 6 frames at 120fps, but interleaved with server)
        _tick_world(ctx, ws)
        
        # Simulate player moving toward portal (slowly)
        if iteration >= 5 and iteration < 10:
            ws.avatars["player"].x = 4.5
            ws.avatars["player"].y = 1.5
        
        # If player was teleported, do map switch
        av = ws.avatars.get("player")
        if av and av.current_map and av.current_map != os.path.basename(ws.map_path) and av.current_map in ws.maps:
            old_name = os.path.basename(ws.map_path)
            target = av.current_map
            if old_name in ws.maps:
                ws.maps[old_name]["items"] = dict(ws.items)
                ws.maps[old_name]["grid"] = ws.grid.copy()
                ws.maps[old_name]["colors"] = dict(ws.colors)
            m = ws.maps[target]
            ws.grid = m["grid"]
            ws.items = dict(m["items"])
            ws.colors = m["colors"]
            ws.map_path = target
            av.current_map = target
            print(f"  iter {iteration}: player switched to {target}")
    
    # Check pollution
    result_A = ws.maps["_test_A.json"]["grid"]
    result_B = ws.maps["_test_B.json"]["grid"]
    
    # Grids should be unchanged
    assert (result_A == orig_grid_A).all(), f"Map A grid polluted!\nOrig:\n{orig_grid_A}\nNow:\n{result_A}"
    assert (result_B == orig_grid_B).all(), f"Map B grid polluted!\nOrig:\n{orig_grid_B}\nNow:\n{result_B}"
    
    # Items should still be in correct maps (no cross-map leakage)
    items_A = ws.maps["_test_A.json"].get("items", {})
    items_B = ws.maps["_test_B.json"].get("items", {})
    for iid, item in items_A.items():
        assert item.kind in ("portal", "item"), f"Unexpected item in Map A: {iid} ({item.kind})"
    for iid, item in items_B.items():
        assert item.kind in ("portal", "item"), f"Unexpected item in Map B: {iid} ({item.kind})"
    
    print(f"  Map A items: {len(items_A)}, Map B items: {len(items_B)}")
    print("✓ Concurrent tick test passed — no state pollution")


if __name__ == "__main__":
    main()
    test_concurrent_ticks()
    print("\n=== ALL TESTS PASSED ===")
