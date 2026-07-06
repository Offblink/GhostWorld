"""Default demo map 2 — return portal back to map 1."""
DEFAULT_MAP2 = {
  "version": 3,
  "grid": [
    [1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1]
  ],
  "player_spawn": {"x": 1.5, "y": 5.5, "angle": 0.0},
  "entities": [
    {"x": 8.5, "y": 5.5, "kind": "portal", "id": "portal_back",
     "portal_target": {"portal_id": "portal_north", "map": "_default_map.json"},
     "size_3d": 150, "width_3d": 0.2, "occlusion": "center"}
  ],
  "colors": {
    "sky_top": [80, 140, 220], "sky_bottom": [160, 200, 240],
    "floor": [60, 120, 60],
    "walls": {"1": {"color": [100, 140, 120]}}
  }
}
