"""Shared utilities used by both local_client and local_agent.

Extracted to eliminate duplication across:
- runner.py (standalone engine)
- local_client.py (metaverse human client)
- local_agent.py (metaverse agent)
"""

import pygame


def fix_ime() -> None:
    """Force US keyboard layout on Windows to work around pygame IME issues."""
    try:
        import ctypes
        h = ctypes.windll.user32.LoadKeyboardLayoutW("00000409", 1)
        if h:
            ctypes.windll.user32.ActivateKeyboardLayout(h, 0)
    except Exception:
        pass


def chinese_font(size: int) -> pygame.font.Font:
    """Return a pygame Font that supports Chinese characters, falling back to default."""
    for name in ["Microsoft YaHei", "SimHei", "SimSun", "FangSong", "KaiTi"]:
        try:
            return pygame.font.SysFont(name, size)
        except Exception:
            continue
    return pygame.font.Font(None, size)


def process_agent_command(handle_message, ws, agent_name: str, cmd: dict, log_fn=None) -> dict | None:
    """Dispatch a single agent command dict to the world.

    Parameters
    ----------
    handle_message: callable(ws, agent_name, msg_dict) -> response_dict
        The server's message handler.
    ws: WorldState
        The shared world state.
    agent_name: str
        Agent's avatar name (e.g. "omp").
    cmd: dict
        Command with at least a "cmd" key.
    log_fn: callable(dict) | None
        Optional logger (for local_agent's JSONL output).

    Returns
    -------
    dict | None
        The response from handle_message, or None if not applicable.
    """
    action = cmd.get("cmd", "")
    resp = None
    if action == "say":
        resp = handle_message(ws, agent_name, {"type": "say", "message": cmd["message"], "channel": "global"})
        if log_fn:
            log_fn({"event": "said", "message": cmd["message"]})
    elif action == "move":
        resp = handle_message(ws, agent_name, {"type": "move", "x": cmd["x"], "y": cmd["y"], "facing": 0})
        if log_fn:
            log_fn({"event": "moving", "to": [cmd["x"], cmd["y"]]})
    elif action == "turn":
        import math
        av = ws.avatars.get(agent_name)
        dx = cmd["x"] - av.x; dy = cmd["y"] - av.y
        resp = handle_message(ws, agent_name, {"type": "turn", "facing": math.atan2(dy, dx)})
    elif action == "track":
        resp = handle_message(ws, agent_name, {"type": "track", "target": cmd.get("target", "")})
        if log_fn:
            log_fn({"event": "tracking", "target": cmd.get("target", "")})
    elif action == "untrack":
        resp = handle_message(ws, agent_name, {"type": "untrack"})
        if log_fn:
            log_fn({"event": "untracked"})
    elif action == "pos":
        resp = handle_message(ws, agent_name, {"type": "pos"})
        if log_fn and resp:
            log_fn({"event": "position", "x": resp.get("x"), "y": resp.get("y"), "map": resp.get("map")})
    elif action == "inv":
        resp = handle_message(ws, agent_name, {"type": "inv"})
        if log_fn and resp:
            log_fn({"event": "inventory", "items": resp.get("items"), "avatars": resp.get("avatars")})
    elif action == "goto":
        resp = handle_message(ws, agent_name, {"type": "goto", "x": cmd["x"], "y": cmd["y"]})
        if log_fn and resp and resp.get("type") == "navigating":
            log_fn({"event": "navigating", "waypoints": len(resp["waypoints"]), "target": resp["target"]})
    elif action == "snapshot":
        resp = handle_message(ws, agent_name, {"type": "snapshot", "caption": cmd.get("caption", "")})
    elif action == "post_issue":
        resp = handle_message(ws, agent_name, {"type": "post_issue", "caption": cmd.get("caption", ""), "filepath": cmd.get("filepath", "")})
        if log_fn and resp:
            log_fn({"event": "post_issue", "url": resp.get("url", "")})
    elif action == "edit_map":
        resp = handle_message(ws, agent_name, {"type": "edit_map", "operations": cmd["operations"]})
        if log_fn:
            log_fn({"event": "map_edit_sent", "ops": len(cmd.get("operations", []))})
    elif action == "look":
        resp = handle_message(ws, agent_name, {"type": "look"})
        if log_fn and resp:
            log_fn({"event": "perception", "position": resp.get("position"), "nearby_items": resp.get("nearby_items"), "all_items": resp.get("all_items"), "inventory": resp.get("inventory")})
    elif action == "pickup":
        msg = {"type": "pickup", "item_id": cmd.get("item_id", "")}
        if "x" in cmd: msg["x"] = cmd["x"]
        if "y" in cmd: msg["y"] = cmd["y"]
        resp = handle_message(ws, agent_name, msg)
        if log_fn:
            log_fn({"event": "picked_up" if resp.get("type") == "picked_up" else "pickup_failed",
                    "item_id": resp.get("item_id", cmd.get("item_id", "")), "label": resp.get("label", "")})
    elif action == "set_entity":
        msg = {"type": "set_entity", "id": cmd.get("id", ""),
            "prop": cmd.get("prop", ""), "value": cmd.get("value"),
            "x": cmd.get("x", 0), "y": cmd.get("y", 0), "kind": cmd.get("kind", "portal"),
            "pickup": cmd.get("pickup"), "pickup_label": cmd.get("pickup_label", ""),
            "capture_for": cmd.get("capture_for", ""), "name": cmd.get("name", ""),
            "texture_path": cmd.get("texture_path", ""), "visible": cmd.get("visible")}
        if cmd.get("delete"):
            msg["delete"] = True
        resp = handle_message(ws, agent_name, msg)
        if log_fn:
            ev = "entity_deleted" if cmd.get("delete") else "entity_set"
            log_fn({"event": ev, "id": cmd.get("id"), "prop": cmd.get("prop") if not cmd.get("delete") else None})
    elif action == "delete_entity":
        new_cmd = dict(cmd, delete=True, cmd="set_entity")
        return process_agent_command(handle_message, ws, agent_name, new_cmd, log_fn=log_fn)
    elif action == "set_cell":
        resp = handle_message(ws, agent_name, {"type": "set_cell", "x": cmd.get("x", 0), "y": cmd.get("y", 0), "wall": cmd.get("wall", 0)})
        if log_fn:
            log_fn({"event": "cell_set", "x": cmd.get("x"), "y": cmd.get("y"), "wall": cmd.get("wall")})
    elif action == "place":
        resp = handle_message(ws, agent_name, {"type": "place", "item_id": cmd.get("item_id", ""), "x": cmd.get("x", 0), "y": cmd.get("y", 0)})
        if log_fn and resp:
            log_fn({"event": "placed", "item_id": cmd.get("item_id"), "x": cmd.get("x"), "y": cmd.get("y")})
    elif action == "give":
        resp = handle_message(ws, agent_name, {"type": "give", "target": cmd.get("target", ""), "item_id": cmd.get("item_id", "")})
        if log_fn:
            log_fn({"event": "gave", "item": cmd.get("item_id", ""), "to": cmd.get("target", "")})
    elif action == "dump_map":
        resp = handle_message(ws, agent_name, {"type": "dump_map"})
        if log_fn and resp and resp.get("type") == "dump_map":
            log_fn({"event": "dump_map", "lines": resp.get("lines", "")})
    return resp
