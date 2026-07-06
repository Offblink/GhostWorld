"""Integration test: GridCanvas mouse click places wall."""
import sys, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)

state = EditorState()
state.current_tool = "wall"
state.selected_wall_type = 5
undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# After refresh, pixmap is built at 15*24 = 360x360
# Canvas is 400x400, so centering offsets: dx=dy=(400-360)//2 = 20
# Click at pixel (20+7*24+12, 20+7*24+12) = (200, 200) for cell (7,7)
px = 20 + 7*24 + 12
py = 20 + 7*24 + 12
print(f"Clicking at pixel ({px},{py}) → expected cell (7,7)")

class FakeEvent:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(px, py)
    def buttons(self): return Qt.LeftButton

canvas.mousePressEvent(FakeEvent())
print(f"grid[7,7] = {state.grid[7,7]} (expected 5)")
assert state.grid[7,7] == 5, f"FAIL: got {state.grid[7,7]}"
print("PASS!")
