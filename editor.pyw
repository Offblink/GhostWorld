"""GhostEngine Map Editor — thin launcher.

For the full editor package, see:  editor/
"""

import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 is required for the editor.  Install with: pip install PySide6")
    sys.exit(1)

from editor.window import EditorWindow


def main():
    from metaverse._branding import apply_qt_icon, claim_taskbar_identity

    claim_taskbar_identity("editor")   # its own taskbar button, next to the game's
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_qt_icon(app, "editor")

    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        from metaverse._paths import seed_examples

        project_dir = str(seed_examples())

    from pathlib import Path

    from metaverse._paths import startup_lines
    for line in startup_lines({"项目": Path(project_dir)}):
        print(f"[editor] {line}")

    w = EditorWindow(project_dir)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
