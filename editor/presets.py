"""GhostEngine 地图编辑器 — 实体预设系统。"""

from __future__ import annotations

from typing import Any

DEFAULT_PRESETS: list[dict[str, Any]] = [
    {
        "name": "精灵",
        "entity": {
            "kind": "avatar", "facing": 0.0, "preset_idx": 0,
            "size_3d": 800, "width_3d": 0.8,
            "anim": {"float": {"speed": 0.003, "amp": 0.05}},
            "occlusion": "per_column", "texture": "",
            "invisible": False, "mm_trigger": False,
            "name": "", "owner": "", "metadata": {},
            "capture_for": "", "portal_target": None,
        },
    },
    {
        "name": "物品",
        "entity": {
            "kind": "item", "facing": 0.0, "preset_idx": 1,
            "size_3d": 150, "width_3d": 0.2,
            "anim": {"float": {"speed": 0.003, "amp": 0.05}},
            "occlusion": "center", "texture": "",
            "invisible": False, "mm_trigger": False,
            "pickup": True, "pickup_label": "",
            "name": "", "owner": "", "metadata": {},
            "capture_for": "", "portal_target": None,
        },
    },
]
