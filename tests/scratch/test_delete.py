"""Test: Delete key on wall + exit dialog Chinese."""
import sys, numpy as np
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QUndoStack, QKeyEvent
from PySide6.QtCore import Qt
app = QApplication(sys.argv)
from editor.model import EditorState
from editor.canvas import GridCanvas

# 1. Test wall delete via keyPressEvent
state = EditorState()
state.grid[5,5] = 3
state.selected_wall_type = 3
state._wall_selected = True
state.current_tool = "select"

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0,0,400,400)
canvas.refresh()

# Simulate Delete key
ke = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
canvas.keyPressEvent(ke)
print(f"After Delete: grid[5,5]={state.grid[5,5]} _wall_selected={getattr(state,'_wall_selected',None)}")

# 2. Test exit dialog buttons
# QMessageBox standard buttons should be localized by Qt
sb = QMessageBox.StandardButton
names = {sb.Save: "Save", sb.Discard: "Discard", sb.Cancel: "Cancel"}
print("Button texts:")
for btn, eng in names.items():
    print(f"  {eng} -> {QMessageBox.tr(eng)}")
print("Done")
