"""GhostEngine 地图编辑器 — 2-D 网格画布。"""

import math, os, pygame
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter, QUndoStack
from PySide6.QtWidgets import QWidget
from . import helpers as helper
from .model import EditorState, CmdWall, CmdEntity, CmdSpawn

class GridCanvas(QWidget):
    CELL_SIZE = 24

    def __init__(self, state, undo_stack, parent=None):
        super().__init__(parent)
        self.state = state; self.undo_stack = undo_stack
        self.setMouseTracking(True); self._dirty = True
        self.setMinimumSize(400, 400); self.resize_to_grid()
        self._pygame_inited = False; self._pm = None

    def _init_pygame(self):
        if not self._pygame_inited:
            if not pygame.get_init(): pygame.init()
            self._pygame_inited = True

    def _build_pixmap(self):
        self._init_pygame()
        st = self.state; w, h = st.grid.shape
        pw, ph = w * self.CELL_SIZE, h * self.CELL_SIZE
        surf = pygame.Surface((pw, ph)); surf.fill((20, 20, 30))
        for x in range(w):
            for y in range(h):
                r = pygame.Rect(x * self.CELL_SIZE, y * self.CELL_SIZE, self.CELL_SIZE - 1, self.CELL_SIZE - 1)
                val = int(st.grid[x, y])
                if val == 0:
                    pygame.draw.rect(surf, (30, 30, 40), r); pygame.draw.rect(surf, (20, 20, 30), r, 1)
                else:
                    wd = helper.wall_lookup(st.colors, val)
                    col = (100, 100, 150)
                    if wd and "color" in wd and isinstance(wd["color"], list) and len(wd["color"]) == 3:
                        col = tuple(wd["color"])
                    pygame.draw.rect(surf, col, r)
        spx = int(st.player_spawn[0] * self.CELL_SIZE); spy = int(st.player_spawn[1] * self.CELL_SIZE)
        pygame.draw.circle(surf, (0, 150, 255), (spx, spy), 6)
        ang = st.player_spawn[2]; ex2 = spx + int(math.cos(ang) * 8); ey2 = spy + int(math.sin(ang) * 8)
        pygame.draw.line(surf, (255, 255, 255), (spx, spy), (ex2, ey2), 2)
        for idx, ent in enumerate(st.entities):
            epx = int(ent["x"] * self.CELL_SIZE); epy = int(ent["y"] * self.CELL_SIZE)
            kind = ent.get("kind", "item")
            if kind == "portal":
                col = (0, 220, 220) if idx == st.selected_entity_idx else (0, 180, 180)
                pygame.draw.circle(surf, col, (epx, epy), 6, 2 if idx == st.selected_entity_idx else 0)
                try:
                    font = pygame.font.SysFont("SimHei", 8)
                    label = font.render("门", True, (0, 220, 220))
                    surf.blit(label, label.get_rect(center=(epx, epy)))
                except: pass
            else:
                col = (255, 100, 255) if idx == st.selected_entity_idx else (255, 100, 100)
                pygame.draw.circle(surf, col, (epx, epy), 5, 2 if idx == st.selected_entity_idx else 0)
        raw = pygame.image.tostring(surf, "RGB")
        self._pm = QPixmap.fromImage(QImage(raw, pw, ph, QImage.Format_RGB888))

    def resize_to_grid(self):
        st = self.state
        self.setMinimumSize(st.grid.shape[0] * self.CELL_SIZE, st.grid.shape[1] * self.CELL_SIZE)
        self._dirty = True

    def refresh(self):
        if self._dirty: self._build_pixmap(); self._dirty = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.fillRect(self.rect(), Qt.darkGray)
        if self._pm:
            dx = (self.width() - self._pm.width()) // 2; dy = (self.height() - self._pm.height()) // 2
            p.drawPixmap(dx, dy, self._pm)
        # draw portal highlight overlay
        hl = getattr(self, '_portal_highlight', None)
        if hl and self._pm:
            gw, gh = self.state.grid.shape
            px, py = hl.get("x", 0), hl.get("y", 0)
            if 0 <= int(px) < gw and 0 <= int(py) < gh:
                dx = (self.width() - self._pm.width()) // 2
                dy = (self.height() - self._pm.height()) // 2
                hx = int(px * self.CELL_SIZE) + dx
                hy = int(py * self.CELL_SIZE) + dy
                r = self.CELL_SIZE // 2 + 2
                paired = getattr(self, '_portal_highlight_paired', False)
                pen_c = QColor(255, 80, 80, 220) if paired else QColor(0, 255, 255, 200)
                brush_c = QColor(255, 80, 80, 60) if paired else QColor(0, 255, 255, 60)
                p.setPen(pen_c)
                p.setBrush(brush_c)
                p.drawEllipse(hx - r, hy - r, r * 2, r * 2)

    def _screen_to_grid(self, pos):
        if self._pm is None: return 0, 0
        dx = (self.width() - self._pm.width()) // 2; dy = (self.height() - self._pm.height()) // 2
        x = (pos.x() - dx) // self.CELL_SIZE; y = (pos.y() - dy) // self.CELL_SIZE
        gw, gh = self.state.grid.shape
        return max(0, min(gw - 1, x)), max(0, min(gh - 1, y))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            st = self.state; sel = st.selected_entity_idx
            if 0 <= sel < len(st.entities):
                old = dict(st.entities[sel])
                if old.get("kind") == "portal" and old.get("id"):
                    self._unpair_deleted_portal(old["id"])
                st.entities.pop(sel); st.selected_entity_idx = -1
                st.modified = True; self.undo_stack.push(CmdEntity(st, sel, old, None))
                self._dirty = True; self.refresh()
                return
            # 无实体选中 → 擦除最后点击的墙壁格
            if hasattr(st, '_last_click'):
                gx, gy = st._last_click
                old = int(st.grid[gx, gy])
                if old != 0:
                    st.grid[gx, gy] = 0; st.modified = True
                    self.undo_stack.push(CmdWall(st, gx, gy, old, 0))
                    st._wall_selected = False
                self._dirty = True; self.refresh()
            return

    def mousePressEvent(self, event):
        self.setFocus(); self._dirty = True
        gx, gy = self._screen_to_grid(event.pos()); st = self.state
        st._last_click = (gx, gy)
        if event.button() == Qt.LeftButton:
            if st.current_tool == "select":
                val = int(st.grid[gx, gy])
                if val != 0: st.selected_wall_type = val; st._wall_selected = True
                else: st._wall_selected = False
                best = -1; best_d = 999; mx, my = gx + 0.5, gy + 0.5
                for i, e in enumerate(st.entities):
                    d = math.hypot(e["x"] - mx, e["y"] - my)
                    if d < 0.8 and d < best_d: best = i; best_d = d
                st.selected_entity_idx = best
                self._notify_select()
            elif st.current_tool == "wall":
                st.selected_entity_idx = -1
                old = int(st.grid[gx, gy]); new = st.selected_wall_type
                st.grid[gx, gy] = new; st.modified = True; self.undo_stack.push(CmdWall(st, gx, gy, old, new))
            elif st.current_tool in ("avatar", "item", "portal"):
                if int(st.grid[gx, gy]) != 0: return
                best = -1; best_d = 999; cx, cy = gx + 0.5, gy + 0.5
                for i, e in enumerate(st.entities):
                    d = math.hypot(e["x"] - cx, e["y"] - cy)
                    if d < 0.8 and d < best_d: best = i; best_d = d
                if best >= 0:
                    self._show_status("此位置已被占用，请先右键移除再放置")
                else:
                    self._add_entity(cx, cy, st.current_tool)
                self._notify_select()
            elif st.current_tool == "spawn":
                if int(st.grid[gx, gy]) != 0: return
                old = st.player_spawn; st.player_spawn = (gx + 0.5, gy + 0.5, st.selected_spawn_angle)
                st.modified = True; self.undo_stack.push(CmdSpawn(st, old, st.player_spawn))
        elif event.button() == Qt.RightButton:
            # Right-click always erases wall + closest entity at this cell
            old = int(st.grid[gx, gy])
            if old != 0:
                st.grid[gx, gy] = 0; st.modified = True
                self.undo_stack.push(CmdWall(st, gx, gy, old, 0))
            self._erase_entity_at(gx + 0.5, gy + 0.5)
            st.selected_entity_idx = -1
            self._notify_select()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._dirty = True; gx, gy = self._screen_to_grid(event.pos()); st = self.state
            last = getattr(st, '_last_move_cell', None)
            if last == (gx, gy) and st.current_tool == "wall":
                return
            st._last_move_cell = (gx, gy)
            if st.current_tool == "wall":
                old = int(st.grid[gx, gy]); new = st.selected_wall_type
                if old != new: st.grid[gx, gy] = new; st.modified = True; self.undo_stack.push(CmdWall(st, gx, gy, old, new))
            self.refresh()
        elif event.buttons() & Qt.RightButton:
            self._dirty = True; gx, gy = self._screen_to_grid(event.pos()); st = self.state
            last = getattr(st, '_last_move_cell', None)
            if last == (gx, gy):
                return
            st._last_move_cell = (gx, gy)
            old = int(st.grid[gx, gy])
            if old != 0:
                st.grid[gx, gy] = 0; st.modified = True
                self.undo_stack.push(CmdWall(st, gx, gy, old, 0))
            self.refresh()

    def _notify_select(self):
        p = self.parent()
        while p is not None:
            if hasattr(p, '_props'): p._props.refresh(); break
            p = p.parent()

    def _entity_config(self, kind="item"):
        from .presets import DEFAULT_PRESETS
        if kind == "avatar":
            return dict(DEFAULT_PRESETS[0]["entity"])
        if kind == "portal":
            from .model import generate_portal_id
            return {"kind": "portal", "id": "", "portal_target": None, "size_3d": 150, "width_3d": 0.2, "occlusion": "center"}
        return dict(DEFAULT_PRESETS[1]["entity"])
    def _add_entity(self, x, y, kind="item"):
        cfg = self._entity_config(kind)
        if kind == "portal" and not cfg.get("id"):
            from .model import generate_portal_id
            cfg["id"] = generate_portal_id(self.state.entities)
        ent = {"x": x, "y": y, **cfg}; idx = len(self.state.entities)
        self.state.entities.append(ent); self.state.selected_entity_idx = idx
        self.state.modified = True
        self.undo_stack.push(CmdEntity(self.state, idx, None, dict(ent)))
    def _show_status(self, msg: str):
        """Show a message in the editor's status bar via parent chain."""
        p = self.parent()
        while p:
            if hasattr(p, '_status'):
                p._status.showMessage(msg)
                return
            p = p.parent()

    def _erase_entity_at(self, x, y):
        st = self.state; best, best_d = -1, 999
        for i, e in enumerate(st.entities):
            d = math.hypot(e["x"] - x, e["y"] - y)
            if d < 0.8 and d < best_d: best = i; best_d = d
        if best >= 0:
            old = dict(st.entities[best])
            if old.get("kind") == "portal" and old.get("id"):
                self._unpair_deleted_portal(old["id"])
            st.entities.pop(best); st.selected_entity_idx = -1
            st.modified = True; self.undo_stack.push(CmdEntity(st, best, old, None))

    def _unpair_deleted_portal(self, portal_id: str):
        """When a portal is deleted, clear its target from any portal that references it."""
        from .model import break_all_references_to_portal
        st = self.state
        map_basename = os.path.basename(st.map_path or "")
        # Clear same-map in-memory portals that target this one
        for e in st.entities:
            pt = e.get("portal_target")
            if pt and isinstance(pt, dict) and pt.get("portal_id") == portal_id:
                e["portal_target"] = None
                st.modified = True
        # Clear cross-map references on disk
        if st.project_dir and map_basename:
            break_all_references_to_portal(st.project_dir, portal_id, map_basename)
    def set_portal_highlight(self, pos: dict | None, paired: bool = False):
        """Set a portal highlight position (or None to clear). Triggers repaint."""
        self._portal_highlight = pos
        self._portal_highlight_paired = paired
        self.update()
