"""Core raycasting render pipeline.

Entry point: :func:`render`.
"""

from __future__ import annotations

import numpy as np

import math
from dataclasses import dataclass

import pygame

from .animation import compute_animation
from .defaults import (
    DEFAULT_RAY_STEP,
    ENTITY_DEFAULT_OCCLUSION,
)
from .entity import project_entity
from .frame import ColorConfig, EntityView, Frame, PlayerView, WallDef



# ── tunables ──────────────────────────────────────────────────

WALL_HEIGHT_RATIO = 0.8   # wall height = screen_h * RATIO / (dist + 0.1)
SKY_PRECOMPUTE = True
# ═══════════════════════════════════════════════════════════════════
# Ray-cast result
# ═══════════════════════════════════════════════════════════════════

@dataclass
class _RayHit:
    distance: float
    face_normal: int   # 0 = vertical (X-face), 1 = horizontal (Y-face)
    tex_x: float       # 0.0 – 1.0
    wall_type: int

# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def render(frame: Frame, dst: pygame.Surface) -> None:
    """Render one frame onto *dst*.

    ``dst`` dimensions determine the viewport size.  Every call is
    self-contained — the engine holds no mutable state.
    """
    sw, sh = dst.get_size()
    if sw <= 0 or sh <= 0:
        return

    # Fill entire surface to prevent ghosting from previous frames
    dst.fill((0, 0, 0))
    _WALL_CACHE.clear()
    _SCALED_CACHE.clear()

    _draw_sky_floor(dst, sw, sh, frame.player, frame.colors)
    wall_dists = _cast_and_draw_walls(frame, dst, sw, sh)
    _draw_entities(frame, dst, sw, sh, wall_dists)


# ═══════════════════════════════════════════════════════════════════
# Sky / floor
# ═══════════════════════════════════════════════════════════════════

