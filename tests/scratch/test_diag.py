"""Diagnostic: entity overwrite, spawn/exit placement, wall toggle."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from PySide6.QtCore import QPoint, Qt
from editor.model import EditorState
from editor.canvas import GridCanvas

app = QApplication(sys.argv)

def test_wall_toggle():
    st = EditorState()
    st.current_tool = "wall"
    st.selected_wall_type = 5
    canvas = GridCanvas(st, QUndoStack())
    canvas.setGeometry(0,0,400,400); canvas.refresh()
    FE = type('E',(),{'button':lambda s:Qt.LeftButton,'pos':lambda s:QPoint(152,152),'buttons':lambda s:Qt.LeftButton})
    canvas.mousePressEvent(FE())
    assert st.grid[5,5]==5, f"Wall place: {st.grid[5,5]}"
    canvas.mousePressEvent(FE())
    assert st.grid[5,5]==0, f"Wall toggle erase: {st.grid[5,5]}"
    print("PASS: wall toggle")

def test_entity_overwrite():
    st = EditorState()
    st.entities = [{"x":5.5,"y":5.5,"texture":"old.png","size_3d":100,"width_3d":0.1,"anim":{},"occlusion":"center"}]
    st.current_tool = "entity"
    canvas = GridCanvas(st, QUndoStack())
    canvas.setGeometry(0,0,400,400); canvas.refresh()
    FE = type('E',(),{'button':lambda s:Qt.LeftButton,'pos':lambda s:QPoint(152,152),'buttons':lambda s:Qt.LeftButton})
    canvas.mousePressEvent(FE())
    e = st.entities[0]
    assert e["texture"]=="", f"Entity not overwritten: {e} (texture should be empty default)"
    print("PASS: entity overwrite")

def test_spawn():
    st = EditorState()
    st.current_tool = "spawn"
    canvas = GridCanvas(st, QUndoStack())
    canvas.setGeometry(0,0,400,400); canvas.refresh()
    FE = type('E',(),{'button':lambda s:Qt.LeftButton,'pos':lambda s:QPoint(152,152),'buttons':lambda s:Qt.LeftButton})
    canvas.mousePressEvent(FE())
    assert st.player_spawn[0]==5.5, f"Spawn x: {st.player_spawn}"
    print("PASS: spawn")

def test_exit():
    st = EditorState()
    st.current_tool = "exit"
    canvas = GridCanvas(st, QUndoStack())
    canvas.setGeometry(0,0,400,400); canvas.refresh()
    FE = type('E',(),{'button':lambda s:Qt.LeftButton,'pos':lambda s:QPoint(152,152),'buttons':lambda s:Qt.LeftButton})
    canvas.mousePressEvent(FE())
    assert st.exit_pos==(5,5), f"Exit: {st.exit_pos}"
    print("PASS: exit")

test_wall_toggle()
test_entity_overwrite()
test_spawn()
test_exit()
print("\nALL PASS")
