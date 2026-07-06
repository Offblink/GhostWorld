"""Headless snapshot renderer — turns WorldState into PNG from any avatar's view."""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
import pygame

from ghostengine import (
    Frame, PlayerView, EntityView, ColorConfig, WallDef, FogConfig,
    render, TextureLoader, load_raw, build_colors,
)


# ensure pygame is initialized for Surface operations
_pygame_inited = False


def _ensure_pygame():
    global _pygame_inited
    if not _pygame_inited:
        pygame.init()
        _pygame_inited = True


def render_snapshot(ws, avatar_id: str, map_path: str = "",
                    width: int = 800, height: int = 600) -> bytes:
    """Render a first-person snapshot for *avatar_id* and return PNG bytes.

    Args:
        ws: WorldState instance.
        avatar_id: The avatar whose perspective to render from.
        map_path: Path to the map JSON (for colors/textures).
        width, height: Output image dimensions.

    Returns:
        PNG file as bytes.
    """
    _ensure_pygame()

    av = ws.avatars.get(avatar_id)
    if not av:
        raise ValueError(f"Avatar '{avatar_id}' not found in world state")

    # load map data for colors and textures
    colors = ColorConfig()
    grid = ws.grid
    items_source = ws.items  # default: main map items
    # if avatar is on a different map, use that map's grid and items
    if av.current_map and av.current_map in ws.maps:
        grid = ws.maps[av.current_map]["grid"]
        items_source = ws.maps[av.current_map].get("items", {})
    if map_path:
        try:
            raw = load_raw(map_path)
            _bd = os.path.dirname(os.path.abspath(map_path))
            assets = os.path.join(_bd, "assets")
            loader = TextureLoader(assets if os.path.isdir(assets) else _bd)
            colors = build_colors(raw, loader)
        except Exception:
            pass

    # build entity list
    entities: list[EntityView] = []
    for aid, a in ws.avatars.items():
        if aid == avatar_id:
            continue
        tex = None
        if a.texture_path:
            try:
                _bd = os.path.dirname(os.path.abspath(map_path if map_path else '.'))
                assets = os.path.join(_bd, "assets")
                tl = TextureLoader(assets if os.path.isdir(assets) else _bd)
                ext = os.path.splitext(a.texture_path)[1].lower()
                tex = tl.load_frames(a.texture_path) if ext == ".gif" else tl.load(a.texture_path)
            except Exception:
                pass
        entities.append(EntityView(
            x=a.x, y=a.y, texture=tex, kind="avatar",
            name=a.name, size_3d=150, width_3d=0.2, facing=a.facing,
        ))

    for iid, item in items_source.items():
        tex = None
        if item.texture_path and map_path:
            try:
                _bd = os.path.dirname(os.path.abspath(map_path))
                assets = os.path.join(_bd, "assets")
                tl = TextureLoader(assets if os.path.isdir(assets) else _bd)
                ext = os.path.splitext(item.texture_path)[1].lower()
                if ext == ".gif":
                    tex = tl.load_frames(item.texture_path)
                else:
                    tex = tl.load(item.texture_path)
            except Exception:
                pass
        entities.append(EntityView(
            x=item.x, y=item.y, texture=tex,
            kind=item.kind, name=item.name,
            size_3d=item.size_3d, width_3d=item.width_3d,
            anim=item.anim, occlusion=item.occlusion,
            visible=item.visible, facing=item.facing,
            pickup=item.pickup, pickup_label=item.pickup_label,
            capture_for=item.capture_for, portal_target=item.portal_target,
        ))

    frame = Frame(
        player=PlayerView(x=av.x, y=av.y, angle=av.facing, pitch=0),
        walls=grid,
        entities=entities,
        colors=colors,
        fov=80, ray_count=width // 2,
        fog=FogConfig(enabled=True),
    )

    surface = pygame.Surface((width, height))
    render(frame, surface)

    import io
    buf = io.BytesIO()
    pygame.image.save(surface, buf, "PNG")
    return buf.getvalue()
