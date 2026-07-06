"""Ray-cast helper and entity screen-projection math.

Low-level geometry functions shared by the renderer.
"""

from __future__ import annotations

import math

from .frame import PlayerView


# ── pure geometry ──────────────────────────────────────────────

def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance between two 2-D points."""
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def relative_angle(
    x: float, y: float, player: PlayerView,
) -> float:
    """Angle from *player* to point *(x, y)*, normalised to ``[-π, π]``."""
    dx = x - player.x
    dy = y - player.y
    ang = math.atan2(dy, dx) - player.angle
    while ang > math.pi:
        ang -= 2 * math.pi
    while ang < -math.pi:
        ang += 2 * math.pi
    return ang


def relative_info(
    x: float, y: float, player: PlayerView,
) -> tuple[float, float]:
    """Angle + distance from *player* to point *(x, y)*.

    Returns ``(angle_rad, distance)``.  Avoids recomputing ``dx/dy``
    when both values are needed (e.g. in :func:`project_entity`).
    """
    dx = x - player.x
    dy = y - player.y
    dist = math.sqrt(dx * dx + dy * dy)
    ang = math.atan2(dy, dx) - player.angle
    while ang > math.pi:
        ang -= 2 * math.pi
    while ang < -math.pi:
        ang += 2 * math.pi
    return ang, dist


# ── projection ─────────────────────────────────────────────────

def project_entity(
    entity_x: float,
    entity_y: float,
    size_3d: float,
    width_3d: float,
    float_offset: float,
    pulse_scale: float,
    player: PlayerView,
    fov_deg: float,
    screen_width: int,
    view_height: int,
    max_dist: float,
) -> dict | None:
    """Compute screen-space projection for one entity.

    Returns ``None`` when the entity is outside the FOV or too far.
    Otherwise returns a dict of projection values.
    """
    rel, dist = relative_info(entity_x, entity_y, player)
    if dist < 0.001 or dist >= max_dist:
        return None

    fov_rad = math.radians(fov_deg)
    if abs(rel) > fov_rad / 2:
        return None

    # screen x (0..screen_width)
    screen_x = (0.5 + rel / fov_rad) * screen_width

    # projected size
    size = int(size_3d * pulse_scale / (dist + 0.5))
    size = max(10, min(view_height * 2, size))
    # screen y (floor-projected, with float offset)
    horizon = view_height // 2 + int(player.pitch)
    horizon = max(0, min(view_height, horizon))
    proj_factor = view_height * 0.5
    floor_y = horizon + (proj_factor / dist) - (
        (float_offset + 0.2) * proj_factor / dist
    )
    screen_y = min(view_height, max(0, int(floor_y)))

    # width projection
    ent_w = int(
        (width_3d / (dist + 0.5))
        * (screen_width / math.tan(fov_rad / 2))
    )
    ent_w = max(4, ent_w)

    # distance-based alpha
    alpha = max(120, 255 - int(dist * 12))
    alpha = min(255, alpha)

    return {
        "distance": dist,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "size": size,
        "screen_width": ent_w,
        "alpha": alpha,
    }
