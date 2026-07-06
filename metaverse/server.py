"""Metaverse server — authoritative world host (same-process, NO NETWORK).

CRITICAL: This project MUST NOT use WebSocket, MCP, or async networking.
All modules share WorldState via direct function calls.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import time




from .world import WorldState


_current_ws: WorldState | None = None
_current_ctx: ServerContext | None = None

def handle_message(ws: WorldState, avatar_id: str, msg: dict) -> dict:
    """Process a single message from an avatar. Returns a response dict."""
    msg_type = msg.get("type", "")

    if msg_type == "connect":
        sp = ws.spawn_points[0] if ws.spawn_points else {"x": 1.5, "y": 1.5, "angle": 0}
        ws.ensure_avatar(avatar_id, x=sp["x"], y=sp["y"], facing=sp.get("angle", 0), owner=msg.get("owner", "agent"), texture_path=msg.get("texture", ""))
        ws.avatars[avatar_id].home_map = os.path.basename(ws.map_path)
        ws.avatars[avatar_id].current_map = os.path.basename(ws.map_path)
        return {"type": "connected", "avatar": avatar_id, "x": sp["x"], "y": sp["y"], "facing": sp.get("angle", 0)}

    if msg_type == "disconnect":
        ws.remove_avatar(avatar_id)
        return {"type": "disconnected", "avatar": avatar_id}

    if msg_type == "move":
        nx, ny = msg.get("x", 0), msg.get("y", 0)
        facing = msg.get("facing", 0)
        av = ws.avatars.get(avatar_id)
        if av: av.goto_path = None
        result = ws.try_move(avatar_id, nx, ny)
        if result is not None:
            ws.avatars[avatar_id].facing = facing
            return {"type": "moved", "x": result[0], "y": result[1], "facing": facing}
        return {"type": "blocked", "x": nx, "y": ny}

    if msg_type == "turn":
        facing = msg.get("facing", 0)
        av = ws.avatars.get(avatar_id)
        if av:
            av.facing = facing
        return {"type": "turned", "facing": facing}

    if msg_type == "say":
        message = msg.get("message", "")
        channel = msg.get("channel", "local")
        av = ws.avatars.get(avatar_id)
        sp = {"x": av.x, "y": av.y} if av else {"x": 0, "y": 0}
        ws.chat_log.append({"from": avatar_id, "message": message, "channel": channel, "tick": ws.tick, "time": time.time(), "pos": sp})
        if len(ws.chat_log) > 50:
            ws.chat_log = ws.chat_log[-50:]
        return {"type": "said", "from": avatar_id, "message": message, "channel": channel}

    if msg_type == "pickup":
        target_id = msg.get("item_id", "")
        px = msg.get("x")
        py = msg.get("y")
        if px is None or py is None:
            return {"type": "error", "reason": "pickup requires x and y coordinates"}
        av = ws.avatars.get(avatar_id)
        items_source = ws.items
        if av and av.current_map and av.current_map in ws.maps:
            items_source = ws.maps[av.current_map]["items"]
        orig_x, orig_y = av.x, av.y
        av.x, av.y = float(px), float(py)
        try:
            picked = ws._check_pickups_from(avatar_id, items_source, 1.0, target_id)
        finally:
            av.x, av.y = orig_x, orig_y
        if picked:
            ws.items.pop(picked[0].id, None)
            return {"type": "picked_up", "item_id": picked[0].id, "label": picked[0].pickup_label}
        return {"type": "nothing_to_pickup"}

    if msg_type == "place":
        item_id = msg.get("item_id", "")
        x = msg.get("x", 0)
        y = msg.get("y", 0)
        ws.place_item(avatar_id, item_id, x, y)
        return {"type": "placed", "item_id": item_id, "x": x, "y": y}

    if msg_type == "give":
        target = msg.get("target", "")
        item_id = msg.get("item_id", "")
        inv = ws.inventories.get(avatar_id, [])
        for i, item in enumerate(inv):
            if item.id == item_id:
                item.owner = ""
                item.capture_for = target  # only target can pick up
                item.pickup = True
                item.x = ws.avatars[avatar_id].x
                item.y = ws.avatars[avatar_id].y
                item.pickup_label = item.pickup_label or item.id
                ws.items[item_id] = inv.pop(i)
                return {"type": "given", "item_id": item_id, "to": target}
        return {"type": "give_failed", "reason": "item not in inventory"}

    if msg_type == "goto":
        tx, ty = msg.get("x", 0), msg.get("y", 0)
        av = ws.avatars.get(avatar_id)
        if av:
            g = ws.maps[av.current_map]["grid"] if av.current_map and av.current_map in ws.maps else ws.grid
            path = ws.pathfind(av.x, av.y, tx, ty, g)
            if path:
                av.goto_path = path
                return {"type": "navigating", "waypoints": path, "target": (tx, ty)}
            return {"type": "unreachable", "target": (tx, ty)}
        return {"type": "error", "reason": "avatar not found"}


    if msg_type == "track":
        av = ws.avatars.get(avatar_id)
        if not av:
            return {"type": "error", "reason": "avatar not found"}
        av.track_target = msg.get("target", "")
        target = ws.avatars.get(av.track_target) or ws.items.get(av.track_target)
        if target:
            av.facing = math.atan2(target.y - av.y, target.x - av.x)
        return {"type": "tracking", "target": av.track_target}

    if msg_type == "untrack":
        av = ws.avatars.get(avatar_id)
        if av:
            av.track_target = ""
        return {"type": "untracked"}
    if msg_type == "look":
        av = ws.avatars.get(avatar_id)
        if not av:
            return {"type": "error", "reason": "avatar not found"}
        nearby = []
        all_items = []
        for item in ws.items.values():
            dist = ((av.x - item.x) ** 2 + (av.y - item.y) ** 2) ** 0.5
            info = {"id": item.id, "name": item.name, "kind": item.kind,
                    "x": item.x, "y": item.y, "distance": dist,
                    "pickup": item.pickup, "capture_for": item.capture_for,
                    "metadata": item.metadata}
            all_items.append(info)
            if dist <= 5.0:
                nearby.append(info)
        other_avs = []
        for aid, a in ws.avatars.items():
            if aid != avatar_id:
                oa = {"name": a.name, "x": a.x, "y": a.y, "facing": a.facing}
                other_avs.append(oa)
        gx, gy = int(av.x), int(av.y)
        grid_slice = []
        for dx in range(-2, 3):
            row = []
            for dy in range(-2, 3):
                ix, iy = gx + dx, gy + dy
                if ix < 0 or iy < 0 or ix >= ws.grid.shape[0] or iy >= ws.grid.shape[1]:
                    row.append(1)
                else:
                    row.append(int(ws.grid[ix, iy]))
            grid_slice.append(row)
        inv = ws.inventories.get(avatar_id, [])
        return {"type": "perception", "position": [av.x, av.y, av.facing],
                "inventory": [{"id": i.id, "label": i.pickup_label} for i in inv],
                "nearby_items": nearby, "all_items": all_items,
                "avatars": other_avs, "grid_slice": grid_slice}

    if msg_type == "pos":
        av = ws.avatars.get(avatar_id)
        if not av:
            return {"type": "error", "reason": "avatar not found"}
        return {"type": "position", "x": av.x, "y": av.y, "facing": av.facing,
                "map": av.current_map or os.path.basename(ws.map_path)}

    if msg_type == "inv":
        inv = ws.inventories.get(avatar_id, [])
        return {"type": "inventory", "items": [{"id": i.id, "label": i.pickup_label} for i in inv]}

    if msg_type == "snapshot":
        caption = msg.get("caption", "")
        try:
            png_bytes = _take_snapshot(ws, avatar_id)
            snap_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshots")
            os.makedirs(snap_dir, exist_ok=True)
            ts = int(time.time())
            safe_name = "".join(c for c in avatar_id if c.isalnum() or c in "_-")[:20]
            local_path = os.path.join(snap_dir, f"{safe_name}_{ts}.png")
            with open(local_path, "wb") as f:
                f.write(png_bytes)
            return {"type": "snapshot_done", "caption": caption, "local": local_path}
        except Exception as e:
            return {"type": "snapshot_error", "reason": str(e)}

    if msg_type == "post_issue":
        caption = msg.get("caption", "")
        filepath = msg.get("filepath", "")
        if not filepath or not os.path.isfile(filepath):
            return {"type": "post_issue_error", "reason": "file not found"}
        try:
            with open(filepath, "rb") as f:
                png_bytes = f.read()
            issue_url = _post_to_github(avatar_id, caption, png_bytes)
            return {"type": "post_issue_done", "caption": caption, "url": issue_url}
        except Exception as e:
            return {"type": "post_issue_error", "reason": str(e)}

    if msg_type == "edit_map":
        ops = msg.get("operations", [])
        for op in ops:
            op_type = op.get("op", "")
            if op_type == "set_cell":
                x, y, w = op.get("x", 0), op.get("y", 0), op.get("wall", 0)
                if 0 <= x < ws.grid.shape[0] and 0 <= y < ws.grid.shape[1]:
                    ws.grid[x, y] = w
            elif op_type == "set_grid":
                grid = op.get("grid", [])
                ox = op.get("x", 0)
                oy = op.get("y", 0)
                if not grid:
                    continue
                if ox == 0 and oy == 0 and len(grid) == ws.grid.shape[1] and len(grid[0]) == ws.grid.shape[0]:
                    import numpy as np
                    ws.grid = np.array(grid, dtype=int).T  # full replacement
                else:
                    for ri, row in enumerate(grid):
                        for ci, val in enumerate(row):
                            gx, gy = ox + ci, oy + ri
                            if 0 <= gx < ws.grid.shape[0] and 0 <= gy < ws.grid.shape[1]:
                                ws.grid[gx, gy] = int(val)
            elif op_type == "set_color":
                key, rgb = op.get("key", ""), op.get("rgb", [128, 128, 128])
                ws.colors[key] = rgb
            elif op_type == "delete_entity":
                entity_id = op.get("id", "")
                # remove from ws.items and ws.maps (all maps)
                ws.items.pop(entity_id, None)
                for mdata in ws.maps.values():
                    mdata.get("items", {}).pop(entity_id, None)
            elif op_type == "reload_maps":
                # save current items and grid before reload
                saved_items = dict(ws.items)
                saved_grid = ws.grid.copy()
                ws._preload_maps()
                # restore current map state
                ws.items = saved_items
                ws.grid = saved_grid
                # re-sync to maps
                map_name = os.path.basename(ws.map_path)
                if map_name in ws.maps:
                    ws.maps[map_name]["grid"] = ws.grid.copy()
                    for eid, item in ws.items.items():
                        ws.maps[map_name]["items"][eid] = type(item)(**item.__dict__) if hasattr(item, '__dict__') else item
            elif op_type == "set_entity":
                entity_id = op.get("id", "")
                prop = op.get("prop", "")
                value = op.get("value")
                # Find the entity across all maps
                found_map = None
                item = ws.items.get(entity_id)
                if item:
                    found_map = os.path.basename(ws.map_path)
                else:
                    for mname, mdata in ws.maps.items():
                        if entity_id in mdata.get("items", {}):
                            item = mdata["items"][entity_id]
                            found_map = mname
                            break
                if item is None:
                    from metaverse.world import Item
                    item = Item(id=entity_id, x=float(op.get('x', 0)), y=float(op.get('y', 0)),
                                kind=op.get('kind', 'portal'))
                    ws.items[entity_id] = item
                    found_map = os.path.basename(ws.map_path)
                if prop == "portal_target":
                    if isinstance(value, dict) and "map" not in value:
                        tx = value.get("x", item.x); ty = value.get("y", item.y)
                        if abs(tx - item.x) < 0.1 and abs(ty - item.y) < 0.1:
                            continue
                    item.portal_target = value
                elif prop in ("x", "y", "facing", "size_3d", "width_3d"):
                    setattr(item, prop, float(value))
                elif prop in ("name", "owner", "capture_for", "pickup_label", "texture_path", "kind"):
                    setattr(item, prop, str(value))
                elif prop == "pickup":
                    item.pickup = bool(value)
                elif prop == "visible":
                    item.visible = bool(value)
                # Sync back to the correct map
                if found_map and found_map in ws.maps:
                    ws.maps[found_map]["items"][entity_id] = type(item)(**item.__dict__) if hasattr(item, '__dict__') else item
        # sync ws.items to current map (deep copy)
        map_name = os.path.basename(ws.map_path)
        if map_name in ws.maps:
            ws.maps[map_name]["grid"] = ws.grid.copy()
            for eid, item in ws.items.items():
                ws.maps[map_name]["items"][eid] = type(item)(**item.__dict__) if hasattr(item, '__dict__') else item
        # persist immediately so map edits survive restart
        if ws.map_path:
            try:
                state_dir = os.path.join(os.path.dirname(ws.map_path), "states")
                os.makedirs(state_dir, exist_ok=True)
                state_path = os.path.join(state_dir, os.path.basename(ws.map_path).replace(".json", "_state.json"))
                ws.save_state(state_path)
            except Exception:
                pass
        return {"type": "map_edited", "operations_applied": len(ops)}

    if msg_type == "set_entity":
        entity_id = msg.get("id", "")
        if not entity_id:
            return {"type": "error", "reason": "entity id required"}
        # ── delete path ──
        if msg.get("delete"):
            existed = entity_id in ws.items
            ws.items.pop(entity_id, None)
            for mdata in ws.maps.values():
                mdata.get("items", {}).pop(entity_id, None)
            if ws.map_path:
                try:
                    import os as _os
                    state_dir = _os.path.join(_os.path.dirname(ws.map_path), "states")
                    _os.makedirs(state_dir, exist_ok=True)
                    state_path = _os.path.join(state_dir, _os.path.basename(ws.map_path).replace(".json", "_state.json"))
                    ws.save_state(state_path)
                except Exception:
                    pass
            return {"type": "entity_deleted", "id": entity_id, "existed": existed}
        # ── create / modify path ──
        prop = msg.get("prop", "")
        value = msg.get("value")
        found_map = None
        if entity_id in ws.items:
            item = ws.items[entity_id]
            found_map = os.path.basename(ws.map_path)
        else:
            for mname, mdata in ws.maps.items():
                if entity_id in mdata.get("items", {}):
                    item = mdata["items"][entity_id]
                    found_map = mname
                    break
            else:
                from metaverse.world import Item
                item = Item(id=entity_id, x=float(msg.get("x", 0)), y=float(msg.get("y", 0)),
                            kind=msg.get("kind", "portal"))
                for f in ("pickup", "visible"):
                    if f in msg: setattr(item, f, bool(msg[f]))
                for f in ("name", "owner", "capture_for", "pickup_label", "texture_path"):
                    if f in msg: setattr(item, f, str(msg[f]))
                if item.kind == "item" and not item.anim:
                    item.anim = {"float": {"speed": 0.003, "amp": 0.05}}
                ws.items[entity_id] = item
                found_map = os.path.basename(ws.map_path)
        if prop == "portal_target":
            if isinstance(value, dict) and "map" not in value:
                tx = value.get("x", item.x); ty = value.get("y", item.y)
                if abs(tx - item.x) < 0.1 and abs(ty - item.y) < 0.1:
                    return {"type": "entity_set", "id": entity_id, "prop": prop, "skipped": True}
            item.portal_target = value
        elif prop in ("x", "y", "facing", "size_3d", "width_3d"):
            setattr(item, prop, float(value))
        elif prop in ("name", "owner", "capture_for", "pickup_label", "texture_path", "kind"):
            setattr(item, prop, str(value))
        elif prop == "pickup":
            item.pickup = bool(value)
        elif prop == "visible":
            item.visible = bool(value)
        if found_map and found_map in ws.maps:
            ws.maps[found_map]["items"][entity_id] = type(item)(**item.__dict__) if hasattr(item, '__dict__') else item
        if ws.map_path:
            try:
                import os as _os2
                state_dir = _os2.path.join(_os2.path.dirname(ws.map_path), "states")
                _os2.makedirs(state_dir, exist_ok=True)
                state_path = _os2.path.join(state_dir, _os2.path.basename(ws.map_path).replace(".json", "_state.json"))
                ws.save_state(state_path)
            except Exception:
                pass
        return {"type": "entity_set", "id": entity_id, "prop": prop}

    # backward compat: delete_entity redirects to set_entity
    if msg_type == "delete_entity":
        msg["delete"] = True
        msg["type"] = "set_entity"
        return handle_message(ws, avatar_id, msg)

    if msg_type == "set_cell":
        x, y, w = msg.get("x", 0), msg.get("y", 0), msg.get("wall", 0)
        if 0 <= x < ws.grid.shape[0] and 0 <= y < ws.grid.shape[1]:
            ws.grid[x, y] = w
        # sync to current map
        map_name = os.path.basename(ws.map_path)
        if map_name in ws.maps:
            ws.maps[map_name]["grid"] = ws.grid.copy()
        return {"type": "cell_set", "x": x, "y": y, "wall": w}
    if msg_type == "dump_map":
        av = ws.avatars.get(avatar_id)
        lines = []
        lines.append(f"=== DUMP MAP ===")
        lines.append(f"ws.map_path: {ws.map_path}")
        lines.append(f"ws.grid.shape: {ws.grid.shape} (h={ws.grid.shape[1]}, w={ws.grid.shape[0]})")
        lines.append(f"")
        lines.append(f"--- Grid (x→, y↓) ---")
        h, w = ws.grid.shape[1], ws.grid.shape[0]
        for y in range(h):
            row = ''.join('█' if ws.grid[x, y] else '·' for x in range(w))
            lines.append(f"y={y:2d}: {row}")
        lines.append(f"")
        lines.append(f"--- Items ({len(ws.items)}) ---")
        for iid, item in ws.items.items():
            lines.append(f"  {iid}: x={item.x} y={item.y} kind={item.kind} pickup={item.pickup} portal={item.portal_target is not None}")
        lines.append(f"")
        lines.append(f"--- Avatars ({len(ws.avatars)}) ---")
        for aid, a in ws.avatars.items():
            lines.append(f"  {aid}: x={a.x} y={a.y} cur_map={a.current_map!r} home={a.home_map!r}")
        lines.append(f"")
        lines.append(f"--- ws.maps keys ({len(ws.maps)}) ---")
        for mname, mdata in ws.maps.items():
            g = mdata['grid']
            n_items = len(mdata.get('items', {}))
            lines.append(f"  {mname}: grid.shape=({g.shape[0]},{g.shape[1]}) items={n_items}")
        return {"type": "dump_map", "lines": "\n".join(lines)}

    return {"type": "error", "reason": f"unknown message type: {msg_type}"}


def _take_snapshot(ws: WorldState, avatar_id: str) -> bytes:
    from .snapshot import render_snapshot
    av = ws.avatars.get(avatar_id)
    # resolve the correct map path for cross-map avatars
    map_path = ws.map_path
    if av and av.current_map and av.current_map in ws.maps:
        map_dir = os.path.dirname(os.path.abspath(ws.map_path))
        map_path = os.path.join(map_dir, av.current_map)
    return render_snapshot(ws, avatar_id, map_path)


def _post_to_github(author: str, caption: str, png_bytes: bytes) -> str:
    import base64, json, subprocess, time
    token = os.environ.get("GHOSTENGINE_GITHUB_TOKEN", "")
    repo = os.environ.get("GHOSTENGINE_REPO", "")
    if not token or not repo:
        return "github-not-configured"

    # 1. Upload PNG via gh api (handles CN network better than requests)
    ts = int(time.time())
    safe_author = "".join(c for c in author if c.isalnum() or c in "_-")[:20]
    path = f"snapshots/{safe_author}_{ts}.png"
    b64_content = base64.b64encode(png_bytes).decode()
    payload = json.dumps({"message": f"snapshot: {caption[:60]}", "content": b64_content})
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}", "--method", "PUT", "--input", "-"],
        input=payload, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return f"github-upload-error-{r.returncode}"
    upload_data = json.loads(r.stdout) if r.stdout else {}
    raw_url = upload_data.get("content", {}).get("download_url", "")
    if not raw_url:
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"

    # 2. Create issue with proper image link
    title = f"📸 {author}: {caption[:80]}"
    body = f"![]({raw_url})\n\n> {caption}\n\n---\n*auto-posted from GhostEngine Metaverse*"
    issue_payload = json.dumps({"title": title, "body": body, "labels": ["metaverse", "snapshot"]})
    r2 = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues", "--method", "POST", "--input", "-"],
        input=issue_payload, capture_output=True, text=True, timeout=15)
    if r2.returncode != 0:
        return f"github-issue-error-{r2.returncode}"
    issue_data = json.loads(r2.stdout) if r2.stdout else {}
    return issue_data.get("html_url", "")


# ── Server runtime ────────────────────────────────────────────────

class ServerContext:
    """Per-server mutable state."""
    def __init__(self):
        self.goto_paths: dict[str, list] = {}


def _build_snapshot(ws: WorldState) -> dict:
    viewer_map = os.path.basename(ws.map_path) if ws.map_path else ""
    avatars = {}
    remote_avatars = {}
    for aid, a in list(ws.avatars.items()):
        inv = list(ws.inventories.get(aid, []))
        a_map = a.current_map or viewer_map
        info = {
            "name": a.name, "x": a.x, "y": a.y, "facing": a.facing,
            "owner": a.owner, "online": a.online, "kind": "avatar",
            "texture_path": a.texture_path, "current_map": a.current_map,
            "inventory": [{"id": i.id, "label": i.pickup_label, "texture_path": i.texture_path}
                          for i in inv],
        }
        if a_map != viewer_map:
            remote_avatars[aid] = info
        else:
            avatars[aid] = info
    # Build items from all maps, tagged with map_name for client-side filtering
    items = {}
    # ws.items = main map runtime items (take priority)
    for iid, i in list(ws.items.items()):
        items[iid] = {"id": i.id, "x": i.x, "y": i.y, "texture_path": i.texture_path,
                       "texture_paths": i.texture_paths, "kind": i.kind,
                       "pickup": i.pickup, "pickup_label": i.pickup_label,
                       "capture_for": i.capture_for, "portal_target": i.portal_target,
                       "size_3d": i.size_3d, "width_3d": i.width_3d,
                       "anim": i.anim, "occlusion": i.occlusion, "visible": i.visible,
                       "facing": i.facing, "name": i.name,
                       "map_name": viewer_map}
    # Template items from all preloaded maps (don't override runtime items)
    for mname, mdata in ws.maps.items():
        for iid, item in mdata.get("items", {}).items():
            if iid not in items:
                items[iid] = {"id": item.id, "x": item.x, "y": item.y,
                               "texture_path": item.texture_path,
                               "texture_paths": item.texture_paths, "kind": item.kind,
                               "pickup": item.pickup, "pickup_label": item.pickup_label,
                               "capture_for": item.capture_for, "portal_target": item.portal_target,
                               "size_3d": item.size_3d, "width_3d": item.width_3d,
                               "anim": item.anim, "occlusion": item.occlusion, "visible": item.visible,
                               "facing": item.facing, "name": item.name,
                               "map_name": mname}
    return {"type": "snapshot", "avatars": avatars, "remote_avatars": remote_avatars, "items": items,
            "grid_shape": list(ws.grid.shape), "colors": ws.colors,
            "chat": list(ws.chat_log[-20:]), "tick": ws.tick}



def _resolve_portal_target(t: dict, ws) -> dict | None:
    """Resolve a portal_target dict to {x, y, map}."""
    if not t or not isinstance(t, dict):
        return None
    if t.get("portal_id"):
        target_map_name = t.get("map", "")
        if target_map_name:
            maps_to_search = [target_map_name]
        else:
            maps_to_search = [os.path.basename(ws.map_path)] + [k for k in ws.maps if k != os.path.basename(ws.map_path)]
        for mname in maps_to_search:
            if mname not in ws.maps:
                continue
            target_items = ws.maps[mname].get("items", {})
            for item in target_items.values():
                if item.kind == "portal" and hasattr(item, 'id') and item.id == t["portal_id"]:
                    result = {"x": item.x, "y": item.y, "map": mname}
                    g = ws.maps[mname]["grid"]
                    gw, gh = g.shape
                    if int(item.x) < 0 or int(item.x) >= gw or int(item.y) < 0 or int(item.y) >= gh:
                        print(f"[server] ⚠ portal '{item.id}' on {mname} has out-of-bounds coords ({item.x:.1f},{item.y:.1f}) for grid {gw}x{gh}")
                    return result
        print(f"[server] ⚠ portal_target {t} not found in maps: {maps_to_search}")
        return None
    if "x" in t and "y" in t:
        result = {"x": t["x"], "y": t["y"]}
        if t.get("map"):
            result["map"] = t["map"]
        return result
    return None

def _tick_world(ctx: ServerContext, ws: WorldState) -> None:
    """Advance world state. Each avatar interacts with its own map."""
    # ── goto path stepping (local avatars only) ──
    for aid, av in list(ws.avatars.items()):
        path = av.goto_path
        if not path:
            continue
        tx, ty = path[0]
        dx, dy = tx - av.x, ty - av.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.1:
            path.pop(0)
            if not path:
                av.goto_path = None; av.goto_done = True
        step = min(dist, 0.1)
        nx = av.x + (dx / dist) * step
        ny = av.y + (dy / dist) * step
        av.facing = math.atan2(dy, dx)
        ws.try_move(aid, nx, ny)

    # ── track_target facing ──
    for aid, av in list(ws.avatars.items()):
        if not av.track_target:
            continue
        target = ws.avatars.get(av.track_target) or ws.items.get(av.track_target)
        if target is None:
            continue
        av.facing = math.atan2(target.y - av.y, target.x - av.x)

    # ── pickups and portals ──
    for aid in list(ws.avatars.keys()):
        av = ws.avatars.get(aid)
        if not av:
            continue
        if av.current_map and av.current_map in ws.maps:
            m = ws.maps[av.current_map]
            picked = ws._check_pickups_from(aid, m["items"])
            for item in picked:
                ws.items.pop(item.id, None)
            any_portal_nearby = False
            for item in m["items"].values():
                if item.kind != "portal" or item.portal_target is None:
                    continue
                dist = ((av.x - item.x) ** 2 + (av.y - item.y) ** 2) ** 0.5
                if dist < 1.0:
                    any_portal_nearby = True
                    if av.last_portal_id == item.id or av.last_portal_id == "__teleported__":
                        continue
                    resolved = _resolve_portal_target(item.portal_target, ws)
                    if resolved is None:
                        continue
                    tx = resolved["x"]; ty = resolved["y"]
                    if abs(tx - av.x) < 0.1 and abs(ty - av.y) < 0.1 and "map" not in resolved:
                        continue
                    av.last_portal_id = item.id
                    if "map" in resolved and resolved["map"] in ws.maps:
                        sp = ws.maps[resolved["map"]]["spawn_points"][0]
                        tx = resolved.get("x", sp["x"])
                        ty = resolved.get("y", sp["y"])
                        # Validate coordinates are within target map grid
                        tgrid = ws.maps[resolved["map"]]["grid"]
                        gw, gh = tgrid.shape
                        if 0 <= int(tx) < gw and 0 <= int(ty) < gh and tgrid[int(tx), int(ty)] == 0:
                            av.x, av.y = tx, ty
                        else:
                            print(f"[server] ⚠ portal target ({tx:.1f},{ty:.1f}) out of bounds or on wall for {resolved['map']} ({gw}x{gh}), using spawn")
                            av.x, av.y = sp["x"], sp["y"]
                        av.goto_path = None; av.goto_done = True
                        av.current_map = resolved["map"]
                        av.last_portal_id = "__teleported__"
            if av.last_portal_id == "__teleported__" and not any_portal_nearby:
                av.last_portal_id = ""
        else:
            ws.check_pickups(aid, pickup_radius=1.0)
            hmap = av.home_map or os.path.basename(ws.map_path)
            m_items = ws.maps.get(hmap, {}).get("items", {})
            target = None
            triggered_id = ""
            for item in m_items.values():
                if item.kind != "portal" or item.portal_target is None:
                    continue
                if ((av.x - item.x) ** 2 + (av.y - item.y) ** 2) ** 0.5 < 1.0:
                    if av.last_portal_id == item.id:
                        continue
                    resolved = _resolve_portal_target(item.portal_target, ws)
                    target = resolved
                    triggered_id = item.id
                    break
                elif av.last_portal_id == item.id:
                    av.last_portal_id = ""
            if target and aid in ws.avatars:
                av = ws.avatars[aid]
                av.last_portal_id = triggered_id
                if "map" in target and target["map"] in ws.maps:
                    sp = ws.maps[target["map"]]["spawn_points"][0]
                    tx = target.get("x", sp["x"]); ty = target.get("y", sp["y"])
                    tgrid = ws.maps[target["map"]]["grid"]
                    gw, gh = tgrid.shape
                    if 0 <= int(tx) < gw and 0 <= int(ty) < gh and tgrid[int(tx), int(ty)] == 0:
                        av.x, av.y = tx, ty
                    else:
                        print(f"[server] ⚠ portal target ({tx:.1f},{ty:.1f}) out of bounds for {target['map']} ({gw}x{gh}), using spawn")
                        av.x, av.y = sp["x"], sp["y"]
                    av.goto_path = None; av.goto_done = True
                    av.current_map = target["map"]
                    av.last_portal_id = ""
                else:
                    tx = target.get("x", av.x); ty = target.get("y", av.y)
                    if abs(tx - av.x) < 0.1 and abs(ty - av.y) < 0.1:
                        continue
                    safe = ws._nearest_passable(tx, ty)
                    if safe and safe != (tx, ty):
                        target["x"] = safe[0]; target["y"] = safe[1]
                    av.x = target.get("x", av.x); av.y = target.get("y", av.y)
                    av.goto_path = None; av.goto_done = True
                    if "angle" in target:
                        av.facing = target["angle"]

def _tick_loop_sync(ctx: ServerContext, ws: WorldState):
    """One tick of the server loop — called inline by LocalClient."""
    ws.tick += 1
    _tick_world(ctx, ws)


def init_server(map_path: str):
    """Initialize world state. No network server — everything runs same-process."""
    global _current_ws, _current_ctx
    ws = WorldState(map_path)
    _current_ws = ws
    ctx = ServerContext()
    _current_ctx = ctx
    state_dir = os.path.join(os.path.dirname(map_path), "states")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, os.path.basename(map_path).replace(".json", "_state.json"))
    try:
        ws.load_state(state_path)
    except Exception as e:
        print(f"Warning: could not load state: {e}")
    print(f"Server init — map: {map_path}")

    async def _auto_save():
        while True:
            await asyncio.sleep(10)
            try:
                ws.save_state(state_path)
            except Exception as e:
                print(f"Auto-save error: {e}")
    asyncio.create_task(_auto_save())
    return ws, ctx, state_path
