"""GhostEngine Map Editor — shared helpers."""

from __future__ import annotations


def wall_lookup(colors: dict, wall_type: int) -> dict | None:
    """Look up a wall definition by integer type, trying both str and int keys."""
    walls = colors.get("walls", {})
    wd = walls.get(str(wall_type))
    if wd is None:
        wd = walls.get(wall_type)
    return wd
