"""First-person controller with collision detection.

Receives abstract motion deltas — the frontend maps input to these.
"""

from __future__ import annotations

import math

import numpy as np

from .frame import PlayerView


class FirstPersonController:
    """First-person camera controller with grid-based collision.

    Parameters
    ----------
    x, y:
        Initial world position.
    angle:
        Initial yaw in radians (0 = east, CCW positive).
    pitch:
        Initial pitch offset in **pixels**.
    walls:
        2-D int array where ``> 0`` = impassable wall.
    radius:
        Player collision radius in world units.
    pitch_limit_ratio:
        Max pitch as fraction of screen height (0 = none).
    """

    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        pitch: float,
        walls: np.ndarray,
        radius: float = 0.3,
        pitch_limit_ratio: float = 0.35,
    ) -> None:
        self.x = x
        self.y = y
        self.angle = angle
        self.pitch = pitch
        self._walls = walls
        self.radius = radius
        self._pitch_ratio = pitch_limit_ratio

        # Sensible default; call set_screen_height() once the real
        # window is created.
        self._screen_h = 600

    # ── public API ──────────────────────────────────────────────


    def set_walls(self, walls: np.ndarray) -> None:
        """Update the wall grid used for collision (e.g. after map edit)."""
        self._walls = walls
    def set_screen_height(self, h: int) -> None:
        self._screen_h = h

    def move(self, forward: float, strafe: float, dt: float) -> tuple[float, float]:
        """Apply forward/strafe deltas with collision resolution.

        Returns the actual (dx, dy) moved.
        """
        dx = forward * math.cos(self.angle) + strafe * math.cos(self.angle - math.pi / 2)
        dy = forward * math.sin(self.angle) + strafe * math.sin(self.angle - math.pi / 2)

        # normalise so diagonal isn't faster
        mag = math.sqrt(dx * dx + dy * dy)
        if mag > 1.0:
            dx /= mag
            dy /= mag

        return self._move_with_collision(dx, dy)

    def rotate(self, yaw_delta: float, pitch_delta: float, dt: float) -> None:
        """Accumulate yaw / pitch."""
        self.angle += yaw_delta
        self.angle %= 2 * math.pi

        self.pitch += pitch_delta
        limit = max(1, int(self._screen_h * self._pitch_ratio))
        self.pitch = max(-limit, min(limit, self.pitch))

    def set_position(
        self,
        x: float,
        y: float,
        angle: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Teleport to a new position / orientation."""
        self.x = x
        self.y = y
        if angle is not None:
            self.angle = angle
        if pitch is not None:
            self.pitch = pitch

    def player_view(self) -> PlayerView:
        """Snapshot current camera state."""
        return PlayerView(
            x=self.x, y=self.y, angle=self.angle, pitch=self.pitch,
        )

    # ── internals ───────────────────────────────────────────────

    def _move_with_collision(self, dx: float, dy: float) -> tuple[float, float]:
        """Separating-axis slide; returns (actual_dx, actual_dy)."""
        dx, _ = self._slide_axis(dx, 0)
        dy, _ = self._slide_axis(dy, 1)
        return dx, dy

    def _slide_axis(self, delta: float, axis: int) -> tuple[float, float]:
        """Try moving *delta* along one axis with back-off.

        *axis*: 0 = X, 1 = Y.  Returns ``(actual, remaining)``.

        Tries the full *delta* first; on collision falls back through
        progressively shorter steps (0.9, 0.75, 0.6, 0.45, 0.3).
        """
        # First attempt: full delta
        tx = self.x + (delta if axis == 0 else 0)
        ty = self.y + (delta if axis == 1 else 0)
        if not self._check_collision(tx, ty):
            if axis == 0:
                self.x = tx
            else:
                self.y = ty
            return delta, 0.0

        # Back-off: try progressively shorter along this axis
        for i in range(5):
            t = delta * (0.9 - i * 0.15)
            tx = self.x + (t if axis == 0 else 0)
            ty = self.y + (t if axis == 1 else 0)
            if not self._check_collision(tx, ty):
                if axis == 0:
                    self.x = tx
                else:
                    self.y = ty
                return t, delta - t
        return 0.0, delta

    def _check_collision(self, x: float, y: float) -> bool:
        """True if *any* of the 9 sample points hits a wall."""
        r = self.radius
        pts = [
            (x, y),
            (x + r, y), (x - r, y),
            (x, y + r), (x, y - r),
            (x + r * 0.7, y + r * 0.7),
            (x - r * 0.7, y + r * 0.7),
            (x + r * 0.7, y - r * 0.7),
            (x - r * 0.7, y - r * 0.7),
        ]
        w, h = self._walls.shape
        for px, py in pts:
            ix = int(px)
            iy = int(py)
            if ix < 0 or ix >= w or iy < 0 or iy >= h:
                return True
            if self._walls[ix, iy] != 0:
                return True
        return False
