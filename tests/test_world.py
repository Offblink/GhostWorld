"""Tests for metaverse/world.py — WorldState management."""
import json
import os
import tempfile

import numpy as np
import pytest

from metaverse.world import WorldState, Avatar, Item


_MAP_TEMPLATE = {
    "version": 2,
    "grid": [[0, 0, 0, 1],
             [0, 0, 0, 1],
             [1, 0, 0, 0],
             [0, 0, 1, 0]],
    "player_spawn": {"x": 1.5, "y": 1.5, "angle": 0},
    "entities": [
        {"x": 2.5, "y": 2.5, "kind": "item", "pickup": True, "pickup_label": "金钥匙",
         "name": "gold_key", "texture": ""},
        {"x": 3.5, "y": 0.5, "kind": "portal", "portal_target": {"x": 0.5, "y": 0.5},
         "name": "portal_01", "texture": ""},
    ],
    "colors": {"sky_top": [135, 206, 235], "sky_bottom": [240, 248, 255], "floor": [34, 139, 34]},
}


def _tmp_map(data=None):
    """Write a temp JSON and return path."""
    d = data or _MAP_TEMPLATE
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(d, f)
    f.close()
    return f.name


class TestWorldStateLoad:
    def test_load_map_sets_grid_and_template_items(self):
        path = _tmp_map()
        try:
            ws = WorldState(path)
            assert ws.grid.shape == (4, 4)
            assert ws.grid[3, 0] == 1  # wall (was grid[0][3] in JSON)
            assert ws.grid[0, 2] == 1  # wall (was grid[2][0] in JSON)
            assert len(ws.items) == 2
            assert "gold_key" in ws.items
            assert ws.items["gold_key"].pickup_label == "金钥匙"
            assert "portal_01" in ws.items
        finally:
            os.unlink(path)

    def test_entities_with_empty_names_get_unique_ids(self):
        """Regression: entities with name="" must not collide (each gets unique auto-id)."""
        data = dict(_MAP_TEMPLATE)
        data["entities"] = [
            {"x": 1.0, "y": 1.0, "kind": "item", "name": "", "pickup": True, "pickup_label": "A"},
            {"x": 2.0, "y": 2.0, "kind": "item", "name": "", "pickup": True, "pickup_label": "B"},
            {"x": 3.0, "y": 3.0, "kind": "portal", "name": "", "portal_target": {"x": 1, "y": 1}},
            {"x": 3.0, "y": 2.0, "kind": "item", "name": "named_one", "pickup": True, "pickup_label": "C"},
        ]
        path = _tmp_map(data)
        try:
            ws = WorldState(path)
            assert len(ws.items) == 4, f"Expected 4 entities, got {len(ws.items)}: {list(ws.items.keys())}"
            # named entity keeps its name
            assert "named_one" in ws.items
            assert ws.items["named_one"].pickup_label == "C"
            # unnamed entities get auto-generated unique ids
            auto_ids = [k for k in ws.items if k not in ("named_one",)]
            assert len(auto_ids) == 3
            assert len(set(auto_ids)) == 3, f"Auto IDs must be unique, got: {auto_ids}"
            # verify all pickup labels are present
            labels = {ws.items[k].pickup_label for k in ws.items}
            assert labels == {"A", "B", "C", ""}
        finally:
            os.unlink(path)


