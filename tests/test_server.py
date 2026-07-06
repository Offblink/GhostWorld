"""Tests for metaverse/server.py — message protocol handling."""
import json

import pytest

from metaverse.world import WorldState, Item


_MAP_DATA = {
    "version": 2,
    "grid": [[0, 0], [0, 0]],
    "player_spawn": {"x": 0.5, "y": 0.5, "angle": 0},
    "entities": [
        {"x": 1.0, "y": 1.0, "kind": "item", "pickup": True, "pickup_label": "book",
         "name": "book_01", "texture": ""},
    ],
    "colors": {},
}


class TestServerProtocol:
    """Test server message handling without WebSocket transport."""

    @pytest.fixture
    def ws(self) -> WorldState:
        return WorldState.from_dict(_MAP_DATA)

    def test_connect_creates_avatar(self, ws):
        from metaverse.server import handle_message
        result = handle_message(ws, "alice", {"type": "connect", "owner": "human"})
        assert result["type"] == "connected"
        assert "alice" in ws.avatars
        assert ws.avatars["alice"].owner == "human"

    def test_move_updates_position(self, ws):
        from metaverse.server import handle_message
        handle_message(ws, "alice", {"type": "connect"})
        result = handle_message(ws, "alice", {"type": "move", "x": 1.2, "y": 0.8, "facing": 1.5})
        assert result["type"] == "moved"
        assert ws.avatars["alice"].x == 1.2
        assert ws.avatars["alice"].y == 0.8
        assert ws.avatars["alice"].facing == 1.5

    def test_move_blocked_by_wall(self, ws):
        from metaverse.server import handle_message
        # make a wall
        ws.grid[1, 1] = 1
        handle_message(ws, "alice", {"type": "connect"})
        result = handle_message(ws, "alice", {"type": "move", "x": 1.0, "y": 1.0, "facing": 0})
        assert result["type"] == "blocked"

    def test_say_broadcasts(self, ws):
        from metaverse.server import handle_message
        handle_message(ws, "alice", {"type": "connect"})
        result = handle_message(ws, "alice", {"type": "say", "message": "hello", "channel": "local"})
        assert result["type"] == "said"
        assert result["from"] == "alice"
        assert result["message"] == "hello"

    def test_pickup_collects_nearby_item(self, ws):
        from metaverse.server import handle_message
        handle_message(ws, "alice", {"type": "connect"})
        # alice starts at spawn (0.5, 0.5), move near book_01 at (1.0, 1.0)
        handle_message(ws, "alice", {"type": "move", "x": 0.9, "y": 0.9, "facing": 0})
        result = handle_message(ws, "alice", {"type": "pickup", "x": 0.9, "y": 0.9})
        assert result["type"] == "picked_up"
        assert result["item_id"] == "book_01"
        assert "book_01" not in ws.items

    def test_unknown_message_type(self, ws):
        from metaverse.server import handle_message
        handle_message(ws, "alice", {"type": "connect"})
        result = handle_message(ws, "alice", {"type": "dance"})
        assert result["type"] == "error"

    def test_disconnect_removes_avatar(self, ws):
        from metaverse.server import handle_message
        handle_message(ws, "alice", {"type": "connect"})
        result = handle_message(ws, "alice", {"type": "disconnect"})
        assert result["type"] == "disconnected"
        assert "alice" not in ws.avatars
