"""qtbot test: verify right panel shows correct sub-panel per entity kind."""
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.dont_write_bytecode = True
sys.path.insert(0, r'C:\tmp\ghostengine')

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from editor.model import EditorState
from editor.props import PropertyPanel

@pytest.fixture
def panel(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    st = EditorState()
    st.map_path = '.'
    st.entities = [
        {"x": 2.5, "y": 3.5, "kind": "portal", "id": "portal_0", "portal_target": None,
         "size_3d": 150, "width_3d": 0.2, "occlusion": "center"},
        {"x": 1.5, "y": 1.5, "kind": "avatar", "size_3d": 800, "width_3d": 0.8,
         "occlusion": "per_column"},
        {"x": 3.5, "y": 3.5, "kind": "item", "pickup": True, "pickup_label": "gem",
         "size_3d": 100, "width_3d": 0.2, "occlusion": "center"},
    ]
    st.selected_entity_idx = -1
    st.current_tool = "select"
    undo = QUndoStack()
    p = PropertyPanel(st, undo)
    p.show()
    app.processEvents()
    return p, st

def assert_showing(widget, msg=""):
    """Assert widget is NOT hidden (i.e., setVisible(True) was called)."""
    assert not widget.isHidden(), f"{msg}: expected visible, got hidden. widget={type(widget).__name__}"

def assert_hidden(widget, msg=""):
    """Assert widget IS hidden (i.e., setVisible(False) was called)."""
    assert widget.isHidden(), f"{msg}: expected hidden, got visible. widget={type(widget).__name__}"

def test_wall_tool_hides_entity_panel(panel):
    p, st = panel
    st.current_tool = "wall"
    p.refresh()
    assert_hidden(p._ent_gb, "Entity panel should be hidden when wall tool active")
    assert_showing(p._wall_gb, "Wall panel should be visible when wall tool active")

def test_portal_selected_shows_portal_page(panel):
    p, st = panel
    st.current_tool = "select"
    st.selected_entity_idx = 0
    p.refresh()
    assert_showing(p._ent_gb, "Entity panel should be visible")
    assert p._sub_stack.currentIndex() == 0, f"Should be page 0 (portal), got {p._sub_stack.currentIndex()}"

def test_avatar_selected_shows_ghost_page(panel):
    p, st = panel
    st.selected_entity_idx = 1
    p.refresh()
    assert_showing(p._ent_gb)
    assert p._sub_stack.currentIndex() == 1, f"Should be page 1 (avatar), got {p._sub_stack.currentIndex()}"

def test_item_selected_shows_prop_page(panel):
    p, st = panel
    st.selected_entity_idx = 2
    p.refresh()
    assert_showing(p._ent_gb)
    assert p._sub_stack.currentIndex() == 2, f"Should be page 2 (item), got {p._sub_stack.currentIndex()}"

def test_deselect_hides_entity_panel(panel):
    p, st = panel
    st.selected_entity_idx = 0
    p.refresh()
    assert_showing(p._ent_gb)
    st.selected_entity_idx = -1
    p.refresh()
    assert_hidden(p._ent_gb, "Entity panel should hide when nothing selected")

def test_switch_from_portal_to_wall_hides_entity(panel):
    p, st = panel
    st.selected_entity_idx = 0
    st.current_tool = "select"
    p.refresh()
    assert_showing(p._ent_gb)
    assert p._sub_stack.currentIndex() == 0
    st.current_tool = "wall"
    st.selected_entity_idx = -1
    p.refresh()
    assert_hidden(p._ent_gb, "Entity panel should hide when switching to wall")
    assert_showing(p._wall_gb, "Wall panel should show")

def test_no_leftover_portal_panel_on_wall_click(panel):
    """Regression: portal properties should NOT show when wall tool is active."""
    p, st = panel
    st.selected_entity_idx = 0
    st.current_tool = "select"
    p.refresh()
    st.current_tool = "wall"
    st.selected_entity_idx = -1
    p.refresh()
    assert_hidden(p._ent_gb)
    assert_showing(p._wall_gb)
    # QStackedWidget is child of _ent_gb; hidden implicitly when parent is hidden
    assert p._ent_gb.isHidden(), "Entity panel must be hidden"

def test_wall_tool_clears_entity_selection(panel):
    """Regression: switching to wall tool must clear selected_entity_idx so entity panel hides."""
    p, st = panel
    # Select portal first
    st.selected_entity_idx = 0
    st.current_tool = "select"
    p.refresh()
    assert not p._ent_gb.isHidden(), "Entity panel should show when portal selected"
    # Switch to wall — this is what _set_tool does
    st.current_tool = "wall"
    st.selected_entity_idx = -1  # _set_tool clears this for non-entity tools
    p.refresh()
    assert p._ent_gb.isHidden(), "Entity panel MUST hide when wall tool active"
    assert not p._wall_gb.isHidden(), "Wall panel MUST show"

def test_only_one_panel_visible_at_any_time(panel):
    """Exclusive visibility: entity, wall, spawn — only ONE at a time."""
    p, st = panel

    # Wall tool
    st.current_tool = "wall"; st.selected_entity_idx = -1
    if hasattr(st, '_wall_selected'): st._wall_selected = True
    p.refresh()
    assert not p._wall_gb.isHidden(), "Wall panel should show"
    assert p._ent_gb.isHidden(), "Entity panel should hide"
    assert p._spawn_gb.isHidden(), "Spawn panel should hide"

    # Entity selected (portal)
    st.current_tool = "select"; st.selected_entity_idx = 0
    if hasattr(st, '_wall_selected'): st._wall_selected = False
    p.refresh()
    assert not p._ent_gb.isHidden(), "Entity panel should show"
    assert p._wall_gb.isHidden(), "Wall panel should hide"
    assert p._spawn_gb.isHidden(), "Spawn panel should hide"

    # Spawn tool
    st.current_tool = "spawn"; st.selected_entity_idx = -1
    if hasattr(st, '_wall_selected'): st._wall_selected = False
    p.refresh()
    assert not p._spawn_gb.isHidden(), "Spawn panel should show"
    assert p._ent_gb.isHidden(), "Entity panel should hide"
    assert p._wall_gb.isHidden(), "Wall panel should hide"
