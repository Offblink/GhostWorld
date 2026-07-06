"""Test: select tool clicks wall — does _wall_selected get set?"""
import sys, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)
state = EditorState()
state.grid[5, 5] = 3  # place wall type 3 at (5,5)
state.current_tool = "select"
state.selected_wall_type = 1  # default
state._wall_selected = False  # ensure clear

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# Click on cell (5,5) = pixel (20+5*24+12, 20+5*24+12) = (152, 152)
class FakeEvent:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(152, 152)
    def buttons(self): return Qt.LeftButton

canvas.mousePressEvent(FakeEvent())

print(f"selected_wall_type: {state.selected_wall_type} (expected 3)")
print(f"_wall_selected: {getattr(state, '_wall_selected', False)} (expected True)")
print(f"current_tool: {state.current_tool} (expected select)")
assert state.selected_wall_type == 3, "FAIL: wall type not selected"
assert state._wall_selected == True, "FAIL: _wall_selected not set"
print("PASS")
