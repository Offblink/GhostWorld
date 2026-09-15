"""GhostEngine Map Editor — entry point.

Usage::

    python -m editor [project_dir]

Requires PySide6.  Install with:  pip install PySide6
"""

import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 is required for the editor.  Install with: pip install PySide6")
    sys.exit(1)


def main():
    from pathlib import Path

    from .window import EditorWindow

    from metaverse._branding import apply_qt_icon, claim_taskbar_identity
    from metaverse._paths import utf8_stdio

    utf8_stdio()               # the startup block prints ✓/✗, pipes are not UTF-8 by default
    claim_taskbar_identity("editor")   # its own taskbar button, next to the game's
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_qt_icon(app, "editor")

    from metaverse._update_check import check_update
    check_update()

    from metaverse._paths import seed_examples, startup_lines
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = str(seed_examples())

    for line in startup_lines({"项目": Path(project_dir)}):
        print(f"[editor] {line}")
    w = EditorWindow(project_dir)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
