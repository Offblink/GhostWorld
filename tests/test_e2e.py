"""End-to-end integration test: same-process server + human client + agent."""
import json
import os
import tempfile

import pytest

from metaverse.world import WorldState
from metaverse.server import handle_message, _build_snapshot, _tick_world, ServerContext


_MAP_DATA = {
    "version": 2,
    "grid": [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]],
    "player_spawn": {"x": 0.5, "y": 0.5, "angle": 0},
    "entities": [
        {"x": 3.0, "y": 3.0, "kind": "item", "pickup": True, "pickup_label": "Scroll", "name": "scroll_01", "texture": ""},
    ],
    "colors": {"sky_top": [135,206,235], "sky_bottom": [240,248,255], "floor": [34,139,34]},
}


def _make_ws():
    """Create a WorldState from embedded map data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(_MAP_DATA, f)
        map_path = f.name
    ws = WorldState(map_path)
    return ws, map_path


class TestE2E:

    def test_two_clients_see_each_other(self):
        ws, map_path = _make_ws()
        ctx = ServerContext()
        try:
            # Connect human
            r = handle_message(ws, "human", {"type": "connect", "token": "token_human", "owner": "human"})
            assert r["type"] == "connected"

            # Connect agent
            r = handle_message(ws, "agent_01", {"type": "connect", "token": "token_agent_01", "owner": "agent"})
            assert r["type"] == "connected"

            # Agent looks
            r = handle_message(ws, "agent_01", {"type": "look"})
            assert r["type"] == "perception"

            # Agent moves
            r = handle_message(ws, "agent_01", {"type": "move", "x": 2.0, "y": 2.0, "facing": 0})
            assert r["type"] == "moved"

            # Human says
            r = handle_message(ws, "human", {"type": "say", "message": "Hello!", "channel": "global"})
            assert r["type"] == "said"

            # Agent moves to item location
            r = handle_message(ws, "agent_01", {"type": "move", "x": 3.0, "y": 3.0, "facing": 0})
            assert r["type"] == "moved"

            # Agent picks up
            r = handle_message(ws, "agent_01", {"type": "pickup", "x": 3.0, "y": 3.0})
            assert r["type"] == "picked_up"

            # Verify both avatars in snapshot
            snap = _build_snapshot(ws)
            assert "human" in snap.get("avatars", {})
            assert "agent_01" in snap.get("avatars", {})
        finally:
            os.unlink(map_path)
