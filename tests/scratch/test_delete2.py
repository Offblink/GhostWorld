"""Diagnostic: does Delete key erase a selected wall?"""
import sys, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack, QKeyEvent
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)
state = EditorState()
state.grid[5, 5] = 3  # wall at (5,5)
state.current_tool = "select"
state._wall_selected = False

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# Step 1: click wall to select it
class FE:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(152, 152)  # cell (5,5)
    def buttons(self): return Qt.LeftButton

canvas.mousePressEvent(FE())
print(f"After click: selected_wall_type={state.selected_wall_type}, _wall_selected={state._wall_selected}, last_click={getattr(state,'_last_click',None)}")
assert state._wall_selected, "FAIL: wall not selected after click"

# Step 2: press Delete
ke = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
canvas.keyPressEvent(ke)
print(f"After Delete: grid[5,5]={state.grid[5,5]} (expected 0)")
assert state.grid[5,5] == 0, f"FAIL: wall not erased, grid[5,5]={state.grid[5,5]}"
print("PASS")