def _draw_sky_floor(
    dst: pygame.Surface,
    sw: int, sh: int,
    player: PlayerView,
    colors: ColorConfig,
) -> None:
    horizon = max(0, min(sh, sh // 2 + int(player.pitch)))

    # Build sky gradient surface once and cache by (top, bottom, width, height)
    sky_key = (colors.sky_top, colors.sky_bottom, sw, horizon)
    sky_surf = _SKY_CACHE.get(sky_key)
    if sky_surf is None or sky_surf.get_height() != horizon:
        sky_surf = pygame.Surface((sw, max(1, horizon)))
        for y in range(horizon):
            t = y / max(1, horizon - 1) if horizon > 1 else 0.5
            r = int(colors.sky_top[0] * (1 - t) + colors.sky_bottom[0] * t)
            g = int(colors.sky_top[1] * (1 - t) + colors.sky_bottom[1] * t)
            b = int(colors.sky_top[2] * (1 - t) + colors.sky_bottom[2] * t)
            pygame.draw.line(sky_surf, (r, g, b), (0, y), (sw, y))
        if len(_SKY_CACHE) > 4:
            _SKY_CACHE.pop(next(iter(_SKY_CACHE)))
        _SKY_CACHE[sky_key] = sky_surf
    dst.blit(sky_surf, (0, 0))

    # floor — fill below horizon with floor colour
    if horizon < sh:
        fh = sh - horizon
        floor_key = (colors.floor, sw, fh)
        floor_surf = _FLOOR_CACHE.get(floor_key)
        if floor_surf is None or floor_surf.get_height() != fh:
            floor_surf = pygame.Surface((sw, fh))
            floor_surf.fill(colors.floor)
            if len(_FLOOR_CACHE) > 2:
                _FLOOR_CACHE.pop(next(iter(_FLOOR_CACHE)))
            _FLOOR_CACHE[floor_key] = floor_surf
        dst.blit(floor_surf, (0, horizon))

def _fog_factor(dist: float, fog: "FogConfig") -> float:
    """0..1 fog opacity at a given distance."""
    if not fog.enabled or dist < fog.start:
        return 0.0
    if dist >= fog.end:
        return 1.0
    return (dist - fog.start) / (fog.end - fog.start)
# ═══════════════════════════════════════════════════════════════════
# Ray-casting
# ═══════════════════════════════════════════════════════════════════

def _cast_ray(
    player: PlayerView,
    walls: np.ndarray,
    ray_angle: float,
    max_dist: float,
    step: float = DEFAULT_RAY_STEP,
) -> _RayHit | None:
    """DDA-style ray march.  Returns ``None`` if no wall hit within range."""
    grid: np.ndarray = walls
    w, h = grid.shape

    dir_x = math.cos(ray_angle)
    dir_y = math.sin(ray_angle)

    px = player.x
    py = player.y

    for _ in range(int(max_dist / step) + 1):
        px += dir_x * step
        py += dir_y * step

        ix = int(px)
        iy = int(py)

        if ix < 0 or ix >= w or iy < 0 or iy >= h:
            break

        wall_type = int(grid[ix, iy])
        if wall_type != 0:
            # back-track to face intersection
            # Determine which face was hit by checking the sign of
            # the delta components entering this cell.
            prev_x = px - dir_x * step
            prev_y = py - dir_y * step

            # Did we cross an X-boundary or Y-boundary last step?
            prev_ix = int(prev_x)
            prev_iy = int(prev_y)

            face: int
            tex_x: float

            if prev_ix != ix:
                # crossed vertical (X) face
                face = 0
                hit_edge = ix if dir_x > 0 else ix + 1
                tex_x = py - math.floor(py)
            else:
                # crossed horizontal (Y) face
                face = 1
                hit_edge = iy if dir_y > 0 else iy + 1
                tex_x = px - math.floor(px)

            tex_x = tex_x - math.floor(tex_x)  # 0..1

            # raw distance
            dx = px - player.x
            dy = py - player.y
            dist = math.sqrt(dx * dx + dy * dy)

            # fisheye correction
            dist *= math.cos(ray_angle - player.angle)
            dist = max(0.01, min(dist, max_dist))

            return _RayHit(
                distance=dist,
                face_normal=face,
                tex_x=tex_x,
                wall_type=wall_type,
            )

    return None


# ═══════════════════════════════════════════════════════════════════
# Wall drawing
# ═══════════════════════════════════════════════════════════════════

_SKY_CACHE: dict[tuple, pygame.Surface] = {}
_FLOOR_CACHE: dict[tuple, pygame.Surface] = {}

_WALL_CACHE: dict[tuple, pygame.Surface] = {}
_WALL_CACHE_MAX = 50


def _cast_and_draw_walls(
    frame: Frame,
    dst: pygame.Surface,
    sw: int, sh: int,
) -> list[float]:
    """Cast all rays, draw wall columns, return wall_distances list."""
    half_fov = math.radians(frame.fov / 2)
    line_w = sw / frame.ray_count
    horizon = max(0, min(sh, sh // 2 + int(frame.player.pitch)))

    wall_dists: list[float] = []


    colors = frame.colors

    for i in range(frame.ray_count):
        ray_ang = (frame.player.angle - half_fov
                   + (i / frame.ray_count) * math.radians(frame.fov))

        hit = _cast_ray(frame.player, frame.walls, ray_ang,
                        frame.max_view_dist)



        if hit is None:
            wall_dists.append(frame.max_view_dist)
            continue
        wall_dists.append(hit.distance)
        # brightness
        bright = max(50, 255 - int(hit.distance * 20)) / 255.0
        # fog
        ff = 0.0
        if frame.fog.enabled:
            ff = _fog_factor(hit.distance, frame.fog)
            bright = bright * (1 - ff * 0.7)

        # wall height
        wall_h = min(sh, int(sh * WALL_HEIGHT_RATIO / (hit.distance + 0.1)))
        wall_top = max(0, int(horizon - wall_h // 2))
        wall_bottom = min(sh, wall_top + wall_h)

        x_start = int(i * line_w)
        x_width = max(2, int(line_w + 1))

        # resolve wall appearance
        wd = colors.walls.get(hit.wall_type)
        color: tuple[int, int, int] | None = None
        tex: pygame.Surface | None = None

        if wd is not None:
            color = wd.color
            tex = wd.texture

        if color is None and tex is None:
            color = (100, 100, 150)  # fallback

        if tex is not None and wall_h > 0:
            tw, th = tex.get_size()
            if tw <= 1 or th <= 1:
                color = color or (100, 100, 150)
            else:
                _draw_textured_wall_column(dst, tex, hit.face_normal, hit.tex_x,
                                           x_start, wall_top, x_width, wall_h, bright)
                continue
        if color is not None and wall_h > 0:
            r = max(0, min(255, int(color[0] * bright)))
            g = max(0, min(255, int(color[1] * bright)))
            b = max(0, min(255, int(color[2] * bright)))
            if frame.fog.enabled:
                ff = _fog_factor(hit.distance, frame.fog)
                fc = frame.fog.color
                r = int(r * (1 - ff) + fc[0] * ff)
                g = int(g * (1 - ff) + fc[1] * ff)
                b = int(b * (1 - ff) + fc[2] * ff)
            pygame.draw.rect(dst, (r, g, b),
                             (x_start, wall_top, x_width, wall_h))

    return wall_dists


def _draw_textured_wall_column(
    dst: pygame.Surface,
    texture: pygame.Surface,
    face: int,
    tex_x: float,
    x: int, y_top: int,
    col_w: int, col_h: int,
    brightness: float,
) -> None:
    """Sample one column from *texture*, scale, blit."""
    tw, th = texture.get_size()

    sample_x = int(tex_x * tw) % tw
    sample_x = max(0, min(tw - 1, sample_x))

    # Cache key
    key = (id(texture), sample_x, col_w, col_h, int(brightness * 100))
    global _WALL_CACHE
    cached = _WALL_CACHE.get(key)
    if cached is not None:
        dst.blit(cached, (x, y_top))
        return

    # subsurface → scale → apply brightness
    try:
        col_surf = texture.subsurface((sample_x, 0, 1, th))
    except ValueError:
        col_surf = texture

    scaled = pygame.transform.scale(col_surf, (col_w, col_h))
    if brightness < 0.99:
        factor = max(0, brightness)
        dark = pygame.Surface((col_w, col_h))
        dark.fill((0, 0, 0))
        dark.set_alpha(int((1.0 - brightness) * 255))
        scaled.blit(dark, (0, 0))

    # cache
    if len(_WALL_CACHE) >= _WALL_CACHE_MAX:
        _WALL_CACHE.pop(next(iter(_WALL_CACHE)))
    _WALL_CACHE[key] = scaled

    dst.blit(scaled, (x, y_top))


_FALLBACK_CACHE: dict[str, pygame.Surface] = {}


def _fallback_tex(kind: str, pickup: bool) -> pygame.Surface:
    """Generate a small default sprite for entities without a texture."""
    key = f"{kind}_{pickup}"
    if key in _FALLBACK_CACHE:
        return _FALLBACK_CACHE[key]
    s = 32
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    if kind == "avatar":
        color = (100, 180, 255)
    elif kind == "portal":
        color = (200, 100, 255)
    elif pickup:
        color = (255, 215, 0)
    else:
        color = (180, 180, 180)
    cx = cy = s // 2
    r = s // 2 - 2
    for i in range(r):
        a = 255 - i * 30
        if a > 0:
            pygame.draw.circle(surf, (*color, a), (cx, cy), r - i)
    _FALLBACK_CACHE[key] = surf
    return surf


# ═══════════════════════════════════════════════════════════════════
# Entity drawing
# ═══════════════════════════════════════════════════════════════════

_SCALED_CACHE: dict[tuple, pygame.Surface] = {}
_SCALED_CACHE_MAX = 64



def _resolve_texture(ent: EntityView, player: PlayerView):
    """Pick the right texture for an entity based on view angle and facing."""
    if ent.textures is None:
        return ent.texture
    dx = ent.x - player.x
    dy = ent.y - player.y
    angle_to = math.atan2(dy, dx)
    rel = angle_to - ent.facing
    while rel > math.pi: rel -= 2 * math.pi
    while rel < -math.pi: rel += 2 * math.pi
    if abs(rel) < math.pi / 4: key = "front"
    elif abs(rel) > 3 * math.pi / 4: key = "back"
    elif rel > 0: key = "right"
    else: key = "left"
    return ent.textures.get(key, ent.texture)

def _draw_entities(
    frame: Frame,
    dst: pygame.Surface,
    sw: int, sh: int,
    wall_dists: list[float],
) -> None:
    """Project every visible entity, sort by distance, draw far→near."""
    line_w = sw / frame.ray_count
    projected = []
    now = pygame.time.get_ticks()
    for ent in frame.entities:
        if not ent.visible:
            continue
        tex = _resolve_texture(ent, frame.player)
        tex_len = len(tex) if isinstance(tex, list) else 1
        anim_state = compute_animation(ent.anim, now, tex_len)
        proj = project_entity(
            ent.x, ent.y,
            ent.size_3d, ent.width_3d,
            anim_state.float_offset, anim_state.pulse_scale,
            frame.player, frame.fov,
            sw, sh, frame.max_view_dist,
        )
        if proj is None:
            continue
        projected.append((proj, ent, anim_state, tex))
    projected.sort(key=lambda x: x[0]["distance"], reverse=True)
    for proj, ent, anim_state, tex in projected:
        _draw_one_entity(
            dst, proj, ent, anim_state, wall_dists, line_w, sw, frame, tex,
        )


def _draw_one_entity(
    dst: pygame.Surface,
    proj: dict,
    ent: EntityView,
    anim_state,
    wall_dists: list[float],
    line_w: float,
    sw: int,
    frame: Frame,
    tex=None,
) -> None:
    """Draw a single entity with occlusion clipping."""
    sx = proj["screen_x"]
    sy = proj["screen_y"]
    size = proj["size"]
    alpha = proj["alpha"]
    ent_w = proj["screen_width"]
    dist = proj["distance"]
    # fog alpha
    if frame.fog.enabled:
        ff = _fog_factor(dist, frame.fog)
        alpha = max(0, int(alpha * (1 - ff)))

    occlusion = ent.occlusion or ENTITY_DEFAULT_OCCLUSION

    # ── occlusion check ──
    if occlusion == "center":
        ray_idx = int(sx / line_w)
        ray_idx = max(0, min(len(wall_dists) - 1, ray_idx))
        if dist >= wall_dists[ray_idx]:
            return

    # ── texture resolve ──
    if tex is None:
        tex = ent.texture
    if tex is None:
        # fallback: render as simple colored blob
        tex = _fallback_tex(ent.kind, ent.pickup)
    if isinstance(tex, list):
        if len(tex) == 0:
            return
        idx = anim_state.frame_index % len(tex)
        tex = tex[idx]

    # ── scale & cache ──
    sw_i = max(1, int(ent_w))
    sh_i = max(1, int(size))
    cache_key = (id(tex), sw_i, sh_i, alpha, anim_state.frame_index)

    global _SCALED_CACHE
    cached = _SCALED_CACHE.get(cache_key)
    if cached is not None:
        scaled = cached
    else:
        # Apply rotation if configured
        base = tex
        if anim_state.rotation != 0.0:
            deg = math.degrees(anim_state.rotation)
            base = pygame.transform.rotate(tex, deg)

        scaled = pygame.transform.scale(base, (sw_i, sh_i))

        if alpha < 255:
            tmp = pygame.Surface((sw_i, sh_i), pygame.SRCALPHA)
            tmp.blit(scaled, (0, 0))
            tmp.set_alpha(alpha)
            scaled = tmp

        if len(_SCALED_CACHE) >= _SCALED_CACHE_MAX:
            _SCALED_CACHE.pop(next(iter(_SCALED_CACHE)))
        _SCALED_CACHE[cache_key] = scaled

    # ── per-column occlusion ──
    if occlusion == "per_column":
        _draw_per_column(dst, scaled, sx, sy, ent_w, dist, wall_dists, line_w, sw)
    else:
        # center occlusion already passed → draw full
        rect = scaled.get_rect(midbottom=(sx, sy))
        dst.blit(scaled, rect)


def _draw_per_column(
    dst: pygame.Surface,
    surf: pygame.Surface,
    sx: float, sy: float,
    ent_w: float, dist: float,
    wall_dists: list[float],
    line_w: float,
    sw: int,
) -> None:
    """Draw only the visible columns of *surf* (not blocked by walls)."""
    sw_i, sh_i = surf.get_size()
    left = sx - ent_w / 2
    right = sx + ent_w / 2

    # Sample ~41 points across the entity span
    samples = 41
    visible_ranges: list[tuple[float, float]] = []
    range_start = None

    for i in range(samples):
        sample_x = left + (ent_w * i) / (samples - 1)
        sample_x = max(0, min(sw - 1, sample_x))
        ray_idx = int(sample_x / line_w)
        ray_idx = max(0, min(len(wall_dists) - 1, ray_idx))

        vis = dist < wall_dists[ray_idx]
        if vis:
            if range_start is None:
                range_start = (sample_x - left) / ent_w  # 0..1
        else:
            if range_start is not None:
                visible_ranges.append((range_start, (sample_x - left) / ent_w))
                range_start = None

    if range_start is not None:
        visible_ranges.append((range_start, 1.0))

    if not visible_ranges:
        return

    # Merge nearby ranges
    merged: list[tuple[float, float]] = [visible_ranges[0]]
    for lo, hi in visible_ranges[1:]:
        if lo - merged[-1][1] < 0.05:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))

    # Draw each visible column strip
    for lo, hi in merged:
        lo = max(0.0, lo)
        hi = min(1.0, hi)
        if lo >= hi:
            continue
        start_px = int(lo * sw_i)
        end_px = int(hi * sw_i) + 1
        start_px = max(0, min(sw_i, start_px))
        end_px = max(start_px, min(sw_i, end_px))
        if start_px < end_px:
            strip = surf.subsurface((start_px, 0, end_px - start_px, sh_i))
            strip_rect = strip.get_rect(
                midbottom=(sx - ent_w / 2 + start_px + (end_px - start_px) / 2, sy),
            )
            dst.blit(strip, strip_rect)