class TestWorldStateItems:
    def test_add_item_to_ground(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        item = Item(id="scroll", x=1.0, y=1.0, texture_path="scroll.png",
                    pickup=True, pickup_label="卷轴")
        ws.add_item(item)
        assert "scroll" in ws.items
        assert ws.items["scroll"].x == 1.0
        assert ws.items["scroll"].y == 1.0

    def test_remove_item(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.remove_item("gold_key")
        assert "gold_key" not in ws.items

    def test_pickup_moves_item_to_inventory(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=2.0, y=2.0, owner="human")
        # alice near gold_key (2.5, 2.5) — dist ≈ 0.5
        picked = ws.check_pickups("alice", pickup_radius=1.0)
        assert len(picked) == 1
        assert picked[0].id == "gold_key"
        assert "gold_key" not in ws.items
        assert len(ws.inventories["alice"]) == 1
        assert ws.inventories["alice"][0].id == "gold_key"

    def test_pickup_skips_if_not_pickup(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=3.0, y=0.0, owner="human")
        # portal_01 at (3.5, 0.5) — portal, not pickup
        picked = ws.check_pickups("alice", pickup_radius=1.0)
        assert len(picked) == 0

    def test_place_item_from_inventory(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", owner="human")
        item = Item(id="scroll", texture_path="scroll.png", pickup=True, pickup_label="卷轴")
        ws.inventories.setdefault("alice", []).append(item)
        ws.place_item("alice", "scroll", x=3.0, y=3.0)
        assert "scroll" in ws.items
        assert ws.items["scroll"].x == 3.0
        assert ws.items["scroll"].y == 3.0
        assert len(ws.inventories["alice"]) == 0


class TestWorldStateAvatars:
    def test_ensure_avatar_creates_and_updates(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("bob", x=1.0, y=1.0, facing=1.5, owner="agent")
        assert "bob" in ws.avatars
        assert ws.avatars["bob"].x == 1.0
        assert ws.avatars["bob"].facing == 1.5
        # update position
        ws.ensure_avatar("bob", x=3.0, y=2.0, facing=0.0, owner="agent")
        assert ws.avatars["bob"].x == 3.0

    def test_remove_avatar(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("bob", owner="agent")
        ws.remove_avatar("bob")
        assert "bob" not in ws.avatars


class TestCollision:
    def test_wall_collision_blocked(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        # (3, 0) is a wall, can't move there (was grid[0][3] in JSON)
        assert not ws.is_passable(3, 0)
        # (1, 1) is open
        assert ws.is_passable(1, 1)

    def test_move_valid_position(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=1.5, y=1.5, owner="human")
        result = ws.try_move("alice", 1.5, 2.5)  # (1.5, 2.5) is open
        assert result is not None
        assert result[0] == 1.5 and result[1] == 2.5

    def test_move_into_wall_rejected(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=0.5, y=1.5, owner="human")
        result = ws.try_move("alice", 0.5, 2.5)  # (0, 2) is wall (grid[0, 2]=1 in transposed)
        assert result is None


class TestPathfind:
    def test_basic_path(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        path = ws.pathfind(1, 1, 2, 2)
        assert len(path) >= 1
        # path ends at goal
        assert path[-1] == (2, 2) or (abs(path[-1][0] - 2) < 0.1 and abs(path[-1][1] - 2) < 0.1)

    def test_blocked_path_returns_empty(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        # (3, 0) is a wall, can't pathfind into it (was grid[0][3] in JSON)
        path = ws.pathfind(1, 1, 3, 0)
        assert path == []


class TestPortal:
    def test_portal_trigger(self):
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=3.0, y=0.5, owner="human")
        # portal_01 at (3.5, 0.5), dist ≈ 0.5
        result = ws.check_portal("alice", trigger_radius=1.0)
        assert result is not None
        assert result["x"] == 0.5
        assert result["y"] == 0.5


class TestPersist:
    """Round-trip save / load."""

    def test_save_and_load_state(self):
        import tempfile, os
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.ensure_avatar("alice", x=2.4, y=2.4, facing=1.5, owner="human")
        ws.check_pickups("alice", pickup_radius=1.0)  # pick up gold_key

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            path = f.name
        try:
            ws.save_state(path)
            assert os.path.getsize(path) > 10

            # reload into a new WorldState
            ws2 = WorldState.from_dict(_MAP_TEMPLATE)
            ws2.load_state(path)
            assert ws2.avatars["alice"].x == 2.4
            assert ws2.avatars["alice"].facing == 1.5
            inv_ids = [i.id for i in ws2.inventories.get("alice", [])]
            assert "gold_key" in inv_ids
        finally:
            os.unlink(path)


class TestCrossMapAvatarVisibility:
    """Avatars on different maps must not render for each other."""

    def test_avatars_filtered_by_current_map(self):
        """Regression: avatar on map A should NOT see avatars on map B."""
        from metaverse.server import _build_snapshot
        import os
        ws = WorldState.from_dict(_MAP_TEMPLATE)
        ws.map_path = "/fake/test_map.json"
        ws.ensure_avatar("alice", x=1.5, y=1.5, owner="human")
        ws.ensure_avatar("bob", x=3.5, y=3.5, owner="agent")
        # bob stays on main map, alice goes to remote map
        ws.avatars["alice"].current_map = "other_map.json"
        snap = _build_snapshot(ws)
        # alice should be in remote_avatars, bob in avatars
        assert "alice" in snap["remote_avatars"]
        assert "bob" in snap["avatars"]
        # simulate _apply_snapshot filtering for alice's view
        my_map = "other_map.json"
        visible = []
        for aid, av in snap["avatars"].items():
            if aid == "alice":
                continue
            av_map = av.get("current_map") or os.path.basename(ws.map_path)
            if av_map != my_map:
                continue
            visible.append(aid)
        # bob is on test_map.json, alice is on other_map.json → bob NOT visible
        assert "bob" not in visible, f"bob should be invisible to alice, but got {visible}"
        # simulate bob's view (same map)
        my_map2 = os.path.basename(ws.map_path)
        visible2 = []
        for aid, av in snap["avatars"].items():
            if aid == "bob":
                continue
            av_map = av.get("current_map") or os.path.basename(ws.map_path)
            if av_map != my_map2:
                continue
            visible2.append(aid)
        # alice is on other_map → NOT visible to bob
        assert "alice" not in visible2, f"alice should be invisible to bob, but got {visible2}"
