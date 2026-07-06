"""Stateless animation computation.

Every function is pure: accepts an AnimConfig dict and a monotonic
``frame_time_ms``, returns an :class:`AnimState`.
"""

import math
from dataclasses import dataclass


@dataclass
class AnimState:
    float_offset: float = 0.0
    pulse_scale: float = 1.0
    rotation: float = 0.0
    frame_index: int = 0


def _cfg(cfg: dict, key: str) -> dict:
    return cfg.get(key, {})


def compute_animation(
    config: dict,
    frame_time_ms: float,
    frame_count: int = 1,
) -> AnimState:
    """Evaluate all animation channels and return an :class:`AnimState`.

    Parameters
    ----------
    config:
        AnimConfig dict.  Supported keys:
        ``"float"``, ``"pulse"``, ``"rotation"``.
        Each value is a dict with at least ``"speed"`` (float).
        ``"float"`` and ``"pulse"`` also accept ``"amp"`` (default 1.0).
    frame_time_ms:
        Monotonic millisecond counter (e.g. ``pygame.time.get_ticks()``).
    frame_count:
        Number of texture frames (1 = static, >1 = GIF).  Only relevant
        when a ``"gif"`` channel is present in the config.
    """
    st = AnimState()

    # ── float ──
    fc = _cfg(config, "float")
    if fc:
        amp = fc.get("amp", 1.0)
        st.float_offset = math.sin(frame_time_ms * fc["speed"]) * amp

    # ── pulse ──
    pc = _cfg(config, "pulse")
    if pc:
        amp = pc.get("amp", 1.0)
        st.pulse_scale = 1.0 + math.sin(frame_time_ms * pc["speed"]) * amp

    # ── rotation ──
    rc = _cfg(config, "rotation")
    if rc:
        st.rotation = (frame_time_ms * rc["speed"]) % (2 * math.pi)

    # ── GIF frames ──
    gc = _cfg(config, "gif")
    if gc and frame_count > 1:
        st.frame_index = int(frame_time_ms * gc["speed"]) % frame_count

    return st
