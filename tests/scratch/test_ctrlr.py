"""Test: menu action triggers _run_with_runner."""
import sys, tempfile
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from editor.window import EditorWindow

w = EditorWindow(tempfile.gettempdir())

# Find the Ctrl+R action by searching all children
for child in w.findChildren(type(app)):
    pass

found = False
for act in w.findChildren(type(w.menuBar().actions()[0])):
    pass

# Simpler: trigger via menu text search
mb = w.menuBar()
actions = mb.actions()
if actions:
    fm = actions[0].menu()
    if fm:
        for a in fm.actions():
            if '启动器' in a.text():
                # Keep a reference to prevent GC
                act = a
                print(f"Found: {act.text()} shortcut={act.shortcut().toString()}")
                # Trigger it
                called = [False]
                w._run_with_runner = lambda: called.__setitem__(0, True)
                act.trigger()
                print(f"Triggered: {called[0]}")
                found = True
                break

if not found:
    # Fallback: check if _run_with_runner is callable
    print(f"_run_with_runner exists: {hasattr(w, '_run_with_runner')}")
    w.state.map_path = tempfile.gettempdir() + '/dummy.json'
    w._save_to = lambda p: None  # prevent actual save
    try:
        w._run_with_runner()
        print("_run_with_runner called directly - OK")
    except Exception as e:
        print(f"Error: {e}")
print("Done")
