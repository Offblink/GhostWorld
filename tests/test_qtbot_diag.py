"""Use qtbot to diagnose the gap between portal fields and delete button."""
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.dont_write_bytecode = True
sys.path.insert(0, r'C:\tmp\ghostengine')

from PySide6.QtWidgets import QApplication, QWidget, QGroupBox
from PySide6.QtCore import QRect

app = QApplication.instance() or QApplication(sys.argv)

from editor.model import EditorState
from editor.props import PropertyPanel
from PySide6.QtGui import QUndoStack

st = EditorState()
st.map_path = r'C:\tmp\ghostengine\examples\_dbg.json' if os.path.exists(r'C:\tmp\ghostengine\examples\_dbg.json') else '.'
st.entities = [
    {"x": 2.5, "y": 3.5, "kind": "portal", "id": "portal_0", "portal_target": None,
     "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
]
st.selected_entity_idx = 0
st.current_tool = "select"
undo = QUndoStack()

panel = PropertyPanel(st, undo)
panel.refresh()

# Force layout calculation
panel.setGeometry(0, 0, 250, 600)
panel.show()
app.processEvents()

print("=== Widget tree with positions ===")

def dump_tree(widget: QWidget, depth=0):
    geo = widget.geometry()
    if geo.width() > 0 and geo.height() > 0:
        visible = widget.isVisible()
        indent = "  " * depth
        name = type(widget).__name__
        title = widget.windowTitle() if hasattr(widget, 'windowTitle') else ''
        objname = widget.objectName()
        extra = ''
        if isinstance(widget, QGroupBox):
            extra = f" title='{widget.title()}'"
        print(f"{indent}{name}{extra} geo=({geo.x()},{geo.y()}) {geo.width()}x{geo.height()} visible={visible}")
        for child in widget.children():
            if isinstance(child, QWidget) and child is not widget:
                dump_tree(child, depth + 1)

dump_tree(panel)

# Specifically check the gap
sub_stack = panel._sub_stack
stack_geo = sub_stack.geometry()
print(f"\n=== QStackedWidget geometry: ({stack_geo.x()},{stack_geo.y()}) {stack_geo.width()}x{stack_geo.height()} ===")
print(f"  Current page index: {sub_stack.currentIndex()}")
print(f"  Size hint: {sub_stack.sizeHint().width()}x{sub_stack.sizeHint().height()}")
print(f"  Min size hint: {sub_stack.minimumSizeHint().width()}x{sub_stack.minimumSizeHint().height()}")

# Check each page's size hint
for i in range(sub_stack.count()):
    page = sub_stack.widget(i)
    print(f"  Page {i}: sizeHint={page.sizeHint().width()}x{page.sizeHint().height()} visible={page.isVisible()}")

# Find the delete button
del_btn = panel._ent_del
del_geo = del_btn.geometry()
print(f"\n=== Delete button: ({del_geo.x()},{del_geo.y()}) {del_geo.width()}x{del_geo.height()} ===")

# Gap between stack bottom and delete button top
stack_bottom = stack_geo.y() + stack_geo.height()
del_top = del_geo.y()
gap = del_top - stack_bottom
print(f"\n=== Gap between stack bottom ({stack_bottom}) and delete top ({del_top}): {gap}px ===")

# What's in the gap?
print("\n=== Widgets in gap region ===")
for child in panel.findChildren(QWidget):
    if child is panel or child is sub_stack or child is del_btn:
        continue
    geo = child.geometry()
    if geo.y() >= stack_bottom and geo.y() + geo.height() <= del_top and geo.width() > 0:
        print(f"  {type(child).__name__}: ({geo.x()},{geo.y()}) {geo.width()}x{geo.height()} visible={child.isVisible()}")
