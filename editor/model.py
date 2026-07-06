"""GhostEngine Map Editor — data model and undo commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from PySide6.QtGui import QUndoCommand

import numpy as np


@dataclass
class EditorState:
    """Mutable state for the map editor."""
    grid: np.ndarray = field(default_factory=lambda: np.zeros((15, 15), dtype=int))
    current_tool: str = "select"
    entities: list[dict] = field(default_factory=list)
    player_spawn: tuple[float, float, float] = (7.5, 7.5, 0.0)
    selected_spawn_angle: float = 0.0
    portal_config: dict = field(default_factory=lambda: {"transition_text": "", "transition_duration": 3.0, "transition_text_size": 36, "transition_text_color": [255, 255, 255]})
    minimap: dict = field(default_factory=lambda: {"mode": "always", "duration": 0})
    test: dict = field(default_factory=lambda: {"g_enabled": False})
    colors: dict[str, Any] = field(default_factory=lambda: {
        "sky_top": [135, 206, 235],
        "sky_bottom": [240, 248, 255],
        "floor": [34, 139, 34],
        "walls": {
            "1": {"color": [100, 100, 150]},
            "2": {"color": [50, 200, 100]},
            "3": {"color": [139, 69, 19]},
            "4": {"color": [70, 130, 180]},
            "5": {"color": [150, 50, 50]},
            "6": {"color": [50, 150, 150]},
            "7": {"color": [160, 140, 60]},
            "8": {"color": [60, 60, 60]},
        },
    })
    selected_wall_type: int = 1
    selected_entity_idx: int = -1
    project_dir: str = "."
    map_path: str | None = None
    modified: bool = False


class CmdWall(QUndoCommand):
    def __init__(self, state: EditorState, x: int, y: int, old: int, new: int):
        super().__init__("放置墙壁")
        self.state = state
        self.x = x
        self.y = y
        self.old = old
        self.new = new

    def undo(self):
        self.state.grid[self.x, self.y] = self.old
        self.state.modified = True

    def redo(self):
        self.state.grid[self.x, self.y] = self.new
        self.state.modified = True


class CmdEntity(QUndoCommand):
    def __init__(self, state: EditorState, idx: int, old_data: dict | None, new_data: dict | None):
        super().__init__("放置实体")
        self.state = state
        self.idx = idx
        self.old = old_data
        self.new = new_data

    def undo(self):
        if self.old is None:
            if 0 <= self.idx < len(self.state.entities):
                self.state.entities.pop(self.idx)
        else:
            if self.idx < len(self.state.entities):
                self.state.entities[self.idx] = self.old
            else:
                self.state.entities.append(self.old)
        self.state.modified = True

    def redo(self):
        if self.new is None:
            if 0 <= self.idx < len(self.state.entities):
                self.state.entities.pop(self.idx)
        else:
            if self.idx < len(self.state.entities):
                self.state.entities[self.idx] = self.new
            else:
                self.state.entities.append(self.new)
        self.state.modified = True


class CmdSpawn(QUndoCommand):
    def __init__(self, state: EditorState, old: tuple, new: tuple):
        super().__init__("移动出生点")
        self.state = state
        self.old = old
        self.new = new

    def undo(self):
        self.state.player_spawn = self.old
        self.state.modified = True

    def redo(self):
        self.state.player_spawn = self.new
        self.state.modified = True


class CmdWallColor(QUndoCommand):
    def __init__(self, state: EditorState, wall_type: int, old: dict | None, new: dict | None):
        super().__init__("修改墙壁颜色")
        self.state = state
        self.wt = str(wall_type)
        self.old = old  # deep copy of the wall dict entry
        self.new = new

    def undo(self):
        ws = self.state.colors.setdefault("walls", {})
        if self.old is None:
            ws.pop(self.wt, None)
        else:
            ws[self.wt] = self.old
        self.state.modified = True

    def redo(self):
        ws = self.state.colors.setdefault("walls", {})
        if self.new is None:
            ws.pop(self.wt, None)
        else:
            ws[self.wt] = self.new
        self.state.modified = True


class CmdWallTex(CmdWallColor):
    def __init__(self, state: EditorState, wall_type: int, old: dict | None, new: dict | None):
        super().__init__(state, wall_type, old, new)
        self.setText("修改墙壁贴图")



class CmdSceneColor(QUndoCommand):
    def __init__(self, state: EditorState, old: dict, new: dict):
        super().__init__("修改场景颜色")
        self.state = state
        self.old = dict(old)
        self.new = dict(new)

    def undo(self):
        self.state.colors.update(self.old)
        self.state.modified = True

    def redo(self):
        self.state.colors.update(self.new)
        self.state.modified = True

class CmdEntityProps(QUndoCommand):
    def __init__(self, state: EditorState, idx: int, old: dict | None, new: dict | None):
        super().__init__("修改实体属性")
        self.state = state
        self.idx = idx
        self.old = old
        self.new = new

    def undo(self):
        if 0 <= self.idx < len(self.state.entities) and self.old is not None:
            self.state.entities[self.idx] = dict(self.old)
            self.state.modified = True

    def redo(self):
        if 0 <= self.idx < len(self.state.entities) and self.new is not None:
            self.state.entities[self.idx] = dict(self.new)
            self.state.modified = True


# ═══════════════════════════════════════════════════════════════════
# Portal pairing helpers
# ═══════════════════════════════════════════════════════════════════

def generate_portal_id(entities: list[dict]) -> str:
    """Return the next available portal_N id."""
    existing = {e["id"] for e in entities if e.get("kind") == "portal" and e.get("id", "").startswith("portal_")}
    n = 0
    while f"portal_{n}" in existing:
        n += 1
    return f"portal_{n}"


def list_project_maps(project_dir: str) -> list[str]:
    """Return absolute paths of all .json map files in project_dir (excluding presets.json)."""
    import os
    if not os.path.isdir(project_dir):
        return []
    maps = []
    for f in sorted(os.listdir(project_dir)):
        if f.endswith(".json") and f != "presets.json":
            maps.append(os.path.join(project_dir, f))
    return maps


def load_map_portals(map_path: str) -> list[dict]:
    """Load a map JSON and return only its portal entities."""
    import json, os
    if not os.path.isfile(map_path):
        return []
    try:
        with open(map_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    portals = []
    for e in data.get("entities", []):
        if e.get("kind") == "portal":
            portals.append(e)
    return portals


def collect_all_portal_targets(project_dir: str) -> set[tuple[str, str]]:
    """Return set of (portal_id, map_basename) that are targeted by any portal across all maps."""
    import json, os
    targeted: set[tuple[str, str]] = set()
    for map_path in list_project_maps(project_dir):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for e in data.get("entities", []):
            pt = e.get("portal_target")
            if pt and isinstance(pt, dict) and pt.get("portal_id"):
                targeted.add((pt["portal_id"], pt.get("map", "")))
    return targeted


def get_unpaired_portals(target_map_path: str, project_dir: str, exclude_id: str = "") -> list[dict]:
    """Return portals on target_map_path that are NOT targeted by any other portal.
    Optionally exclude a portal by id (to prevent self-targeting)."""
    import os
    portals = load_map_portals(target_map_path)
    if not portals:
        return []
    targeted = collect_all_portal_targets(project_dir)
    map_basename = os.path.basename(target_map_path)
    unpaired = []
    for p in portals:
        pid = p.get("id", "")
        if pid == exclude_id:
            continue
        if (pid, map_basename) not in targeted:
            unpaired.append(p)
    return unpaired



def break_all_references_to_portal(project_dir: str, portal_id: str, map_basename: str) -> None:
    """Clear portal_target of any portal (across all maps) that targets *portal_id*.
    Saves modified map files to disk. Also clears in-memory current-map entities if provided."""
    import json, os
    changed: set[str] = set()
    maps_data: dict[str, dict] = {}
    for mp in list_project_maps(project_dir):
        try:
            with open(mp, "r", encoding="utf-8") as f:
                maps_data[mp] = json.load(f)
        except Exception:
            continue
    for mp, data in maps_data.items():
        for e in data.get("entities", []):
            if e.get("kind") != "portal":
                continue
            pt = e.get("portal_target")
            if not pt or not isinstance(pt, dict):
                continue
            if pt.get("portal_id") != portal_id:
                continue
            if pt.get("map", "") not in ("", map_basename):
                continue
            e["portal_target"] = None
            changed.add(mp)
    for mp in changed:
        try:
            with open(mp, "w", encoding="utf-8") as f:
                json.dump(maps_data[mp], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def auto_pair_portals(project_dir: str) -> None:
    """For every portal with a target, ensure the target portal points back.
    If the target was previously paired with someone else, break that old pairing.
    Saves modified map files to disk."""
    import json, os
    maps_data: dict[str, dict] = {}
    for mp in list_project_maps(project_dir):
        try:
            with open(mp, "r", encoding="utf-8") as f:
                maps_data[mp] = json.load(f)
        except Exception:
            continue

    changed_maps: set[str] = set()

    for mp, data in maps_data.items():
        my_basename = os.path.basename(mp)
        for e in data.get("entities", []):
            if e.get("kind") != "portal":
                continue
            pt = e.get("portal_target")
            if not pt or not isinstance(pt, dict) or not pt.get("portal_id"):
                continue
            if not e.get("id"):
                continue
            target_id = pt["portal_id"]
            target_map_name = pt.get("map", "")
            # Find target map file
            target_mp = None
            for t_mp in maps_data:
                if os.path.basename(t_mp) == target_map_name:
                    target_mp = t_mp
                    break
            if target_mp is None:
                continue
            target_data = maps_data[target_mp]
            # Find target portal and set its target back to me
            for te in target_data.get("entities", []):
                if te.get("kind") != "portal":
                    continue
                if te.get("id") != target_id:
                    continue
                # Check if already paired correctly
                tpt = te.get("portal_target") or {}
                if tpt.get("portal_id") == e.get("id") and tpt.get("map") == my_basename:
                    continue  # already paired
                # Break old pairing: find whoever previously targeted this portal
                old_targeter_id = tpt.get("portal_id", "")
                old_targeter_map = tpt.get("map", "")
                if old_targeter_id:
                    for omp, odata in maps_data.items():
                        if os.path.basename(omp) == old_targeter_map:
                            for oe in odata.get("entities", []):
                                if oe.get("id") == old_targeter_id:
                                    oe["portal_target"] = None
                                    changed_maps.add(omp)
                            break
                # Set target portal's target to me
                te["portal_target"] = {"portal_id": e.get("id", ""), "map": my_basename}
                changed_maps.add(target_mp)
                break

    # Save changed maps
    for mp in changed_maps:
        try:
            with open(mp, "w", encoding="utf-8") as f:
                json.dump(maps_data[mp], f, indent=2, ensure_ascii=False)
        except Exception:
            pass
