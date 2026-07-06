"""GhostEngine 地图编辑器 — 属性面板。"""
import math
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)
from . import helpers as helper
from .model import EditorState, CmdEntity, CmdWallColor, CmdWallTex, CmdEntityProps, CmdSceneColor

class PropertyPanel(QWidget):
    def __init__(self, state: EditorState, undo_stack, parent=None):
        super().__init__(parent)
        self.state = state; self._undo_stack = undo_stack; self._ent_original = None
        self.setMinimumWidth(220); ly = QVBoxLayout(self)

        self._scene_gb = QGroupBox("场景", self); sfl = QFormLayout(self._scene_gb)
        self._sky_top_btn = QPushButton(); self._sky_top_btn.setFixedSize(60, 28); self._sky_top_btn.clicked.connect(lambda: self._pick_scene_color("sky_top")); sfl.addRow("天空顶部:", self._sky_top_btn)
        self._sky_bottom_btn = QPushButton(); self._sky_bottom_btn.setFixedSize(60, 28); self._sky_bottom_btn.clicked.connect(lambda: self._pick_scene_color("sky_bottom")); sfl.addRow("天空底部:", self._sky_bottom_btn)
        self._floor_btn = QPushButton(); self._floor_btn.setFixedSize(60, 28); self._floor_btn.clicked.connect(lambda: self._pick_scene_color("floor")); sfl.addRow("地板:", self._floor_btn)
        ly.addWidget(self._scene_gb)
        self._scene_gb.hide()  # 已移至左侧栏
        self._wall_gb = QGroupBox("墙壁属性"); fl = QVBoxLayout(self._wall_gb)
        self._wall_type_btns = []; wt_row = QHBoxLayout()
        for wt, col, name in [(1, (100,100,150),"石墙"), (2, (50,200,100),"绿墙"), (3, (139,69,19),"木板"), (4, (70,130,180),"钢铁"), (5, (150,50,50),"砖墙"), (6, (50,150,150),"玻璃"), (7, (160,140,60),"金墙"), (8, (60,60,60),"暗墙")]:
            btn = QPushButton(name); btn.setFixedHeight(24)
            btn.setStyleSheet(f"QPushButton {{ background-color:rgb({col[0]},{col[1]},{col[2]}); color:{'white' if sum(col)<400 else 'black'}; border:1px solid #555; font-size:10px; }} QPushButton:checked {{ border:2px solid #0af; }}")
            btn.setCheckable(True); btn.clicked.connect(lambda c, w=wt: self._pick_wall_type(w))
            self._wall_type_btns.append((btn, wt)); wt_row.addWidget(btn)
        fl.addLayout(wt_row)
        wpf = QFormLayout(); self._wall_color_btn = QPushButton(); self._wall_color_btn.setFixedSize(48,24); self._wall_color_btn.clicked.connect(self._pick_wall_color); wpf.addRow("颜色:", self._wall_color_btn)
        tr = QHBoxLayout(); self._wall_tex_edit = QLineEdit(); self._wall_tex_edit.setPlaceholderText("贴图.png"); self._wall_tex_edit.editingFinished.connect(self._on_wall_tex_changed); tr.addWidget(self._wall_tex_edit)
        btn = QPushButton("…"); btn.setFixedWidth(24); btn.clicked.connect(self._browse_wall_tex); tr.addWidget(btn); wpf.addRow("贴图:", tr); fl.addLayout(wpf)
        ly.addWidget(self._wall_gb)

        self._spawn_gb = QGroupBox("起点"); sfl = QFormLayout(self._spawn_gb)
        self._spawn_dir_btns = []; sd_row = QHBoxLayout()
        for angle, label in [(0.0,"→东"), (math.pi/2,"↓南"), (math.pi,"←西"), (math.pi*3/2,"↑北")]:
            btn = QPushButton(label); btn.setFixedHeight(24)
            btn.setStyleSheet("QPushButton { background-color:#1a3a5c; color:#ccc; border:1px solid #555; font-size:10px; } QPushButton:checked { border:2px solid #0af; }")
            btn.setCheckable(True); btn.clicked.connect(lambda c, a=angle: self._pick_spawn_dir(a))
            self._spawn_dir_btns.append((btn, angle)); sd_row.addWidget(btn)
        sfl.addRow("朝向:", sd_row); ly.addWidget(self._spawn_gb)
        self._spawn_gb.setVisible(False)

        self._ent_gb = QGroupBox("实体"); efl = QFormLayout(self._ent_gb); efl.setVerticalSpacing(2); efl.setContentsMargins(4, 4, 4, 4)
        # ── 通用字段 ──
        xy_row = QHBoxLayout(); self._ent_x = QDoubleSpinBox(); self._ent_x.setFixedHeight(22); self._ent_x.setRange(0,100); self._ent_x.setDecimals(1); self._ent_x.setSingleStep(0.5); self._ent_x.valueChanged.connect(self._on_ent_changed); xy_row.addWidget(self._ent_x)
        self._ent_y = QDoubleSpinBox(); self._ent_y.setFixedHeight(22); self._ent_y.setRange(0,100); self._ent_y.setDecimals(1); self._ent_y.setSingleStep(0.5); self._ent_y.valueChanged.connect(self._on_ent_changed); xy_row.addWidget(self._ent_y); efl.addRow("位置:", xy_row)
        sz_row = QHBoxLayout(); self._ent_size = QSpinBox(); self._ent_size.setFixedHeight(22); self._ent_size.setRange(10,2000); self._ent_size.setValue(150); self._ent_size.valueChanged.connect(self._on_ent_changed); sz_row.addWidget(self._ent_size)
        self._ent_width = QDoubleSpinBox(); self._ent_width.setFixedHeight(22); self._ent_width.setRange(0.01,5); self._ent_width.setDecimals(2); self._ent_width.setSingleStep(0.1); self._ent_width.setValue(0.2); self._ent_width.valueChanged.connect(self._on_ent_changed); sz_row.addWidget(self._ent_width); efl.addRow("3D:", sz_row)
        etr = QHBoxLayout(); self._ent_tex = QLineEdit(); self._ent_tex.setFixedHeight(22); self._ent_tex.setPlaceholderText("贴图.png"); self._ent_tex.editingFinished.connect(self._on_ent_changed); etr.addWidget(self._ent_tex)
        eb = QPushButton("…"); eb.setFixedSize(24,22); eb.clicked.connect(self._browse_ent_tex); etr.addWidget(eb); efl.addRow("贴图:", etr)
        self._ent_occlusion = QComboBox(); self._ent_occlusion.setFixedHeight(22); self._ent_occlusion.addItem("中心遮挡","center"); self._ent_occlusion.addItem("逐列遮挡","per_column"); self._ent_occlusion.currentIndexChanged.connect(self._on_ent_changed); efl.addRow("遮挡:", self._ent_occlusion)
        # ── 子面板容器（传送门/精灵/物品，互斥显示）──
        self._sub_stack = QStackedWidget()
        self._sub_stack.currentChanged.connect(self._on_stack_page_changed)

        self._portal_page = QWidget(); ptfl = QFormLayout(self._portal_page); ptfl.setVerticalSpacing(2); ptfl.setContentsMargins(0, 0, 0, 0)
        self._portal_id_label = QLabel(""); self._portal_id_label.setStyleSheet("color:#888;font-size:10px;"); ptfl.addRow("ID:", self._portal_id_label)
        self._portal_target_combo = QComboBox(); self._portal_target_combo.setFixedHeight(22); self._portal_target_combo.activated.connect(self._on_portal_target_activated); self._portal_target_combo.highlighted.connect(self._on_portal_combo_highlighted); ptfl.addRow("目标传送门:", self._portal_target_combo)
        self._portal_hint = QLabel(""); self._portal_hint.setStyleSheet("color:#fa0;font-size:10px;"); ptfl.addRow(self._portal_hint)
        self._sub_stack.addWidget(self._portal_page)  # index 0
        # Page 1: 精灵
        self._ghost_gb = QGroupBox("精灵属性"); gfl = QFormLayout(self._ghost_gb); gfl.setVerticalSpacing(2); gfl.setContentsMargins(4, 4, 4, 4)
        self._ent_facing = QComboBox(); self._ent_facing.setFixedHeight(22); self._ent_facing.addItem("→东", 0.0); self._ent_facing.addItem("↓南", math.pi/2); self._ent_facing.addItem("←西", math.pi); self._ent_facing.addItem("↑北", math.pi*3/2); self._ent_facing.currentIndexChanged.connect(self._on_ent_changed); gfl.addRow("朝向:", self._ent_facing)
        self._ent_name = QLineEdit(); self._ent_name.setFixedHeight(22); self._ent_name.setPlaceholderText("精灵名"); self._ent_name.editingFinished.connect(self._on_ent_changed); gfl.addRow("名称:", self._ent_name)
        self._ent_owner = QLineEdit(); self._ent_owner.setFixedHeight(22); self._ent_owner.setPlaceholderText("归属"); self._ent_owner.editingFinished.connect(self._on_ent_changed); gfl.addRow("归属:", self._ent_owner)
        self._chk_use_facing = QCheckBox("使用朝向贴图"); self._chk_use_facing.toggled.connect(self._on_ent_changed); self._chk_use_facing.toggled.connect(self._on_facing_toggled); gfl.addRow(self._chk_use_facing)
        fw = QWidget(); ftr = QHBoxLayout(fw); ftr.setContentsMargins(0,0,0,0); self._tex_front = QLineEdit(); self._tex_front.setFixedHeight(22); self._tex_front.setPlaceholderText("正面贴图.png"); self._tex_front.editingFinished.connect(self._on_ent_facing_tex); ftr.addWidget(self._tex_front)
        fb = QPushButton("…"); fb.setFixedSize(24,22); fb.clicked.connect(lambda: self._browse_facing_tex("front")); ftr.addWidget(fb); self._tex_front_w = fw; gfl.addRow(" 前:", fw)
        bw = QWidget(); btr = QHBoxLayout(bw); btr.setContentsMargins(0,0,0,0); self._tex_back = QLineEdit(); self._tex_back.setFixedHeight(22); self._tex_back.setPlaceholderText("背面贴图.png"); self._tex_back.editingFinished.connect(self._on_ent_facing_tex); btr.addWidget(self._tex_back)
        bb = QPushButton("…"); bb.setFixedSize(24,22); bb.clicked.connect(lambda: self._browse_facing_tex("back")); btr.addWidget(bb); self._tex_back_w = bw; gfl.addRow(" 后:", bw)
        lw = QWidget(); ltr = QHBoxLayout(lw); ltr.setContentsMargins(0,0,0,0); self._tex_left = QLineEdit(); self._tex_left.setFixedHeight(22); self._tex_left.setPlaceholderText("左侧贴图.png"); self._tex_left.editingFinished.connect(self._on_ent_facing_tex); ltr.addWidget(self._tex_left)
        lb = QPushButton("…"); lb.setFixedSize(24,22); lb.clicked.connect(lambda: self._browse_facing_tex("left")); ltr.addWidget(lb); self._tex_left_w = lw; gfl.addRow(" 左:", lw)
        rw = QWidget(); rtr = QHBoxLayout(rw); rtr.setContentsMargins(0,0,0,0); self._tex_right = QLineEdit(); self._tex_right.setFixedHeight(22); self._tex_right.setPlaceholderText("右侧贴图.png"); self._tex_right.editingFinished.connect(self._on_ent_facing_tex); rtr.addWidget(self._tex_right)
        rb = QPushButton("…"); rb.setFixedSize(24,22); rb.clicked.connect(lambda: self._browse_facing_tex("right")); rtr.addWidget(rb); self._tex_right_w = rw; gfl.addRow(" 右:", rw)
        self._sub_stack.addWidget(self._ghost_gb)  # index 1
        # Page 2: 物品
        self._prop_gb = QGroupBox("物品属性"); pfl = QFormLayout(self._prop_gb); pfl.setVerticalSpacing(2); pfl.setContentsMargins(4, 4, 4, 4)
        self._chk_pickup = QCheckBox("可拾取"); self._chk_pickup.toggled.connect(self._on_ent_changed); self._chk_pickup.toggled.connect(self._on_pickup_toggled); pfl.addRow(self._chk_pickup)
        self._ent_pickup_label = QLineEdit(); self._ent_pickup_label.setFixedHeight(22); self._ent_pickup_label.setPlaceholderText("例如：卷轴"); self._ent_pickup_label.editingFinished.connect(self._on_ent_changed); pfl.addRow("拾取标签:", self._ent_pickup_label)
        self._ent_capture_for = QLineEdit(); self._ent_capture_for.setFixedHeight(22); self._ent_capture_for.setPlaceholderText("留空=公开 * =任何人 名字=定向"); self._ent_capture_for.editingFinished.connect(self._on_ent_changed); pfl.addRow("捕获对象:", self._ent_capture_for)
        self._chk_invisible = QCheckBox("隐形"); self._chk_invisible.toggled.connect(self._on_ent_changed)
        chk_row = QHBoxLayout(); chk_row.addWidget(self._chk_invisible); pfl.addRow("标志:", chk_row)
        self._chk_float = QCheckBox("悬浮"); self._chk_float.toggled.connect(self._on_ent_changed); self._chk_pulse = QCheckBox("脉动"); self._chk_pulse.toggled.connect(self._on_ent_changed); self._chk_rotation = QCheckBox("旋转"); self._chk_rotation.toggled.connect(self._on_ent_changed)
        anim_row = QHBoxLayout(); anim_row.addWidget(self._chk_float); anim_row.addWidget(self._chk_pulse); anim_row.addWidget(self._chk_rotation); pfl.addRow("动画:", anim_row)
        self._sub_stack.addWidget(self._prop_gb)  # index 2
        efl.addRow(self._sub_stack)
        # 删除按钮
        self._ent_del = QPushButton("删除实体"); self._ent_del.setFixedHeight(24); self._ent_del.clicked.connect(self._on_delete_entity); efl.addRow(self._ent_del)
        ly.addWidget(self._ent_gb)
        self._ent_gb.setVisible(False)  # 初始隐藏，等待 refresh 控制
        ly.addStretch()
        self.refresh()

    def refresh(self):
        st = self.state
        for key, btn in [("sky_top", self._sky_top_btn), ("sky_bottom", self._sky_bottom_btn), ("floor", self._floor_btn)]:
            c = st.colors.get(key, [128, 128, 128])
            if isinstance(c, list) and len(c) == 3:
                btn.setStyleSheet(f"background-color:rgb({c[0]},{c[1]},{c[2]});border:1px solid #555;")
        # ── Exclusive visibility: only ONE panel at a time ──
        sel = st.selected_entity_idx
        show_ent = st.current_tool in ("avatar", "item", "portal") or (0 <= sel < len(st.entities))
        show_wall = st.current_tool == "wall" or getattr(st, '_wall_selected', False)
        show_spawn = st.current_tool == "spawn"
        # Priority: entity > wall > spawn
        if show_ent:
            self._ent_gb.setVisible(True); self._wall_gb.setVisible(False); self._spawn_gb.setVisible(False)
        elif show_wall:
            self._ent_gb.setVisible(False); self._wall_gb.setVisible(True); self._spawn_gb.setVisible(False)
        elif show_spawn:
            self._ent_gb.setVisible(False); self._wall_gb.setVisible(False); self._spawn_gb.setVisible(True)
        else:
            self._ent_gb.setVisible(False); self._wall_gb.setVisible(False); self._spawn_gb.setVisible(False)
        self._sync_wall_btns()
        if show_ent and 0 <= sel < len(st.entities):
            e = st.entities[sel]
            kind = e.get("kind", "item")
            is_avatar = kind == "avatar"
            is_portal = kind == "portal" or st.current_tool == "portal"
            if is_portal: self._ent_gb.setTitle("传送门属性")
            elif is_avatar: self._ent_gb.setTitle("精灵属性")
            else: self._ent_gb.setTitle("物品属性")
            # Only sync fields from entity when selection changes, not every tick
            changed = getattr(self, '_last_entity_idx', -1) != sel
            if changed:
                self._last_entity_idx = sel
                self._ent_x.blockSignals(True);self._ent_x.setValue(e["x"]);self._ent_x.blockSignals(False)
                self._ent_y.blockSignals(True);self._ent_y.setValue(e["y"]);self._ent_y.blockSignals(False)
                self._ent_size.blockSignals(True);self._ent_size.setValue(e.get("size_3d",150));self._ent_size.blockSignals(False)
                self._ent_width.blockSignals(True);self._ent_width.setValue(e.get("width_3d",0.2));self._ent_width.blockSignals(False)
                self._ent_tex.setText(e.get("texture",""))
                self._ent_occlusion.blockSignals(True);i=self._ent_occlusion.findData(e.get("occlusion","center"))
                if i>=0:self._ent_occlusion.setCurrentIndex(i)
                self._ent_occlusion.blockSignals(False)
                self._ent_owner.blockSignals(True);self._ent_owner.setText(e.get("owner",""));self._ent_owner.blockSignals(False)
                self._chk_use_facing.blockSignals(True);self._chk_use_facing.setChecked(e.get("use_facing",False));self._chk_use_facing.blockSignals(False)
                self._ent_facing.setVisible(True)
                self._ent_facing.blockSignals(True);fi=self._ent_facing.findData(e.get("facing",0.0))
                if fi>=0:self._ent_facing.setCurrentIndex(fi); self._ent_facing.blockSignals(False)
                ft_vis=e.get("use_facing",False)
                tx=e.get("textures",{})
                for d,w,wrap in [("front",self._tex_front,self._tex_front_w),("back",self._tex_back,self._tex_back_w),("left",self._tex_left,self._tex_left_w),("right",self._tex_right,self._tex_right_w)]:
                    w.blockSignals(True);w.setText(tx.get(d,""));w.blockSignals(False)
                    wrap.setVisible(ft_vis)
                self._chk_pickup.blockSignals(True);self._chk_pickup.setChecked(e.get("pickup",False));self._chk_pickup.blockSignals(False)
                pu_vis=e.get("pickup",False)
                self._ent_pickup_label.setVisible(pu_vis)
                self._ent_pickup_label.blockSignals(True);self._ent_pickup_label.setText(e.get("pickup_label",""));self._ent_pickup_label.blockSignals(False)
                self._ent_capture_for.blockSignals(True);self._ent_capture_for.setText(e.get("capture_for",""));self._ent_capture_for.blockSignals(False)
                self._chk_invisible.blockSignals(True);self._chk_invisible.setChecked(e.get("invisible",False));self._chk_invisible.blockSignals(False)
                anim=e.get("anim",{})
                self._chk_float.blockSignals(True);self._chk_float.setChecked("float" in anim);self._chk_float.blockSignals(False)
                self._chk_pulse.blockSignals(True);self._chk_pulse.setChecked("pulse" in anim);self._chk_pulse.blockSignals(False)
                self._chk_rotation.blockSignals(True);self._chk_rotation.setChecked("rotation" in anim);self._chk_rotation.blockSignals(False)
            # portal fields — refresh combo every tick, but skip if popup is open
            pt = e.get("portal_target") or {}
            self._portal_id_label.setText(f"ID: {e.get('id', '(未分配)')}")
            if not self._portal_target_combo.view().isVisible():
                self._populate_portal_combo(e, pt)
            # Switch stacked sub-panel
            if is_portal:
                self._sub_stack.setCurrentIndex(0)
            elif is_avatar:
                self._sub_stack.setCurrentIndex(1)
            else:
                self._sub_stack.setCurrentIndex(2)
            if self._ent_original is None:
                self._ent_original = dict(e)
        elif show_ent:
            if st.current_tool == "portal":
                self._ent_gb.setTitle("新传送门")
                self._sub_stack.setCurrentIndex(0)
            elif st.current_tool == "avatar":
                self._ent_gb.setTitle("新精灵")
                self._sub_stack.setCurrentIndex(1)
            else:
                self._ent_gb.setTitle("新物品")
                self._sub_stack.setCurrentIndex(2)
        else:
            if self._ent_original is not None: self._commit_entity_change()


    def _commit_entity_change(self):
        """Commit pending entity property edits to the undo stack."""
        if self._ent_original is None:
            return
        st = self.state; sel = st.selected_entity_idx
        if sel < 0 or sel >= len(st.entities):
            self._ent_original = None
            return
        new_state = dict(st.entities[sel])
        if self._ent_original != new_state:
            self._undo_stack.push(CmdEntityProps(st, sel, dict(self._ent_original), new_state))
        self._ent_original = None

    def _on_stack_page_changed(self, _idx: int):
        """Resize the stacked widget to match the current page's height."""
        page = self._sub_stack.currentWidget()
        if page:
            h = page.sizeHint().height()
            self._sub_stack.setFixedHeight(h)
    def _pick_wall_type(self, wall_type: int):
        self.state.selected_wall_type = wall_type
        self._sync_wall_btns()

    def _sync_wall_btns(self):
        wt = self.state.selected_wall_type
        for btn, w in self._wall_type_btns:
            btn.setChecked(w == wt)
        # sync color button and texture field for the newly selected wall type
        wd = helper.wall_lookup(self.state.colors, wt)
        if wd and "color" in wd and isinstance(wd["color"], list) and len(wd["color"]) == 3:
            c = wd["color"]
            self._wall_color_btn.setStyleSheet(
                f"background-color:rgb({c[0]},{c[1]},{c[2]});border:1px solid #555;")
        else:
            self._wall_color_btn.setStyleSheet("background-color:#646496;border:1px solid #555;")
        tex = wd.get("texture", "") if wd else ""
        self._wall_tex_edit.blockSignals(True)
        self._wall_tex_edit.setText(tex)
        self._wall_tex_edit.blockSignals(False)
    def _pick_spawn_dir(self, angle: float):
        self.state.selected_spawn_angle = angle
        for btn, a in self._spawn_dir_btns:
            btn.setChecked(abs(a - angle) < 0.01)
    def _pick_wall_color(self):
        wd=helper.wall_lookup(self.state.colors, self.state.selected_wall_type)
        cur=QColor(100,100,150)
        if wd and "color" in wd and isinstance(wd["color"],list) and len(wd["color"])==3: cur=QColor(*wd["color"])
        color=QColorDialog.getColor(cur,self,"选择墙壁颜色")
        if color.isValid():
            st=self.state;ws=st.colors.setdefault("walls",{});wk=str(st.selected_wall_type)
            old=dict(ws.get(wk,{})) if wk in ws else None
            new={"color":[color.red(),color.green(),color.blue()]}
            if wk in ws and "texture" in ws[wk]: new["texture"]=ws[wk]["texture"]
            ws[wk]=new;st.modified=True
            self._undo_stack.push(CmdWallColor(st,st.selected_wall_type,old,new));self.refresh();self._trigger_auto_save()

    def _pick_scene_color(self, key):
        st = self.state
        cur_c = st.colors.get(key, [128, 128, 128])
        cur = QColor(*cur_c) if isinstance(cur_c, list) and len(cur_c) == 3 else QColor(128, 128, 128)
        color = QColorDialog.getColor(cur, self, f"选择{'天空顶部' if key=='sky_top' else '天空底部' if key=='sky_bottom' else '地板'}颜色")
        if color.isValid():
            new_c = [color.red(), color.green(), color.blue()]
            old = {key: cur_c}
            new = {key: new_c}
            st.colors[key] = new_c
            st.modified = True
            self._undo_stack.push(CmdSceneColor(st, old, new))
            self.refresh(); self._trigger_auto_save()

    def _browse_wall_tex(self):
        p,_=QFileDialog.getOpenFileName(self,"选择墙壁贴图","","图片 (*.png *.jpg *.gif);;全部 (*)")
        if p: self._wall_tex_edit.setText(p); self._on_wall_tex_changed()

    def _on_wall_tex_changed(self):
        st=self.state;wt=st.selected_wall_type;ws=st.colors.setdefault("walls",{});wk=str(wt)
        old=dict(ws.get(wk,{})) if wk in ws else None;tex=self._wall_tex_edit.text().strip()
        if wk not in ws: ws[wk]={"color":[100,100,150]}
        new=dict(ws[wk])
        if tex: new["texture"]=tex
        else: new.pop("texture",None)
        ws[wk]=new;st.modified=True;self._undo_stack.push(CmdWallTex(st,wt,old,new));self._trigger_auto_save()

    def _browse_ent_tex(self):
        p,_=QFileDialog.getOpenFileName(self,"选择实体贴图","","图片 (*.png *.jpg *.gif);;全部 (*)")
        if p: self._ent_tex.setText(p); self._on_ent_changed()



    # ═══════════════════════════════════════════════════════════
    # Portal target system
    # ═══════════════════════════════════════════════════════════

    def _on_portal_target_activated(self, idx: int):
        if idx < 0: return
        st = self.state; sel = st.selected_entity_idx
        if sel < 0 or sel >= len(st.entities): return
        e = st.entities[sel]
        if e.get("kind") != "portal": return
        data = self._portal_target_combo.itemData(idx)
        if isinstance(data, dict) and data.get("id"):
            self._pair_portal(e, data["id"], data.get("map", ""))
        else:
            self._unpair_portal(e)
        self._update_portal_hint(e)
        self._on_ent_changed()
        self._highlight_on_canvas(None, False)

    def _pair_portal(self, source, target_id, target_map):
        st = self.state
        smap = os.path.basename(st.map_path or "")
        sid = source.get("id", "")
        if not sid: return
        # If already paired with someone else, break that old pairing first
        old = source.get("portal_target") or {}
        if isinstance(old, dict) and old.get("portal_id") and old.get("portal_id") != target_id:
            self._unpair_portal(source)
        source["portal_target"] = {"portal_id": target_id, "map": target_map}
        st.modified = True
        if target_map == smap:
            for ent in st.entities:
                if ent.get("id") == target_id and ent.get("kind") == "portal":
                    ent["portal_target"] = {"portal_id": sid, "map": smap}
                    st.modified = True
                    return
        else:
            self._write_cross_map(target_map, target_id, sid, smap)
    def _unpair_portal(self, source):
        st = self.state
        sid = source.get("id", "")
        smap = os.path.basename(st.map_path or "")
        old = source.get("portal_target") or {}
        oid = old.get("portal_id", "") if isinstance(old, dict) else ""
        omap = old.get("map", "") if isinstance(old, dict) else ""
        source["portal_target"] = None
        st.modified = True
        if oid and omap == smap:
            for ent in st.entities:
                if ent.get("id") == oid and ent.get("kind") == "portal":
                    ent["portal_target"] = None
                    st.modified = True
                    break
        if oid and omap and omap != smap:
            self._clear_cross_map_ref(omap, oid, sid, smap)
        from .model import break_all_references_to_portal
        break_all_references_to_portal(st.project_dir, sid, smap)

    def _write_cross_map(self, tmap, tid, sid, smap):
        import json
        p = os.path.join(self.state.project_dir, tmap)
        if not os.path.isfile(p): return
        try:
            with open(p, "r", encoding="utf-8") as f: data = json.load(f)
        except Exception: return
        for e in data.get("entities", []):
            if e.get("id") == tid and e.get("kind") == "portal":
                e["portal_target"] = {"portal_id": sid, "map": smap}
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                except Exception: pass
                return

    def _clear_cross_map_ref(self, tmap, tid, sid, smap):
        import json
        p = os.path.join(self.state.project_dir, tmap)
        if not os.path.isfile(p): return
        try:
            with open(p, "r", encoding="utf-8") as f: data = json.load(f)
        except Exception: return
        for e in data.get("entities", []):
            if e.get("id") != tid or e.get("kind") != "portal": continue
            pt = e.get("portal_target") or {}
            if isinstance(pt, dict) and pt.get("portal_id") == sid \
               and pt.get("map", "") == smap:
                e["portal_target"] = None
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                except Exception: pass
            return

    # ── Combo ──

    def _populate_portal_combo(self, current_entity, current_pt):
        from .model import load_map_portals, list_project_maps, collect_all_portal_targets
        st = self.state
        sid = current_entity.get("id", "")
        smap = os.path.basename(st.map_path or "")
        paired_set = collect_all_portal_targets(st.project_dir)
        self._portal_target_combo.blockSignals(True)
        self._portal_target_combo.clear()
        self._portal_target_combo.addItem("(未选择)", None)
        maps = list_project_maps(st.project_dir)
        if st.map_path and not any(os.path.basename(m) == smap for m in maps):
            maps.insert(0, st.map_path)
        for mp in maps:
            mn = os.path.basename(mp)
            portals = ([e for e in st.entities if e.get("kind") == "portal"]
                       if mn == smap else load_map_portals(mp))
            for p in portals:
                pid = p.get("id", "")
                if pid == sid and mn == smap: continue
                paired = (pid, mn) in paired_set or (pid, "") in paired_set
                label = f"[{mn}] {pid} [已配对]" if paired else f"[{mn}] {pid}"
                self._portal_target_combo.addItem(label,
                    {"id": pid, "map": mn, "x": p.get("x",0), "y": p.get("y",0), "paired": paired})
                if paired:
                    row = self._portal_target_combo.count() - 1
                    self._portal_target_combo.setItemData(row, QColor(128, 128, 128), Qt.ForegroundRole)
        tid = current_pt.get("portal_id", "") if isinstance(current_pt, dict) else ""
        tmap = current_pt.get("map", "") if isinstance(current_pt, dict) else ""
        if tid:
            for i in range(self._portal_target_combo.count()):
                d = self._portal_target_combo.itemData(i)
                if isinstance(d, dict) and d.get("id") == tid and d.get("map","") == tmap:
                    self._portal_target_combo.setCurrentIndex(i); break
            else:
                self._portal_target_combo.addItem(
                    f"[⚠已删除] {tid}", {"id": tid, "map": tmap, "x": 0, "y": 0})
                self._portal_target_combo.setCurrentIndex(self._portal_target_combo.count()-1)
        self._portal_target_combo.setMaxVisibleItems(max(10, self._portal_target_combo.count()))
        self._portal_target_combo.blockSignals(False)
        self._update_portal_hint(current_entity)

    # ── Highlight ──

    def _on_portal_combo_highlighted(self, index: int):
        view = self._portal_target_combo.view()
        if view and not getattr(self, '_popup_filter_installed', False):
            view.installEventFilter(self); self._popup_filter_installed = True
        if index < 0: self._highlight_on_canvas(None, False); return
        d = self._portal_target_combo.itemData(index)
        if isinstance(d, dict) and d.get("map","") == os.path.basename(self.state.map_path or ""):
            self._highlight_on_canvas(d, False)
        else:
            self._highlight_on_canvas(None, False)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Hide: self._highlight_on_canvas(None, False)
        return super().eventFilter(obj, event)

    def _highlight_on_canvas(self, pos, paired=False):
        w = self.parent()
        while w:
            if hasattr(w, '_grid'): w._grid.set_portal_highlight(pos, paired); return
            w = w.parent()

    def _update_portal_hint(self, entity):
        pt = entity.get("portal_target")
        if not pt or not isinstance(pt, dict) or not pt.get("portal_id"):
            self._portal_hint.setText("⚠ 此传送门未设置目标")
        else:
            self._portal_hint.setText("")
    def _on_ent_changed(self):
        st=self.state;sel=st.selected_entity_idx
        if sel<0 or sel>=len(st.entities): return
        e=st.entities[sel]
        e["x"]=self._ent_x.value();e["y"]=self._ent_y.value()
        e["size_3d"]=self._ent_size.value();e["width_3d"]=self._ent_width.value()
        e["texture"] = self._ent_tex.text().strip()
        e["occlusion"] = self._ent_occlusion.currentData()
        e["kind"] = e.get("kind", st.current_tool if st.current_tool in ("avatar","item","portal") else "item")
        anim={}
        if self._chk_float.isChecked(): anim["float"]={"speed":0.003,"amp":0.05}
        if self._chk_pulse.isChecked(): anim["pulse"]={"speed":0.005,"amp":0.1}
        if self._chk_rotation.isChecked(): anim["rotation"]={"speed":0.001}
        e["anim"]=anim;st.modified=True
        e["facing"] = self._ent_facing.currentData()
        e["use_facing"] = self._chk_use_facing.isChecked()
        e["invisible"] = self._chk_invisible.isChecked()
        e["name"] = self._ent_name.text().strip()
        e["owner"] = self._ent_owner.text().strip()
        e["capture_for"] = self._ent_capture_for.text().strip()
        e["pickup"] = self._chk_pickup.isChecked()
        e["pickup_label"] = self._ent_pickup_label.text().strip()
        # portal fields — portal_target is set via combo in _on_portal_target_changed
        # No need to sync portal_map text field here; the combo carries the full target data
        new_state=dict(e)
        if self._ent_original != new_state:
            self._undo_stack.push(CmdEntityProps(st, sel, dict(self._ent_original), new_state))
            # Force save immediately
            self._trigger_auto_save()

    def _trigger_auto_save(self):
        """Walk parent chain to find EditorWindow and call _auto_save."""
        w = self.parent()
        while w:
            if hasattr(w, '_auto_save'):
                w._auto_save()
                return
            w = w.parent()
    def _on_delete_entity(self):
        st=self.state;sel=st.selected_entity_idx
        if 0<=sel<len(st.entities):
            old=dict(st.entities[sel]);st.entities.pop(sel);st.selected_entity_idx=-1;st.modified=True
            self._undo_stack.push(CmdEntity(st,sel,old,None))
            self._trigger_auto_save()

    def _on_facing_toggled(self, checked):
        for w in [self._tex_front_w, self._tex_back_w, self._tex_left_w, self._tex_right_w]:
            w.setVisible(checked)

    def _on_pickup_toggled(self, checked):
        self._ent_pickup_label.setVisible(checked)
    def _on_ent_facing_tex(self):
        st = self.state; sel = st.selected_entity_idx
        if sel < 0 or sel >= len(st.entities): return
        e = st.entities[sel]
        tx = e.setdefault("textures", {})
        for d, w in [("front", self._tex_front), ("back", self._tex_back), ("left", self._tex_left), ("right", self._tex_right)]:
            v = w.text().strip()
            if v: tx[d] = v
            elif d in tx: del tx[d]
        st.modified = True

    def _browse_facing_tex(self, direction: str):
        p, _ = QFileDialog.getOpenFileName(self, f"选择朝向贴图", "", "图片 (*.png *.jpg *.gif);;全部 (*)")
        if p:
            w = {"front": self._tex_front, "back": self._tex_back, "left": self._tex_left, "right": self._tex_right}.get(direction)
            if w: w.setText(p)
            self._on_ent_facing_tex()
