"""Metaverse world state — authoritative server-side data model."""
from __future__ import annotations
from dataclasses import dataclass, field
from heapq import heappush, heappop
from typing import Any

import numpy as np


@dataclass
class Avatar:
    """An online entity controlled by a human or agent."""
    name: str
    x: float = 0.0
    y: float = 0.0
    facing: float = 0.0
    owner: str = ""          # "human" | agent_id
    online: bool = True
    goto_path: list | None = None   # waypoints for auto-navigation
    goto_done: bool = False        # set True when goto completes
    texture_path: str = ""
    current_map: str = ""
    home_map: str = ""              # map this avatar spawned on
    remote_map: str = ""             # cross-map: avatar is on a different map
    remote_pos: tuple[float, float] | None = None  # position on remote map
    last_portal_id: str = ""          # last triggered portal id (edge-trigger)
    track_target: str = ""            # avatar/item id to track (face towards)

@dataclass
class Item:
    """An item on the ground or in an inventory."""
    id: str
    x: float = 0.0
    y: float = 0.0
    texture_path: str = ""
    texture_paths: dict[str, str] | None = None
    kind: str = "item"              # "item" | "portal"
    pickup: bool = False
    pickup_label: str = ""
    capture_for: str = ""           # ""=public, "name"=directed, "*"=any
    portal_target: dict[str, Any] | None = None
    anim: dict[str, Any] = field(default_factory=dict)
    size_3d: float = 150.0
    width_3d: float = 0.2
    occlusion: str = "center"
    visible: bool = True
    facing: float = 0.0
    name: str = ""
    owner: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class WorldState:
    """Authoritative world state for one or more maps."""

    def __init__(self, map_path: str = "", data: dict | None = None):
        self.map_path = map_path
        self.grid: np.ndarray = np.zeros((1, 1), dtype=int)
        self.items: dict[str, Item] = {}
        self.avatars: dict[str, Avatar] = {}
        self.inventories: dict[str, list[Item]] = {}
        self.colors: dict = {}
        self.spawn_points: list[dict] = []
        self.chat_log: list[dict] = []
        self.tick: int = 0
        self.maps: dict[str, dict] = {}
        if map_path:
            import json
            with open(map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if data:
            self._load(data)
        self._preload_maps()

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        return cls(data=data)


    def _preload_maps(self):
        import os, json as _json
        if not self.map_path:
            return
        d = os.path.dirname(os.path.abspath(self.map_path))
        if not os.path.isdir(d):
            return
        for f in os.listdir(d):
            if not f.endswith(".json") or f == os.path.basename(self.map_path) or f == "presets.json":
                continue
            self._load_map_file(os.path.join(d, f))
        # also add the main map itself
        self._load_map_file(self.map_path)

    def _load_map_file(self, path: str):
        import os, json as _json, numpy as _np
        try:
            with open(path, "r", encoding="utf-8") as fh:
                mdata = _json.load(fh)
            name = os.path.basename(path)
            grid = _np.array(mdata.get("grid", [[0]]), dtype=int).T
            citems = {}
            for i, e in enumerate(mdata.get("entities", [])):
                eid = e.get("id") or e.get("name") or f"{e.get('kind', 'entity')}_{i}"
                item = Item(id=eid, x=e["x"], y=e["y"],
                    texture_path=e.get("texture",""), kind=e.get("kind","item"),
                    pickup=e.get("pickup",False), pickup_label=e.get("pickup_label",""),
                    capture_for=e.get("capture_for",""), portal_target=e.get("portal_target"),
                    size_3d=e.get("size_3d",150), name=e.get("name",""))
                citems[item.id] = item
            self.maps[name] = {"grid": grid, "colors": mdata.get("colors", {}),
                "spawn_points": [mdata.get("player_spawn", {"x":1.5,"y":1.5,"angle":0})],
                "items": citems}
        except Exception as e:
            import traceback
            print(f"[world] FAILED loading {path}: {e}")
            traceback.print_exc()

    def load_map(self, path: str) -> bool:
        """Load a new map, preserving avatars and inventories. Returns True on success."""
        import json, os
        if not os.path.isfile(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.map_path = path
        self._load(data)
        return True
    def _load(self, data: dict):
        self.grid = np.array(data.get("grid", [[0]]), dtype=int).T
        self.colors = data.get("colors", {})
        ps = data.get("player_spawn", {"x": 1.5, "y": 1.5, "angle": 0})
        self.spawn_points = [ps]
        for i, e in enumerate(data.get("entities", [])):
            eid = e.get("id") or e.get("name") or f"{e.get('kind', 'entity')}_{i}"
            item = Item(
                id=eid,
                x=e["x"], y=e["y"],
                texture_path=e.get("texture", ""),
                texture_paths=e.get("textures"),
                kind=e.get("kind", "item"),
                pickup=e.get("pickup", False),
                pickup_label=e.get("pickup_label", ""),
                capture_for=e.get("capture_for", ""),
                portal_target=e.get("portal_target"),
                anim=e.get("anim", {}),
                size_3d=e.get("size_3d", 150),
                width_3d=e.get("width_3d", 0.2),
                occlusion=e.get("occlusion", "center"),
                visible=not e.get("invisible", False),
                facing=e.get("facing", 0.0),
                name=e.get("name", ""),
                owner=e.get("owner", ""),
                metadata=e.get("metadata", {}),
            )
            self.items[item.id] = item
        # Validate and clean up ghost entities
        from ghostengine.mapfile import validate_entities_on_walls
        errors = validate_entities_on_walls(self.grid, data.get("entities", []), data.get("player_spawn"))
        gw, gh = self.grid.shape
        stale = [iid for iid, item in self.items.items()
                 if int(item.x) < 0 or int(item.x) >= gw or int(item.y) < 0 or int(item.y) >= gh]
        for iid in stale:
            del self.items[iid]
            print(f"[world] 🧹 removed out-of-bounds entity: {iid}")
        for err in errors:
            print(f"[world] ⚠ {err}")
    def save_state(self, path: str):
        """Persist runtime state (grid, items, inventories, avatar positions) to JSON."""
        import json
        data = {
            "map": self.map_path,
            "grid": self.grid.tolist(),
            "items": {},
            "inventories": {},
            "avatar_states": {},
        }
        for iid, item in self.items.items():
            data["items"][iid] = {
                "id": item.id, "x": item.x, "y": item.y,
                "texture_path": item.texture_path,
                "texture_paths": item.texture_paths,
                "kind": item.kind,
                "pickup": item.pickup, "pickup_label": item.pickup_label,
                "capture_for": item.capture_for,
                "portal_target": item.portal_target,
                "anim": item.anim, "size_3d": item.size_3d,
                "width_3d": item.width_3d, "occlusion": item.occlusion,
                "visible": item.visible, "facing": item.facing,
                "name": item.name, "owner": item.owner,
                "metadata": item.metadata,
            }
        for name, inv in self.inventories.items():
            data["inventories"][name] = [{
                "id": i.id, "texture_path": i.texture_path,
                "kind": i.kind, "pickup_label": i.pickup_label,
                "name": i.name, "metadata": i.metadata,
            } for i in inv]
        for name, av in self.avatars.items():
            data["avatar_states"][name] = {
                "x": av.x, "y": av.y, "facing": av.facing,
                "owner": av.owner, "online": av.online,
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """Restore runtime state from JSON. Merges with existing template items."""
        import json, os
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # restore grid — validate shape matches current map
        if "grid" in data:
            new_grid = np.array(data["grid"], dtype=int)
            if new_grid.shape == self.grid.shape:
                self.grid = new_grid
            else:
                print(f"[world] state grid shape {new_grid.shape} != expected {self.grid.shape}, ignoring")
        # sync restored grid to current map so try_move sees edits
        map_name = os.path.basename(self.map_path)
        if map_name in self.maps:
            self.maps[map_name]["grid"] = self.grid.copy()
        # restore items
        for iid, d in data.get("items", {}).items():
            item = Item(
                id=d.get("id", iid), x=d.get("x", 0), y=d.get("y", 0),
                texture_path=d.get("texture_path", ""),
                texture_paths=d.get("texture_paths"),
                kind=d.get("kind", "item"),
                pickup=d.get("pickup", False),
                pickup_label=d.get("pickup_label", ""),
                capture_for=d.get("capture_for", ""),
                portal_target=d.get("portal_target"),
                anim=d.get("anim", {}),
                size_3d=d.get("size_3d", 150),
                width_3d=d.get("width_3d", 0.2),
                occlusion=d.get("occlusion", "center"),
                visible=d.get("visible", True),
                facing=d.get("facing", 0),
                name=d.get("name", ""),
                owner=d.get("owner", ""),
                metadata=d.get("metadata", {}),
            )
            self.items[item.id] = item
        # restore inventories
        for name, inv in data.get("inventories", {}).items():
            self.inventories[name] = []
            for d in inv:
                self.inventories[name].append(Item(
                    id=d.get("id", ""), texture_path=d.get("texture_path", ""),
                    kind=d.get("kind", "item"),
                    pickup_label=d.get("pickup_label", ""),
                    name=d.get("name", ""), metadata=d.get("metadata", {}),
                ))
        # restore avatar positions
        for name, d in data.get("avatar_states", {}).items():
            self.avatars[name] = Avatar(
                name=name, x=d.get("x", 0), y=d.get("y", 0),
                facing=d.get("facing", 0), owner=d.get("owner", ""),
                online=False,
            )

    # ── Items ──

    def add_item(self, item: Item):
        self.items[item.id] = item

    def remove_item(self, item_id: str):
        self.items.pop(item_id, None)

    def check_pickups(self, avatar_id: str, pickup_radius: float = 1.0, item_id: str = "") -> list[Item]:
        return self._check_pickups_from(avatar_id, self.items, pickup_radius, item_id)

    def _check_pickups_from(self, avatar_id: str, items_dict: dict[str, Item],
                            pickup_radius: float = 1.0, item_id: str = "") -> list[Item]:
        """Check pickups from a specific items dict (for cross-map support).
        If item_id is non-empty, only pick up that specific item."""
        av = self.avatars.get(avatar_id)
        if not av: return []
        picked = []
        to_remove = []
        for iid, item in list(items_dict.items()):
            if not item.pickup: continue
            if item_id and iid != item_id: continue
            dist = ((av.x - item.x) ** 2 + (av.y - item.y) ** 2) ** 0.5
            if dist < pickup_radius:
                if not item.capture_for or item.capture_for in ("*", av.name, av.owner):
                    picked.append(item)
                    to_remove.append(iid)
        for iid in to_remove:
            inv = self.inventories.setdefault(avatar_id, [])
            inv.append(items_dict.pop(iid))
        return picked

    def place_item(self, avatar_id: str, item_id: str, x: float, y: float):
        inv = self.inventories.get(avatar_id, [])
        for i, item in enumerate(inv):
            if item.id == item_id:
                item.x = x
                item.y = y
                item.owner = ""
                self.items[item_id] = inv.pop(i)
                return

    # ── Avatars ──

    def ensure_avatar(self, name: str, x: float = 0, y: float = 0,
                      facing: float = 0, owner: str = "", texture_path: str = ""):
        if name in self.avatars:
            av = self.avatars[name]
            av.x = x; av.y = y; av.facing = facing; av.owner = owner
            if texture_path: av.texture_path = texture_path
        else:
            self.avatars[name] = Avatar(name=name, x=x, y=y, facing=facing, owner=owner, texture_path=texture_path)

    def remove_avatar(self, name: str):
        self.avatars.pop(name, None)

    # ── Collision ──

    def is_passable(self, x: float, y: float) -> bool:
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.grid.shape[0] or iy >= self.grid.shape[1]:
            return False
        return self.grid[ix, iy] == 0

    def try_move(self, avatar_id: str, nx: float, ny: float) -> tuple[float, float] | None:
        """Attempt to move avatar to (nx, ny). Returns new position if valid, None if blocked."""
        av = self.avatars.get(avatar_id)
        if not av: return None
        grid = self.maps[av.current_map]["grid"] if av.current_map and av.current_map in self.maps else self.grid
        ix, iy = int(nx), int(ny)
        if 0 <= ix < grid.shape[0] and 0 <= iy < grid.shape[1] and grid[ix, iy] == 0:
            av.x = nx; av.y = ny
            return (nx, ny)
        return None

    # ── Pathfinding ──

    def pathfind(self, sx: float, sy: float, tx: float, ty: float, grid=None) -> list[tuple[float, float]]:
        g = grid if grid is not None else self.grid
        """A* from (sx, sy) to (tx, ty). Returns waypoints as [(x, y), ...]."""
        sx_i, sy_i = int(sx), int(sy)
        tx_i, ty_i = int(tx), int(ty)
        if sx_i == tx_i and sy_i == ty_i:
            return [(tx, ty)]
        if not (0 <= tx_i < g.shape[0] and 0 <= ty_i < g.shape[1] and g[tx_i, ty_i] == 0):
            return []
        h, w = g.shape
        def neighbors(x, y):
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                bx, by = x + dx, y + dy
                if 0 <= bx < h and 0 <= by < w and g[bx, by] == 0:
                    yield bx, by
        open_set = [(0, 0, sx_i, sy_i, None)]
        came_from = {}
        g_score = {(sx_i, sy_i): 0}
        while open_set:
            _, score, cx, cy, prev = heappop(open_set)
            if (cx, cy) in came_from: continue
            came_from[(cx, cy)] = prev
            if cx == tx_i and cy == ty_i:
                path: list[tuple[float, float]] = []
                cur = (cx, cy)
                while came_from.get(cur):
                    px, py = cur
                    path.append((px + 0.5, py + 0.5))
                    cur = came_from[cur]
                path.reverse()
                if not path or path[-1] != (tx, ty):
                    path.append((tx, ty))
                return path
            for nx, ny in neighbors(cx, cy):
                nscore = score + 1
                if (nx, ny) not in g_score or nscore < g_score[(nx, ny)]:
                    g_score[(nx, ny)] = nscore
                    f = nscore + abs(nx - tx_i) + abs(ny - ty_i)
                    heappush(open_set, (f, nscore, nx, ny, (cx, cy)))
        return []

    # ── Portal ──

    def _nearest_passable(self, x: float, y: float) -> tuple[float, float] | None:
        """Find the nearest passable cell to (x, y), spiraling outward.
        Returns (cx+0.5, cy+0.5) or None if the whole grid is walls."""
        ix, iy = int(x), int(y)
        h, w = self.grid.shape
        if 0 <= ix < h and 0 <= iy < w and self.grid[ix, iy] == 0:
            return (x, y)
        for radius in range(1, max(h, w)):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    nx, ny = ix + dx, iy + dy
                    if 0 <= nx < h and 0 <= ny < w and self.grid[nx, ny] == 0:
                        return (nx + 0.5, ny + 0.5)
        return None

    def check_portal(self, avatar_id: str, trigger_radius: float = 1.0) -> dict | None:
        av = self.avatars.get(avatar_id)
        if not av: return None
        for item in self.items.values():
            if item.kind != "portal" or item.portal_target is None: continue
            dist = ((av.x - item.x) ** 2 + (av.y - item.y) ** 2) ** 0.5
            if dist < trigger_radius:
                return item.portal_target
        return None
