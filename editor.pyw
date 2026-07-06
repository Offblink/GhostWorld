"""GhostEngine Map Editor — thin launcher.

For the full editor package, see:  editor/
"""

import os
import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 is required for the editor.  Install with: pip install PySide6")
    sys.exit(1)

from editor.window import EditorWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")

    w = EditorWindow(project_dir)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
