"""GhostEngine — software raycasting 3-D engine.

Usage::

    from ghostengine import Frame, PlayerView, EntityView, ColorConfig, render
    import numpy as np

    frame = Frame(
        player=PlayerView(x=5, y=5, angle=0, pitch=0),
        walls=np.zeros((10, 10), dtype=int),
        entities=[],
        colors=ColorConfig(),
    )

    surface = pygame.display.set_mode((800, 600))
    render(frame, surface)
    pygame.display.flip()
"""

from .animation import AnimState, compute_animation
from .controller import FirstPersonController
from .entity import distance, project_entity, relative_angle, relative_info
from .frame import ColorConfig, EntityView, FogConfig, Frame, PlayerView, WallDef
from .mapfile import build_colors, build_entities, load_raw, save_raw, validate_entities_on_walls
from .minimap import draw_minimap
from .renderer import render
from .texture import TextureLoader

__all__ = [
    "Frame", "PlayerView", "EntityView", "ColorConfig", "WallDef", "FogConfig",
    "render",
    "FirstPersonController",
    "AnimState", "compute_animation",
    "distance", "relative_angle", "relative_info", "project_entity",
    "TextureLoader",
    "load_raw", "save_raw", "build_colors", "build_entities", "validate_entities_on_walls",
    "draw_minimap",
]
