"""Identify which QGroupBox widgets are top-level windows."""
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.dont_write_bytecode = True
sys.path.insert(0, r'C:\tmp\ghostengine')

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

import json
test_map = {
    "version": 3,
    "grid": [[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1]],
    "player_spawn": {"x": 2.5, "y": 2.5, "angle": 0.0},
    "entities": [
        {"x": 2.5, "y": 3.5, "kind": "portal", "id": "portal_0", "portal_target": None,
         "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
    ],
    "colors": {"sky_top": [135,206,235], "sky_bottom": [240,248,255], "floor": [34,139,34],
               "walls": {"1": {"color": [100,100,150]}}},
    "minimap": {"mode": "always", "duration": 0}
}
tmpdir = os.path.join(r'C:\tmp\ghostengine', "examples")
map_path = os.path.join(tmpdir, "_test_window2.json")
with open(map_path, "w", encoding="utf-8") as f:
    json.dump(test_map, f)

from editor.window import EditorWindow
window = EditorWindow(project_dir=tmpdir)
window._load_map(map_path)

# Identify top-level QGroupBox widgets
from PySide6.QtWidgets import QGroupBox, QFrame, QMenu

print("=== Top-level QGroupBox widgets ===")
for w in QApplication.topLevelWidgets():
    if isinstance(w, QGroupBox):
        print(f"  QGroupBox: title='{w.title()}' objectName='{w.objectName()}' visible={w.isVisible()}")
        # Check if it has a parent
        print(f"    parent: {type(w.parent()).__name__ if w.parent() else 'NONE'}")
        # Try to find this widget in the window's widget tree
        def find_in_tree(root, target, path=""):
            if root is target:
                return path
            for child in root.children():
                try:
                    if child.isWidgetType():
                        result = find_in_tree(child, target, path + "/" + type(child).__name__)
                        if result:
                            return result
                except:
                    pass
            return None
        location = find_in_tree(window, w, "EditorWindow")
        if location:
            print(f"    In tree: {location}")
        else:
            print(f"    NOT in EditorWindow tree!")

# Also identify QFrame top-level
print("\n=== Top-level QFrame widgets ===")
for w in QApplication.topLevelWidgets():
    if isinstance(w, QFrame) and not isinstance(w, QGroupBox):
        print(f"  QFrame: objectName='{w.objectName()}' visible={w.isVisible()}")

os.unlink(map_path)
print("\nDone.")
