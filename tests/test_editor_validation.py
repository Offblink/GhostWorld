"""Test editor map validation: wall overlap warnings and out-of-bounds cleanup."""
import sys, os, json, tempfile
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ghostengine.mapfile import validate_entities_on_walls


class TestWallOverlap:
    def test_entity_on_wall_detected(self):
        grid = np.array([[1, 0], [0, 0]], dtype=int).T  # wall at (0,0)
        entities = [{"x": 0.5, "y": 0.5, "kind": "item", "id": "bad_item"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 1
        assert "overlaps wall" in errors[0]
        assert "bad_item" in errors[0]

    def test_entity_on_open_not_flagged(self):
        grid = np.array([[0, 0], [0, 0]], dtype=int).T
        entities = [{"x": 0.5, "y": 0.5, "kind": "item", "id": "good_item"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 0

    def test_spawn_on_wall_detected(self):
        grid = np.array([[0, 1], [0, 0]], dtype=int).T  # wall at (1,0)
        entities = []
        errors = validate_entities_on_walls(grid, entities, {"x": 1.5, "y": 0.5})
        assert len(errors) == 1
        assert "spawn" in errors[0]

    def test_multiple_errors_reported(self):
        grid = np.array([[1, 0], [0, 1]], dtype=int).T
        entities = [
            {"x": 0.5, "y": 0.5, "kind": "item", "id": "a"},
            {"x": 1.5, "y": 1.5, "kind": "portal", "id": "b"},
        ]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 2


class TestOutOfBounds:
    def test_entity_outside_grid_detected(self):
        grid = np.zeros((5, 5), dtype=int)
        entities = [{"x": 6.5, "y": 2.5, "kind": "item", "id": "ghost"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 1
        assert "OUTSIDE grid" in errors[0]

    def test_negative_coordinates_detected(self):
        grid = np.zeros((5, 5), dtype=int)
        entities = [{"x": -1.5, "y": 2.5, "kind": "item", "id": "ghost"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 1
        assert "OUTSIDE grid" in errors[0]

    def test_edge_coordinates_not_flagged(self):
        grid = np.zeros((5, 5), dtype=int)
        entities = [{"x": 4.5, "y": 4.5, "kind": "item", "id": "ok"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 0


class TestCrossMapScenario:
    def test_large_map_coords_on_small_grid(self):
        """Regression: coordinates from a 35x35 map should be flagged on a 15x15 grid."""
        grid = np.zeros((15, 15), dtype=int)
        entities = [{"x": 9.5, "y": 22.5, "kind": "portal", "id": "portal_0"}]
        errors = validate_entities_on_walls(grid, entities)
        assert len(errors) == 1
        assert "OUTSIDE grid (15x15)" in errors[0]
