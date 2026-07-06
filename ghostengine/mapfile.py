"""Map file I/O — JSON serialisation for the GhostEngine map format.

This is an *optional* submodule.  The core renderer never imports it.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .frame import ColorConfig, EntityView, WallDef


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def load_raw(path: str) -> dict:
    """Read a map ``.json`` file, run migrations, return raw dict."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _migrate(data)


def save_raw(data: dict, path: str) -> None:
    """Write *data* to *path* as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
def _migrate(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    v = data.get("version", 0)
    if v == 0:
        data["version"] = 1
        v = 1
    if v == 1:
        _v1_to_v2(data)
        data["version"] = 2
        v = 2
    if v == 2:
        _v2_to_v3(data)
        data["version"] = 3
        v = 3
    return data


def _v1_to_v2(data: dict) -> None:
    """Migrate v1 'exit' field to v2 portal entity."""
    ex = data.pop("exit", None)
    if ex and isinstance(ex, dict):
        portal_ent = {
            "x": float(ex.get("x", 0)) + 0.5,
            "y": float(ex.get("y", 0)) + 0.5,
            "kind": "portal",
            "portal_target": {
                "x": float(ex.get("x", 0)) + 0.5,
                "y": float(ex.get("y", 0)) + 0.5,
            },
            "size_3d": 150, "width_3d": 0.2, "occlusion": "center",
        }
        if ex.get("target_map"):
            portal_ent["portal_target"]["map"] = ex["target_map"]
        entities = data.setdefault("entities", [])
        entities.append(portal_ent)


def _v2_to_v3(data: dict) -> None:
    """Migrate v2 to v3: assign portal ids, convert coordinate targets to null."""
    portal_idx = 0
    for e in data.get("entities", []):
        if e.get("kind") != "portal":
            continue
        # Assign id if missing
        if not e.get("id"):
            while any(oe.get("id") == f"portal_{portal_idx}" for oe in data.get("entities", [])):
                portal_idx += 1
            e["id"] = f"portal_{portal_idx}"
            portal_idx += 1
        # Convert coordinate-based portal_target to null (requires re-pairing)
        pt = e.get("portal_target")
        if pt and isinstance(pt, dict) and "x" in pt and "y" in pt and not pt.get("portal_id"):
            e["portal_target"] = None


# ═══════════════════════════════════════════════════════════════════
# Higher-level helpers (for frontends)
# ═══════════════════════════════════════════════════════════════════

def build_colors(raw: dict, texture_loader=None) -> ColorConfig:
    """Convert the ``"colors"`` section of a map dict into a :class:`ColorConfig`."""
    c = raw.get("colors", {})

    walls: dict[int, WallDef] = {}
    raw_walls = c.get("walls", {})
    for k_str, v in raw_walls.items():
        wall_type = int(k_str)
        color = tuple(v.get("color")) if "color" in v else None
        tex = None
        tex_path = v.get("texture")
        if tex_path and texture_loader is not None:
            tex = texture_loader.load(tex_path)
        walls[wall_type] = WallDef(color=color, texture=tex)

    return ColorConfig(
        sky_top=tuple(c.get("sky_top", (135, 206, 235))),
        sky_bottom=tuple(c.get("sky_bottom", (240, 248, 255))),
        floor=tuple(c.get("floor", (34, 139, 34))),
        walls=walls,
    )


def build_entities(raw: dict, texture_loader=None) -> list[EntityView]:
    """Convert the ``"entities"`` section into :class:`EntityView` list."""
    result: list[EntityView] = []
    for e in raw.get("entities", []):
        tex_path = e.get("texture", "")
        tex = None
        if tex_path and texture_loader is not None:
            ext = os.path.splitext(tex_path)[1].lower()
            if ext == ".gif":
                tex = texture_loader.load_frames(tex_path)
            else:
                tex = texture_loader.load(tex_path)
        texs = None
        raw_texs = e.get("textures")
        if raw_texs and texture_loader is not None:
            texs = {}
            for d, tp in raw_texs.items():
                if tp:
                    ext = os.path.splitext(tp)[1].lower()
                    if ext == ".gif":
                        texs[d] = texture_loader.load_frames(tp)
                    else:
                        texs[d] = texture_loader.load(tp)

        result.append(EntityView(
            x=e["x"],
            y=e["y"],
            texture=tex,
            texture_path=tex_path,
            textures=texs,
            texture_paths=raw_texs,
            facing=e.get("facing", 0.0),
            kind=e.get("kind", "item"),
            size_3d=e.get("size_3d", 150),
            width_3d=e.get("width_3d", 0.2),
            anim=e.get("anim", {}),
            occlusion=e.get("occlusion", "center"),
            visible=not e.get("invisible", False),
            mm_trigger=e.get("mm_trigger", False),
            pickup=e.get("pickup", False),
            pickup_label=e.get("pickup_label", ""),
            capture_for=e.get("capture_for", ""),
            portal_target=e.get("portal_target"),
            name=e.get("name", ""),
            owner=e.get("owner", ""),
            metadata=e.get("metadata", {}),
        ))
    return result


def validate_entities_on_walls(grid, entities, player_spawn=None) -> list[str]:
    """Check for entities on walls or out of bounds. Returns list of error messages."""
    import numpy as np
    errors: list[str] = []
    g = np.asarray(grid, dtype=int)
    gw, gh = g.shape
    for ent in entities:
        x, y = ent.get("x", 0), ent.get("y", 0)
        ix, iy = int(x), int(y)
        kind = ent.get("kind", "entity")
        eid = ent.get("id", ent.get("name", "?"))
        if ix < 0 or iy < 0 or ix >= gw or iy >= gh:
            errors.append(f"{kind} '{eid}' at ({x:.1f},{y:.1f}) is OUTSIDE grid ({gw}x{gh})")
        elif g[ix, iy] != 0:
            errors.append(f"{kind} '{eid}' at ({x:.1f},{y:.1f}) overlaps wall cell [{ix},{iy}] (type={g[ix,iy]})")
    if player_spawn:
        sx, sy = int(player_spawn.get("x", 0)), int(player_spawn.get("y", 0))
        if 0 <= sx < gw and 0 <= sy < gh and g[sx, sy] != 0:
            errors.append(f"player spawn at ({player_spawn.get('x')},{player_spawn.get('y')}) overlaps wall cell [{sx},{sy}]")
    return errors
