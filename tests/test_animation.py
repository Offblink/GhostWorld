"""Tests for animation.py — stateless pure functions.

All tests run without pygame; only math is exercised.
"""

import math

from ghostengine.animation import AnimState, compute_animation


class TestComputeAnimation:
    """Core animation computation."""

    def test_no_config_returns_identity(self) -> None:
        result = compute_animation({}, 0)
        assert result == AnimState(0.0, 1.0, 0.0, 0)

    def test_float_offset_sine(self) -> None:
        """float: speed=0.003, amp=0.05 at t where sin=1."""
        t = (math.pi / 2) / 0.003  # sin(t * 0.003) = sin(π/2) = 1
        result = compute_animation(
            {"float": {"speed": 0.003, "amp": 0.05}}, t,
        )
        assert result.float_offset == pytest.approx(0.05, abs=0.001)
        assert result.pulse_scale == 1.0
        assert result.rotation == 0.0

    def test_float_zero_at_zero(self) -> None:
        result = compute_animation(
            {"float": {"speed": 0.005, "amp": 0.5}}, 0,
        )
        assert result.float_offset == pytest.approx(0.0, abs=0.001)

    def test_pulse_scale(self) -> None:
        """Pulse at sin=1: scale = 1 + amp."""
        t = (math.pi / 2) / 0.005
        result = compute_animation(
            {"pulse": {"speed": 0.005, "amp": 0.1}}, t,
        )
        assert result.pulse_scale == pytest.approx(1.1, abs=0.001)

    def test_pulse_default_amp_is_one(self) -> None:
        """When amp is omitted, default to 1.0."""
        t = (math.pi / 2) / 0.004
        result = compute_animation(
            {"pulse": {"speed": 0.004}}, t,
        )
        assert result.pulse_scale == pytest.approx(2.0, abs=0.001)

    def test_rotation_wraps(self) -> None:
        result = compute_animation(
            {"rotation": {"speed": 0.001}}, 100_000,
        )
        assert 0.0 <= result.rotation < 2 * math.pi

    def test_rotation_linear(self) -> None:
        r1 = compute_animation({"rotation": {"speed": 0.001}}, 1000)
        r2 = compute_animation({"rotation": {"speed": 0.001}}, 2000)
        # angle doubles when time doubles
        assert r2.rotation == pytest.approx(r1.rotation * 2 % (2 * math.pi), abs=0.01)

    def test_combined_animations(self) -> None:
        """Heart: float + pulse together."""
        t = (math.pi / 2) / 0.003  # sin = 1
        result = compute_animation(
            {
                "float": {"speed": 0.003, "amp": 0.05},
                "pulse": {"speed": 0.005, "amp": 0.1},
            },
            t,
        )
        assert result.float_offset == pytest.approx(0.05, abs=0.001)
        # pulse at this t: sin(π/2 * 0.005 / 0.003) ≈ sin(2.618) ≈ 0.5
        expected_scale = 1.0 + 0.1 * math.sin(t * 0.005)
        assert result.pulse_scale == pytest.approx(expected_scale, abs=0.01)

    def test_gif_frame_index(self) -> None:
        """frame_index cycles through 4 frames."""
        result = compute_animation(
            {"gif": {"speed": 0.01}}, 150, frame_count=4,
        )
        assert result.frame_index == 1  # 150 * 0.01 = 1.5 → int = 1

    def test_gif_frame_index_wraps(self) -> None:
        result = compute_animation(
            {"gif": {"speed": 0.01}}, 1000, frame_count=4,
        )
        assert result.frame_index == (1000 * 0.01) % 4

    def test_static_texture_frame_index_zero(self) -> None:
        """frame_count=1 → frame_index always 0."""
        result = compute_animation({"gif": {"speed": 0.1}}, 9999, frame_count=1)
        assert result.frame_index == 0

    def test_empty_config_dicts_ignored(self) -> None:
        """Empty sub-dicts are no-ops."""
        result = compute_animation({"float": {}}, 1000)
        assert result.float_offset == 0.0


# hook for pytest
import pytest
