"""Tests for entity.py — pure geometry functions.

No pygame window needed.
"""

import math

from ghostengine.entity import distance, project_entity, relative_angle, relative_info
from ghostengine.frame import PlayerView


class TestDistance:
    def test_zero(self) -> None:
        assert distance(0, 0, 0, 0) == 0.0

    def test_unit(self) -> None:
        assert distance(0, 0, 3, 4) == 5.0

    def test_negative_coords(self) -> None:
        d = distance(-1, -2, -4, -6)
        assert d == pytest.approx(5.0, abs=0.001)


class TestRelativeAngle:
    def test_looking_straight_at_entity(self) -> None:
        p = PlayerView(x=0, y=0, angle=0, pitch=0)
        ang = relative_angle(1, 0, p)
        assert ang == pytest.approx(0.0, abs=0.001)

    def test_entity_behind(self) -> None:
        p = PlayerView(x=0, y=0, angle=0, pitch=0)
        ang = relative_angle(-1, 0, p)
        assert abs(ang) == pytest.approx(math.pi, abs=0.001)

    def test_wraps_negative(self) -> None:
        p = PlayerView(x=0, y=0, angle=0, pitch=0)
        ang = relative_angle(0, -1, p)  # -90° = -π/2
        assert ang == pytest.approx(-math.pi / 2, abs=0.001)

    def test_player_rotated(self) -> None:
        """Player looking north (angle=π/2).  Entity east of player."""
        p = PlayerView(x=0, y=0, angle=math.pi / 2, pitch=0)
        ang = relative_angle(1, 0, p)
        assert ang == pytest.approx(-math.pi / 2, abs=0.001)


class TestRelativeInfo:
    def test_returns_angle_and_distance(self) -> None:
        p = PlayerView(x=0, y=0, angle=0, pitch=0)
        ang, dist = relative_info(3, 4, p)
        assert dist == pytest.approx(5.0, abs=0.001)
        assert ang == pytest.approx(math.atan2(4, 3), abs=0.001)


class TestProjectEntity:
    _player = PlayerView(x=5, y=5, angle=0, pitch=0)

    def test_entity_straight_ahead(self) -> None:
        """Entity at (7, 5) directly in front of player."""
        result = project_entity(
            7, 5,  # position
            150, 0.2,  # size_3d, width_3d
            0.0, 1.0,  # float_offset, pulse_scale
            self._player, 80,  # fov=80°
            800, 600,  # screen
            10.0,  # max_dist
        )
        assert result is not None
        # Entity straight ahead → screen x = centre
        assert result["screen_x"] == pytest.approx(400, abs=5)
        assert result["distance"] == pytest.approx(2.0, abs=0.01)

    def test_entity_outside_fov(self) -> None:
        """Entity far to the left (>40° from centre)."""
        result = project_entity(
            5, 6,  # x, y — at same x, slight differential, but relative angle depends
            150, 0.2, 0.0, 1.0,
            PlayerView(x=5, y=5, angle=0, pitch=0), 80,
            800, 600, 10.0,
        )
        # Entity at (5,6) relative to (5,5) is 90° → outside 40° half-FOV
        assert result is None

    def test_entity_too_far(self) -> None:
        result = project_entity(
            20, 5, 150, 0.2, 0.0, 1.0,
            self._player, 80, 800, 600, 10.0,
        )
        assert result is None

    def test_alpha_fades_with_distance(self) -> None:
        """Closer entities have higher alpha."""
        near = project_entity(
            6, 5, 150, 0.2, 0.0, 1.0,
            self._player, 80, 800, 600, 10.0,
        )
        far = project_entity(
            9, 5, 150, 0.2, 0.0, 1.0,
            self._player, 80, 800, 600, 10.0,
        )
        assert near is not None
        assert far is not None
        assert near["alpha"] >= far["alpha"]

    def test_size_affected_by_pulse(self) -> None:
        base = project_entity(
            7, 5, 100, 0.2, 0.0, 1.0,
            self._player, 80, 800, 600, 10.0,
        )
        pulsed = project_entity(
            7, 5, 100, 0.2, 0.0, 2.0,  # pulse_scale = 2
            self._player, 80, 800, 600, 10.0,
        )
        assert base is not None
        assert pulsed is not None
        # pulsed size ≈ 2× base size (minus rounding)
        assert pulsed["size"] > base["size"]

    def test_returns_expected_keys(self) -> None:
        result = project_entity(
            7, 5, 150, 0.2, 0.0, 1.0,
            self._player, 80, 800, 600, 10.0,
        )
        assert result is not None
        for k in ("distance", "screen_x", "screen_y", "size", "screen_width", "alpha"):
            assert k in result


import pytest
