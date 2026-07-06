"""Tests for renderer._cast_ray — DDA ray marching.

No pygame window needed — just numpy grids.
"""

import math

import numpy as np
import pytest

from ghostengine.frame import PlayerView
from ghostengine.renderer import _cast_ray


# ── helpers ─────────────────────────────────────────────────────

def _make_grid(w: int = 10, h: int = 10) -> np.ndarray:
    return np.zeros((w, h), dtype=int)


class TestCastRay:
    """Unit tests for the DDA ray march."""

    def test_hit_vertical_wall_straight_ahead(self) -> None:
        """Player at (2.5, 2.5) looking east (angle=0). Wall at x=5."""
        grid = _make_grid(10, 10)
        grid[5, 2] = 1  # wall at (5, 2)
        player = PlayerView(x=2.5, y=2.5, angle=0, pitch=0)

        hit = _cast_ray(player, grid, 0.0, 10.0)
        assert hit is not None
        assert hit.distance > 0
        assert hit.wall_type == 1
        # Hit vertical face (X-aligned)
        assert hit.face_normal == 0
        # tex_x should be in [0, 1)
        assert 0.0 <= hit.tex_x < 1.0

    def test_no_hit_in_open_space(self) -> None:
        grid = _make_grid(10, 10)
        player = PlayerView(x=5, y=5, angle=0, pitch=0)
        hit = _cast_ray(player, grid, 0.0, 3.0)  # only 3 units of range
        # 5→… no walls within 3 units
        assert hit is None

    def test_fisheye_correction(self) -> None:
        """Fisheye correction ensures rays at different angles to the same
        wall report approximately the same perpendicular distance."""
        grid = _make_grid(50, 50)
        # A vertical wall at x=20, spanning y=0..40
        grid[20, 0:41] = 1

        # Player at (5, 20), looking east (angle=0)
        player = PlayerView(x=5.5, y=20, angle=0, pitch=0)

        # Straight ahead (0°) — wall at x=20, perpendicular distance ≈ 14.5
        straight = _cast_ray(player, grid, 0.0, 25.0)
        assert straight is not None

        # 30° to the right — same vertical wall, perpendicular distance ≈ 14.5
        angled = _cast_ray(player, grid, math.radians(30), 25.0)
        assert angled is not None

        # After correction, both should report ~14.5
        assert straight.distance == pytest.approx(14.5, abs=0.3)
        assert angled.distance == pytest.approx(14.5, abs=1.0)
    def test_face_detection_vertical(self) -> None:
        """Ray hitting a wall column → face_normal=0."""
        grid = _make_grid(20, 20)
        grid[10, :] = 1  # vertical wall at x=10
        player = PlayerView(x=5, y=5, angle=0, pitch=0)
        hit = _cast_ray(player, grid, 0.0, 10.0)
        assert hit is not None
        assert hit.face_normal == 0  # X-face

    def test_face_detection_horizontal(self) -> None:
        """Ray hitting a wall row → face_normal=1."""
        grid = _make_grid(20, 20)
        grid[:, 10] = 1  # horizontal wall at y=10
        player = PlayerView(x=5, y=5, angle=math.pi / 2, pitch=0)  # looking south
        hit = _cast_ray(player, grid, math.pi / 2, 10.0)
        assert hit is not None
        assert hit.face_normal == 1  # Y-face

    def test_tex_x_range(self) -> None:
        """tex_x always in [0, 1)."""
        grid = _make_grid(20, 20)
        grid[10, 5] = 1
        player = PlayerView(x=5, y=5, angle=0, pitch=0)

        # Sample many rays to ensure tex_x range
        for offset in [0.0, 0.1, 0.2, 0.3, 0.4, -0.1, -0.2]:
            p = PlayerView(x=5.0, y=5.0 + offset, angle=0, pitch=0)
            hit = _cast_ray(p, grid, 0.0, 10.0)
            if hit is not None:
                assert 0.0 <= hit.tex_x < 1.0, f"tex_x={hit.tex_x} out of range"

    def test_edge_of_grid(self) -> None:
        """Ray starting at edge and moving outward → no hit (out of bounds)."""
        grid = _make_grid(10, 10)
        player = PlayerView(x=0.1, y=5, angle=math.pi, pitch=0)  # looking west
        hit = _cast_ray(player, grid, math.pi, 2.0)
        assert hit is None  # immediately out of bounds

    def test_corner_hit(self) -> None:
        """Ray passing through a diagonal corner should hit one wall."""
        grid = _make_grid(20, 20)
        grid[10, 10] = 1
        grid[9, 10] = 1  # a thicker wall block
        player = PlayerView(x=5, y=5, angle=0.7, pitch=0)  # diagonal
        hit = _cast_ray(player, grid, 0.7, 13.0)
        # Should hit something
        assert hit is not None
        assert hit.wall_type == 1

    def test_corrected_distance_non_negative(self) -> None:
        """Distance after fisheye correction is always positive."""
        grid = _make_grid(20, 20)
        grid[10, :] = 1
        player = PlayerView(x=5, y=5, angle=0, pitch=0)

        for deg in range(-70, 71, 10):
            ang = math.radians(deg)
            hit = _cast_ray(player, grid, ang, 15.0)
            if hit is not None:
                assert hit.distance > 0.0
