"""GhostEngine Map Editor — entry point.

Usage::

    python -m editor [project_dir]

Requires PySide6.  Install with:  pip install PySide6
"""

import os
import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 is required for the editor.  Install with: pip install PySide6")
    sys.exit(1)


def main():
    from .window import EditorWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    from metaverse._update_check import check_update
    check_update()
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")

    w = EditorWindow(project_dir)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
