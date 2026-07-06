"""Test: entity tool places entity."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)
state = EditorState()
state.current_tool = "entity"

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# Click empty cell (5,5)
class FE:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(152, 152)
    def buttons(self): return Qt.LeftButton

canvas.mousePressEvent(FE())
print(f"entities count: {len(state.entities)} (expect 1)")
assert len(state.entities) == 1, f"FAIL: {len(state.entities)}"
print(f"entity: {state.entities[0]}")
print("PASS")
