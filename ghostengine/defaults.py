"""Engine-wide default values. All configurable via Frame or mapfile."""

# ── Colour defaults ──────────────────────────────────────────────

DEFAULT_SKY_TOP = (135, 206, 235)
DEFAULT_SKY_BOTTOM = (240, 248, 255)
DEFAULT_FLOOR = (34, 139, 34)
DEFAULT_WALL_COLOR = (100, 100, 150)
DEFAULT_EXIT_WALL_COLOR = (50, 200, 100)

DEFAULT_WALLS = {
    1: {"color": DEFAULT_WALL_COLOR},
    2: {"color": DEFAULT_EXIT_WALL_COLOR},
}


def fallback_wall_color(wall_type: int) -> tuple[int, int, int]:
    """Return a colour for an unknown wall type by darkening the default."""
    r, g, b = DEFAULT_WALL_COLOR
    factor = max(0.4, 1.0 - wall_type * 0.08)
    return (int(r * factor), int(g * factor), int(b * factor))


# ── Rendering defaults ───────────────────────────────────────────

DEFAULT_FOV = 80.0
DEFAULT_RAY_COUNT = 300
DEFAULT_MAX_VIEW_DIST = 10.0
DEFAULT_RAY_STEP = 0.1

# ── Controller defaults ──────────────────────────────────────────

PLAYER_RADIUS = 0.3
PITCH_LIMIT_RATIO = 0.35  # fraction of screen height

# ── Entity defaults ──────────────────────────────────────────────

ENTITY_DEFAULT_SIZE_3D = 150
ENTITY_DEFAULT_WIDTH_3D = 0.2
ENTITY_DEFAULT_OCCLUSION = "center"

# ── Cache defaults ────────────────────────────────────────────────

SCALED_CACHE_MAX = 10
