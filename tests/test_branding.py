"""Two faces, two icons, two taskbar identities.

The launcher and the editor are separate windows a user sees side by side, so
they must not share an icon *or* an AppUserModelID: Windows groups taskbar
buttons by the id, and one shared id merges both windows into a single button
that can show only one of the two icons.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaverse import _branding

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def test_each_face_has_its_own_icon_files():
    launcher, editor = _branding.icon_path("launcher"), _branding.icon_path("editor")
    assert launcher.is_file() and editor.is_file()
    assert launcher != editor
    assert _branding.sprite_path("launcher").is_file()
    assert _branding.sprite_path("editor").is_file()


def _qt_app():
    """Qt needs a running application before anything touches icons."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_icons_carry_every_size():
    """"Sharp on a HiDPI taskbar" is the whole reason each size is rendered
    separately instead of being rescaled from a big one."""
    _qt_app()
    from PySide6.QtGui import QIcon

    for kind in ("launcher", "editor"):
        got = sorted((s.width(), s.height()) for s in QIcon(str(_branding.icon_path(kind))).availableSizes())
        assert got == SIZES, f"{kind} icon is missing sizes: {got}"


def test_the_window_icon_is_the_one_for_that_face():
    app = _qt_app()
    from PySide6.QtGui import QIcon

    assert _branding.apply_qt_icon(app, "editor") is True
    got = app.windowIcon().pixmap(48, 48).toImage()
    want = QIcon(str(_branding.icon_path("editor"))).pixmap(48, 48).toImage()
    other = QIcon(str(_branding.icon_path("launcher"))).pixmap(48, 48).toImage()
    assert got == want and got != other, "the editor came up wearing the launcher's icon"


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="taskbar identity is a Windows shell feature")
def test_each_face_claims_its_own_taskbar_identity():
    assert _branding.APP_IDS["launcher"] != _branding.APP_IDS["editor"]
    assert _branding.claim_taskbar_identity("editor") is True
    assert _branding.current_taskbar_identity() == _branding.APP_IDS["editor"]
    assert _branding.claim_taskbar_identity("launcher") is True
    assert _branding.current_taskbar_identity() == _branding.APP_IDS["launcher"]
