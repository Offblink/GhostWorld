"""Mini-map rendering API — 2-D overview of the map.

All functions are stateless; callers provide grid, player, entity data.
"""

from __future__ import annotations

import math

import numpy as np
import pygame


def draw_minimap(
    dst: pygame.Surface,
    grid: np.ndarray,
    player_x: float,
    player_y: float,
    player_angle: float,
    entities: list[tuple[float, float, tuple[int, int, int]]] | None = None,
    *,
    mm_size: int = 200,
    margin: int = 10,
    corner: str = "top_right",
    bg_color: tuple[int, int, int, int] = (30, 35, 50, 200),
    wall_color: tuple[int, int, int] = (100, 100, 150),
    path_color: tuple[int, int, int] = (30, 30, 40),
    path_outline: tuple[int, int, int] = (20, 20, 30),
    player_color: tuple[int, int, int] = (0, 150, 255),
    entity_color: tuple[int, int, int] = (255, 100, 100),
    wall_colors: dict[int, tuple[int, int, int]] | None = None,
    agent_flashlight: bool = True,
    agent_flash_color: tuple[int, int, int, int] = (0, 255, 100, 50),
    agent_x: float | None = None,
    agent_y: float | None = None,
    agent_angle: float | None = None,
) -> pygame.Rect:
    """Draw a 2-D mini-map overlay onto *dst*.

    Parameters
    ----------
    dst:
        Destination surface (usually the screen).
    grid:
        2-D int array (0 = path, >0 = wall).
    player_x, player_y, player_angle:
        Current player position and yaw (radians, 0 = east).
    entities:
        Optional list of ``(x, y, color)`` tuples.
    mm_size:
        Size of the square mini-map in pixels.
    margin:
        Distance from the corner in pixels.
    corner:
        Which corner to anchor: ``"top_left"``, ``"top_right"``,
        ``"bottom_left"``, ``"bottom_right"``.
    bg_color:
        RGBA fill colour for the map background.
    wall_color:
        Default colour for wall cells.
    path_color:
        Fill colour for path cells.
    path_outline:
        Outline colour for path cells.
    player_color:
        Colour of the player dot.
    entity_color:
        Default colour for entity dots (overridden per-entity if
        colour is provided in the *entities* list).
    wall_colors:
        Optional lookup ``wall_type → colour`` for per-type wall
        colouring (overrides *wall_color*).

    Returns
    -------
    pygame.Rect
        The bounding box of the rendered mini-map (useful for hit-testing).
    """
    sdw, sdh = dst.get_size()
    mm = pygame.Surface((mm_size, mm_size), pygame.SRCALPHA)
    pygame.draw.rect(mm, bg_color, mm.get_rect(), border_radius=5)

    gw, gh = grid.shape
    cell = min((mm_size - 10) // gw, (mm_size - 10) // gh, 8)
    ox = (mm_size - gw * cell) // 2
    oy = (mm_size - gh * cell) // 2

    for x in range(gw):
        for y in range(gh):
            rect = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)
            val = int(grid[x, y])
            if val != 0:
                wcol = wall_color
                if wall_colors and val in wall_colors:
                    wcol = wall_colors[val]
                pygame.draw.rect(mm, wcol, rect)
            else:
                pygame.draw.rect(mm, path_color, rect)
                pygame.draw.rect(mm, path_outline, rect, 1)

    # player
    pp = (int(ox + player_x * cell), int(oy + player_y * cell))
    r = max(2, cell // 3)
    pygame.draw.circle(mm, player_color, pp, r)
    ex = pp[0] + int(math.cos(player_angle) * cell * 0.5)
    ey = pp[1] + int(math.sin(player_angle) * cell * 0.5)
    pygame.draw.line(mm, player_color, pp, (ex, ey), 1)

    cone_len = cell * 3.5
    # agent flashlight cone (60° FOV, green)
    if agent_flashlight and agent_x is not None and agent_y is not None and agent_angle is not None:
        ap = (int(ox + agent_x * cell), int(oy + agent_y * cell))
        a_left = agent_angle - math.radians(30)
        a_right = agent_angle + math.radians(30)
        apts = [
            ap,
            (ap[0] + int(math.cos(a_left) * cone_len), ap[1] + int(math.sin(a_left) * cone_len)),
            (ap[0] + int(math.cos(a_right) * cone_len), ap[1] + int(math.sin(a_right) * cone_len)),
        ]
        pygame.draw.polygon(mm, agent_flash_color, apts)
        pygame.draw.circle(mm, (0, 255, 100), ap, max(2, cell // 3))

    # entities
    if entities:
        for ex, ey, ecol in entities:
            ep = (int(ox + ex * cell), int(oy + ey * cell))
            pygame.draw.circle(mm, ecol, ep, max(1, cell // 3))

    # position
    if corner == "top_right":
        pos = (sdw - mm_size - margin, margin)
    elif corner == "top_left":
        pos = (margin, margin)
    elif corner == "bottom_right":
        pos = (sdw - mm_size - margin, sdh - mm_size - margin)
    elif corner == "bottom_left":
        pos = (margin, sdh - mm_size - margin)
    else:
        pos = (margin, margin)

    dst.blit(mm, pos)
    return pygame.Rect(pos[0], pos[1], mm_size, mm_size)
