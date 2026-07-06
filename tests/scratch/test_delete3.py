"""Diagnostic: does window QShortcut eat Delete before canvas?"""
import sys, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QShortcut, QKeySequence, QUndoStack, QKeyEvent
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)
state = EditorState()
state.grid[5, 5] = 3
state.current_tool = "select"

undo = QUndoStack()
canvas = GridCanvas(state, undo)
canvas.setGeometry(0, 0, 400, 400)
canvas.refresh()

# Add QShortcut like the editor does
sc_calls = [0]
def on_sc():
    sc_calls[0] += 1
sc = QShortcut(QKeySequence(Qt.Key_Delete), canvas)
sc.activated.connect(on_sc)

# Click wall
class FE:
    def button(self): return Qt.LeftButton
    def pos(self): return QPoint(152, 152)
    def buttons(self): return Qt.LeftButton
canvas.mousePressEvent(FE())

# Send Delete
ke = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
QApplication.sendEvent(canvas, ke)
print(f"Shortcut calls: {sc_calls[0]}")
print(f"keyPressEvent should have run: grid[5,5]={state.grid[5,5]}")

# Send Delete via shortcut (simulate what happens when shortcut fires)
QApplication.sendEvent(canvas, ke)  # second press
print(f"After 2nd Delete: grid[5,5]={state.grid[5,5]}, sc calls={sc_calls[0]}")
