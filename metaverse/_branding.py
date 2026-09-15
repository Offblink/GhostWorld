"""Who Windows thinks this program is, and which icon it wears.

Two independent things decide the taskbar button, and both have to be in place
before the first window exists:

* the **AppUserModelID** — Windows groups taskbar buttons by it, and a process
  that never claims one is grouped under its interpreter, which is why a source
  run of `python -m editor` wears python's icon;
* the **window icon** — Qt takes a `QIcon`, pygame takes a surface; the Windows
  *shell* (Explorer, Alt-Tab) additionally reads the icon embedded in a frozen
  exe, which is `tools/build_exe.py`'s job.

Asset lookup has to survive freezing: PyInstaller unpacks bundled `assets/` into
`sys._MEIPASS`, which is nowhere near `__file__`, so every path here goes through
`asset_dir()`.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_ID = "Offblink.GhostWorld"
# Two faces, two identities. Windows groups taskbar buttons by AppUserModelID, so
# a shared id would *merge* the launcher and the editor into one button and show
# exactly one of the two icons; distinct ids give each its own button (and its own
# pinned entry). Icons also differ — see `tools/make_icon.py`.
APP_IDS = {"launcher": APP_ID, "editor": f"{APP_ID}.Editor"}
ICONS = {"launcher": "ghostworld.ico", "editor": "ghostworld-editor.ico"}
SPRITES = {"launcher": "ghostworld.png", "editor": "ghostworld-editor.png"}


def asset_dir() -> Path:
    """The `assets/` directory — the bundle's when frozen, the checkout's otherwise."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def icon_path(kind: str = "launcher") -> Path:
    """The multi-size .ico: Qt icons and the frozen exe's embedded icon."""
    return asset_dir() / ICONS[kind]


def sprite_path(kind: str = "launcher") -> Path:
    """A PNG, because pygame loads surfaces and cannot read .ico."""
    return asset_dir() / SPRITES[kind]


def claim_taskbar_identity(kind: str = "launcher") -> bool:
    """Give this process its own taskbar identity; True when the OS took it.

    Called before any window is created — a window that exists first is already
    grouped under the interpreter and does not move.
    """
    if sys.platform != "win32":
        return False
    import ctypes

    return ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_IDS[kind]) == 0


def current_taskbar_identity() -> str:
    """What `claim_taskbar_identity` set, read back from the shell ("" if unset)."""
    if sys.platform != "win32":
        return ""
    import ctypes
    from ctypes import c_wchar_p

    buf = c_wchar_p()
    if ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(buf)) != 0:
        return ""
    return buf.value or ""


def apply_qt_icon(app, kind: str = "launcher") -> bool:
    """Window / Alt-Tab icon for a QApplication (PySide6). False if the .ico is missing."""
    path = icon_path(kind)
    if not path.is_file():
        return False
    from PySide6.QtGui import QIcon

    icon = QIcon(str(path))
    if icon.isNull():
        return False
    app.setWindowIcon(icon)
    return True


def apply_pygame_icon(kind: str = "launcher") -> bool:
    """The game's window icon (pygame/SDL) — call after `set_mode`."""
    path = sprite_path(kind)
    if not path.is_file():
        return False
    import pygame

    try:
        pygame.display.set_icon(pygame.image.load(str(path)))
    except (pygame.error, OSError):
        return False
    return True
