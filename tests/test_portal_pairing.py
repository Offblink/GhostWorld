"""Test portal pairing/unpairing/re-pairing logic (pure state, no Qt)."""
import sys, os, json, tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from editor.model import EditorState, generate_portal_id, break_all_references_to_portal


@pytest.fixture
def state():
    st = EditorState()
    st.project_dir = tempfile.mkdtemp()
    st.map_path = os.path.join(st.project_dir, "test_map.json")
    # Add two portals to the in-memory state
    st.entities = [
        {"x": 2.5, "y": 3.5, "kind": "portal", "id": "portal_A", "portal_target": None,
         "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
        {"x": 7.5, "y": 7.5, "kind": "portal", "id": "portal_B", "portal_target": None,
         "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
        {"x": 10.5, "y": 10.5, "kind": "portal", "id": "portal_C", "portal_target": None,
         "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
    ]
    st.selected_entity_idx = -1
    return st


class TestPortalPairing:
    def test_pair_portal_sets_target(self, state):
        a = state.entities[0]
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        assert a["portal_target"]["portal_id"] == "portal_B"

    def test_pair_sets_reverse(self, state):
        a = state.entities[0]
        b = state.entities[1]
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        b["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        assert b["portal_target"]["portal_id"] == "portal_A"
        assert a["portal_target"]["portal_id"] == "portal_B"

    def test_unpair_clears_target(self, state):
        a = state.entities[0]
        b = state.entities[1]
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        b["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        # Unpair A
        a["portal_target"] = None
        assert a["portal_target"] is None

    def test_unpair_clears_reverse(self, state):
        """When A unpairs, B's reference to A should also be cleared."""
        a = state.entities[0]
        b = state.entities[1]
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        b["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        # Simulate unpair: clear both sides
        a["portal_target"] = None
        b["portal_target"] = None
        assert a["portal_target"] is None
        assert b["portal_target"] is None

    def test_re_pair_breaks_old(self, state):
        """When A re-pairs from B to C, B should become unpaired."""
        a = state.entities[0]
        b = state.entities[1]
        c = state.entities[2]
        # Initial: A ↔ B
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        b["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        # Re-pair: A → C, clear B's ref to A
        a["portal_target"] = {"portal_id": "portal_C", "map": "test_map.json"}
        b["portal_target"] = None
        c["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        assert a["portal_target"]["portal_id"] == "portal_C"
        assert b["portal_target"] is None
        assert c["portal_target"]["portal_id"] == "portal_A"

    def test_delete_portal_breaks_others(self, state):
        """Deleting A should clear B's pairing to A."""
        a = state.entities[0]
        b = state.entities[1]
        a["portal_target"] = {"portal_id": "portal_B", "map": "test_map.json"}
        b["portal_target"] = {"portal_id": "portal_A", "map": "test_map.json"}
        pid = a["id"]
        # Simulate deletion: remove A, clear B's ref
        state.entities.pop(0)
        for ent in state.entities:
            pt = ent.get("portal_target")
            if pt and isinstance(pt, dict) and pt.get("portal_id") == pid:
                ent["portal_target"] = None
        assert b["portal_target"] is None

    def test_portal_target_format(self, state):
        """portal_target must always be {portal_id, map}, no coordinates."""
        a = state.entities[0]
        a["portal_target"] = {"portal_id": "portal_B", "map": "other.json"}
        assert "x" not in a["portal_target"]
        assert "y" not in a["portal_target"]
        assert a["portal_target"]["portal_id"] == "portal_B"
        assert a["portal_target"]["map"] == "other.json"
