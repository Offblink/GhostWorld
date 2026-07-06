"""Test: select tool clicks wall and entity."""
import sys, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)
state = EditorState()
state.grid[5, 5] = 3  # wall
state.entities = [{"x": 7.5, "y": 7.5, "texture": "", "size_3d": 150, "width_3d": 0.2, "anim": {}, "occlusion": "center"}]
state.current_tool = "select"
state.selected_wall_type = 1
state._wall_selected = False

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# Click wall at (5,5): pixel = (20+5*24+12, 20+5*24+12) = (152, 152)
class FE:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(152, 152)
    def buttons(self): return Qt.LeftButton

canvas.mousePressEvent(FE())
print(f"After wall click: selected_wall_type={state.selected_wall_type} (expect 3)")
print(f"_wall_selected={state._wall_selected} (expect True)")
assert state.selected_wall_type == 3, "FAIL wall select"
assert state._wall_selected == True, "FAIL _wall_selected"

# Click entity at (7.5, 7.5): pixel = (20+7*24+12, 20+7*24+12) = (200, 200)
canvas.mousePressEvent(type('E',(),{'button':lambda s:Qt.LeftButton,'pos':lambda s:QPoint(200,200),'buttons':lambda s:Qt.LeftButton})())
print(f"After entity click: selected_entity_idx={state.selected_entity_idx} (expect 0)")
assert state.selected_entity_idx == 0, "FAIL entity select"
print("ALL PASS")
