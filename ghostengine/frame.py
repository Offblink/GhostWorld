"""Immutable data contracts for the engine pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pygame


# ═══════════════════════════════════════════════════════════════════
# Player
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PlayerView:
    """Snapshot of the player camera for one frame."""
    x: float
    y: float
    angle: float        # radians, 0=right, CCW positive
    pitch: float        # pixels offset from screen-centre horizon


# ═══════════════════════════════════════════════════════════════════
# Entity
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EntityView:
    """Lightweight render-descriptor for one entity (sprite / item / avatar / portal)."""
    x: float
    y: float

    texture: pygame.Surface | list[pygame.Surface] | None = None  # static, GIF frames; None means use texture_path
    texture_path: str = ""                                         # path for network / lazy loading
    textures: dict[str, pygame.Surface | list[pygame.Surface]] | None = None  # directional (front/back/left/right)
    texture_paths: dict[str, str] | None = None                    # directional path variant, for serialisation
    facing: float = 0.0             # radians, for directional texture selection

    kind: str = "item"              # "avatar" | "item" | "portal"
    size_3d: float         = 150    # base projection size (pixels)
    width_3d: float        = 0.2    # base projection width (world units)

    anim: dict[str, Any]              = field(default_factory=dict)
    occlusion: str = "center"         # "center" | "per_column"
    visible: bool = True

    # ── interaction ──
    mm_trigger: bool = False
    pickup: bool = False
    pickup_label: str = ""
    capture_for: str = ""            # ""=public, "*"=anyone, "name"=owner-only auto-pickup
    portal_target: dict | None = None # {"portal_id":str, "map":str}
    dialogue: str = ""               # NPC dialogue text (empty = no dialogue)

    # ── metaverse identity ──
    name: str = ""
    owner: str = ""                  # who controls this avatar ("human" | agent_id | "")
    metadata: dict[str, Any] = field(default_factory=dict)

# ═══════════════════════════════════════════════════════════════════
# Colours
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WallDef:
    color: tuple[int, int, int] | None = None
    texture: pygame.Surface | None = None


@dataclass
class ColorConfig:
    sky_top: tuple[int, int, int]   = (135, 206, 235)
    sky_bottom: tuple[int, int, int] = (240, 248, 255)
    floor: tuple[int, int, int]      = (34, 139, 34)
    walls: dict[int, WallDef]        = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Fog
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FogConfig:
    """Distance-based fog for walls and entities."""
    color: tuple[int, int, int] = (80, 80, 100)
    start: float = 5.0
    end: float = 10.0
    enabled: bool = True


# ═══════════════════════════════════════════════════════════════════
# Frame
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Frame:
    """Complete world-state for one frame.  Passed to render()."""
    player: PlayerView
    walls: np.ndarray
    entities: list[EntityView]
    colors: ColorConfig

    fov: float = 80.0
    max_view_dist: float = 10.0
    ray_count: int = 300
    fog: FogConfig = field(default_factory=FogConfig)
    exit_pos: tuple | None = None
    exit_config: dict = field(default_factory=dict)
    minimap_config: dict = field(default_factory=lambda: {"mode": "always", "duration": 0})
