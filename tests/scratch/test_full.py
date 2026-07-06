"""Test: full editor window click flow."""
import sys, tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QPoint
app = QApplication(sys.argv)
from editor.window import EditorWindow

w = EditorWindow(tempfile.gettempdir())
w.show()
QTest.qWait(100)  # let layout settle

# Verify state
print(f"Tool: {w.state.current_tool} (expect select)")
print(f"Grid[7,7]: {w.state.grid[7,7]} (expect 0)")

# Switch to wall tool
w._set_tool("wall")
print(f"Tool after switch: {w.state.current_tool}")

# Simulate click on grid at (7,7)
# Grid is centered in the canvas widget. Canvas size depends on grid dimensions.
# Grid is 15x15 with CELL_SIZE=24 → 360x360 pixmap
# Canvas minimum size = 360x360. But actual size in window is larger (splitter gives more space)
# Need to find where the grid pixmap is on screen

# Let's find the grid widget and its position
gw = w._grid
print(f"Grid widget size: {gw.width()}x{gw.height()}")
print(f"Grid widget pos: {gw.mapToGlobal(QPoint(0,0))}")

# Compute click position: cell (7,7) = pixel (20 + 7*24 + 12, 20 + 7*24 + 12) = (200, 200)
# if pixmap is 360x360 centered in widget
pm = gw._pm
if pm:
    print(f"Pixmap size: {pm.width()}x{pm.height()}")
    dx = (gw.width() - pm.width()) // 2
    dy = (gw.height() - pm.height()) // 2
    click_x = dx + 7*24 + 12
    click_y = dy + 7*24 + 12
    print(f"Clicking at widget coords: ({click_x}, {click_y})")
    
    QTest.mouseClick(gw, Qt.LeftButton, pos=QPoint(click_x, click_y))
    QTest.qWait(100)
    
    print(f"Grid[7,7] after click: {w.state.grid[7,7]} (expect 1)")
    if w.state.grid[7,7] == 1:
        print("PASS")
    else:
        print("FAIL - wall not placed")
else:
    print("FAIL - no pixmap")
