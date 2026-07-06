"""Regression test: Item objects must not be shared across map entries."""
import sys, os, json, tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from metaverse.world import WorldState, Item


_MAP_A = {
    "version": 3,
    "grid": [[0, 0, 0, 0, 0]] * 5,
    "player_spawn": {"x": 1.5, "y": 1.5, "angle": 0},
    "entities": [
        {"x": 2.5, "y": 2.5, "kind": "portal", "id": "portal_a",
         "portal_target": {"portal_id": "portal_b", "map": "map_b.json"}},
    ],
    "colors": {"sky_top": [135, 206, 235], "sky_bottom": [240, 248, 255], "floor": [34, 139, 34]},
}

_MAP_B = {
    "version": 3,
    "grid": [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]] * 10,
    "player_spawn": {"x": 1.5, "y": 1.5, "angle": 0},
    "entities": [
        {"x": 4.5, "y": 4.5, "kind": "portal", "id": "portal_b",
         "portal_target": {"portal_id": "portal_a", "map": "map_a.json"}},
    ],
    "colors": {"sky_top": [135, 206, 235], "sky_bottom": [240, 248, 255], "floor": [34, 139, 34]},
}


class TestItemIsolation:
    """After map switch, modifying ws.items must not affect ws.maps entries."""

    @pytest.fixture
    def world(self, tmp_path):
        # Write map files
        map_a = tmp_path / "map_a.json"
        map_b = tmp_path / "map_b.json"
        json.dump(_MAP_A, open(map_a, "w"))
        json.dump(_MAP_B, open(map_b, "w"))
        ws = WorldState(str(map_a))
        return ws

    def test_portal_coordinates_independent(self, world):
        """portal_a on map_a has x=2.5, portal_b on map_b has x=4.5. Must stay independent."""
        item_a = world.maps["map_a.json"]["items"]["portal_a"]
        item_b = world.maps["map_b.json"]["items"]["portal_b"]
        assert item_a.x == pytest.approx(2.5)
        assert item_b.x == pytest.approx(4.5)
        # Modify ws.items (simulating in-game state)
        if "portal_a" in world.items:
            world.items["portal_a"].x = 99.0
        # Map storage must NOT be affected
        assert world.maps["map_a.json"]["items"]["portal_a"].x == pytest.approx(2.5)

    def test_portal_target_preserved_per_map(self, world):
        """Each map's portal_target must remain independent."""
        ta = world.maps["map_a.json"]["items"]["portal_a"].portal_target
        tb = world.maps["map_b.json"]["items"]["portal_b"].portal_target
        assert ta is not None
        assert tb is not None
        assert ta["portal_id"] == "portal_b"
        assert tb["portal_id"] == "portal_a"
