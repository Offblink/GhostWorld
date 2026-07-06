"""Texture loading with LRU cache.

The engine renderer receives :class:`pygame.Surface` objects directly —
it never touches the filesystem.  This module is used by *frontends*
to resolve relative paths and avoid redundant I/O.
"""

from __future__ import annotations

import os
import pygame

try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    PILImage = None  # type: ignore[assignment]
    _HAS_PIL = False


class TextureLoader:
    """Loads and caches :class:`pygame.Surface` objects from disk.

    Parameters
    ----------
    base_dir:
        Directory that relative ``texture`` paths in map files are
        resolved against (usually the project ``assets/`` folder).
    """

    def __init__(self, base_dir: str) -> None:
        self._base = base_dir
        self._cache: dict[str, pygame.Surface] = {}

    # ── public API ──────────────────────────────────────────────

    def load(self, relative_path: str) -> pygame.Surface:
        if not relative_path:
            return pygame.Surface((1, 1))
        full = os.path.join(self._base, relative_path)
        if full in self._cache:
            return self._cache[full]
        try:
            surf = pygame.image.load(full)
            try:
                surf = surf.convert_alpha()
            except Exception:
                pass  # headless — no display surface to optimize against
        except Exception:
            surf = pygame.Surface((16, 16))
            surf.fill((255, 0, 255))  # magenta — visible placeholder
        self._cache[full] = surf
        return surf

    def load_frames(self, relative_path: str) -> list[pygame.Surface]:
        """Load an animated GIF as a list of frames.

        Requires Pillow for animated GIF support.  Falls back to a
        single-frame load if Pillow is not installed.
        """
        full = os.path.join(self._base, relative_path)
        cache_key = f"__gif__{full}"

        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[return-value]

        ext = os.path.splitext(relative_path)[1].lower()
        frames: list[pygame.Surface] = []

        if ext == ".gif" and _HAS_PIL:
            pil_img = PILImage.open(full)
            try:
                while True:
                    frame = pil_img.copy().convert("RGBA")
                    mode = frame.mode
                    size = frame.size
                    data = frame.tobytes("raw", mode)
                    surf = pygame.image.fromstring(data, size, mode)
                    frames.append(surf)
                    pil_img.seek(pil_img.tell() + 1)
            except EOFError:
                pass
            finally:
                pil_img.close()
        else:
            frames = [self.load(relative_path)]

        self._cache[cache_key] = frames
        return frames

    def clear(self) -> None:
        """Discard all cached surfaces."""
        self._cache.clear()
