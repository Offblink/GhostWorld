"""Detect unexpected top-level windows in the GhostEngine editor."""
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.dont_write_bytecode = True
ROOT = r'C:\tmp\ghostengine'
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QPoint

app = QApplication.instance() or QApplication(sys.argv)

# Create a test map with a portal
import json, tempfile
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
tmpdir = os.path.join(ROOT, "examples")
os.makedirs(tmpdir, exist_ok=True)
map_path = os.path.join(tmpdir, "_test_window.json")
with open(map_path, "w", encoding="utf-8") as f:
    json.dump(test_map, f)

from editor.window import EditorWindow

print("=== Before creating EditorWindow ===")
for w in QApplication.topLevelWidgets():
    print(f"  Top-level: {type(w).__name__} visible={w.isVisible()} title='{w.windowTitle()}'")

window = EditorWindow(project_dir=tmpdir)
window._load_map(map_path)

print("\n=== After creating EditorWindow + loading map ===")
for w in QApplication.topLevelWidgets():
    print(f"  Top-level: {type(w).__name__} visible={w.isVisible()} title='{w.windowTitle()}'")

# Check PropertyPanel - is it a top-level window?
props = window._props
print(f"\n=== PropertyPanel ===")
print(f"  Type: {type(props).__name__}")
print(f"  isWindow: {props.isWindow()}")
print(f"  parent: {type(props.parent()).__name__ if props.parent() else 'None'}")
print(f"  isVisible: {props.isVisible()}")

# Simulate clicking the portal entity on the canvas
from editor.canvas import GridCanvas
canvas = window._grid

# Find the portal entity cell
portal_ent = window.state.entities[0]
gx = int(portal_ent["x"])
gy = int(portal_ent["y"])
print(f"\n=== Clicking portal at grid ({gx}, {gy}) ===")

# Calculate screen position of the grid cell
cell_size = GridCanvas.CELL_SIZE
# Center of canvas
cw = canvas.width(); ch = canvas.height()
pm = canvas._pm
if pm:
    dx = (cw - pm.width()) // 2; dy = (ch - pm.height()) // 2
    sx = dx + int(gx * cell_size) + cell_size // 2
    sy = dy + int(gy * cell_size) + cell_size // 2
    print(f"  Clicking at screen pos: ({sx}, {sy})")

    # Use select tool
    window._set_tool("select")
    QTest.mouseClick(canvas, Qt.LeftButton, pos=canvas.mapFromGlobal(canvas.mapToGlobal(
        QPoint(sx, sy))))

print(f"\n  Selected entity index: {window.state.selected_entity_idx}")

print("\n=== After clicking portal ===")
for w in QApplication.topLevelWidgets():
    print(f"  Top-level: {type(w).__name__} visible={w.isVisible()} title='{w.windowTitle()}'")

# Check if there are MORE top-level windows than expected
top_levels = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
print(f"\n  Visible top-level windows: {len(top_levels)}")
for w in top_levels:
    print(f"    - {type(w).__name__}: '{w.windowTitle()}' isWindow={w.isWindow()}")

# Also check: does the PropertyPanel have any CHILD that is a window?
def find_windows(widget, depth=0):
    results = []
    for child in widget.children():
        try:
            if child.isWidgetType() and child.isWindow():
                results.append((depth, type(child).__name__, child.windowTitle(), child.isVisible()))
            results.extend(find_windows(child, depth + 1))
        except:
            pass
    return results

print("\n=== PropertyPanel children that are windows ===")
for d, name, title, vis in find_windows(props):
    print(f"  {'  ' * d}{name}: '{title}' visible={vis}")

# Cleanup
os.unlink(map_path)
print("\nDone.")
