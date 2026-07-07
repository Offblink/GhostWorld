"""GhostEngine 地图编辑器 — 主窗口。"""

import os, sys
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut, QUndoStack
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter, QStatusBar, QTextBrowser, QToolBar, QVBoxLayout, QWidget,
)
from ghostengine import load_raw, save_raw
from .model import EditorState, CmdEntity, auto_pair_portals, generate_portal_id
from .canvas import GridCanvas
from .props import PropertyPanel
from .templates import TEMPLATES
from .map_list import MapListPanel


class EditorWindow(QMainWindow):
    def __init__(self, project_dir="."):
        super().__init__()
        self.setWindowTitle("GhostWorld — 未命名")
        self.state = EditorState(project_dir=project_dir)
        self.resize(1280, 800)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.indexChanged.connect(self._on_undo_changed)

        # 菜单
        mb = self.menuBar()
        fm = mb.addMenu("文件(&F)")
        for label, slot, key in [("新建(&N)", self._new_map, QKeySequence.New),
                                   ("打开(&O)...", self._open, QKeySequence.Open),
                                   ("保存(&S)", self._prompt_save, QKeySequence.Save),
                                   ("另存为(&A)...", self._save_as, QKeySequence("Ctrl+Shift+S")),
                                   ("用预览器打开(&L)", self._run_with_runner, QKeySequence("Ctrl+R"))]:
            a = QAction(label, self); a.triggered.connect(slot); a.setShortcut(key); fm.addAction(a)
        fm.addSeparator()
        a = QAction("退出(&X)", self); a.setShortcut(QKeySequence.Quit); a.triggered.connect(self.close); fm.addAction(a)

        em = mb.addMenu("编辑(&E)")
        a = self.undo_stack.createUndoAction(self, "撤销(&U)")
        a.setShortcut(QKeySequence.Undo); em.addAction(a)
        a = self.undo_stack.createRedoAction(self, "重做(&R)")
        a.setShortcut(QKeySequence.Redo); em.addAction(a)
        em.addSeparator()
        a = QAction("调整网格大小(&G)...", self); a.triggered.connect(self._resize_grid); em.addAction(a)
        hm = mb.addMenu("帮助(&H)")
        a = QAction("使用说明(&U)", self); a.triggered.connect(self._show_help); hm.addAction(a)

        # 工具栏
        tb = self.addToolBar("工具")
        self._tool_btns = {}
        for name, label in [("select", "选择"), ("wall", "墙壁"), ("avatar", "精灵"), ("item", "物品"), ("spawn", "起点"), ("portal", "传送门")]:
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda c, n=name: self._set_tool(n))
            tb.addAction(act); self._tool_btns[name] = act
        self._tool_btns["select"].setChecked(True)
        sp = QWidget(); sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); tb.addWidget(sp)
        a = QAction("▶ 预览", self); a.triggered.connect(self._run_with_runner); tb.addAction(a)
        self._map_list = MapListPanel(project_dir)
        self._map_list.map_selected.connect(self._load_map)
        # 左侧栏：始终可见
        left_w = QWidget(); left_ly = QVBoxLayout(left_w); left_ly.setContentsMargins(2, 2, 2, 2)
        left_ly.addWidget(self._map_list)
        # 场景颜色
        sc_gb = QGroupBox("场景", left_w)
        sc_fl = QFormLayout(sc_gb)
        self._sky_top_btn = QPushButton(); self._sky_top_btn.setFixedSize(50, 22); self._sky_top_btn.clicked.connect(self._pick_sky_top); sc_fl.addRow("天空顶:", self._sky_top_btn)
        self._sky_bottom_btn = QPushButton(); self._sky_bottom_btn.setFixedSize(50, 22); self._sky_bottom_btn.clicked.connect(self._pick_sky_bottom); sc_fl.addRow("天空底:", self._sky_bottom_btn)
        self._floor_btn = QPushButton(); self._floor_btn.setFixedSize(50, 22); self._floor_btn.clicked.connect(self._pick_floor); sc_fl.addRow("地板:", self._floor_btn)
        left_ly.addWidget(sc_gb)
        # 小地图
        mm_gb = QGroupBox("小地图", left_w)
        mm_fl = QFormLayout(mm_gb)
        self._chk_mm_enabled = QCheckBox("启用小地图")
        self._chk_mm_enabled.setChecked(True)
        self._chk_mm_enabled.toggled.connect(self._on_mm_toggled)
        mm_fl.addRow(self._chk_mm_enabled)
        left_ly.addWidget(mm_gb)
        # ── 测试/游戏开关 ──
        tg_gb = QGroupBox("测试", left_w); tg_fl = QFormLayout(tg_gb)
        self._chk_g_ghosts = QCheckBox("G 雾效"); self._chk_g_ghosts.toggled.connect(self._on_test_changed); tg_fl.addRow(self._chk_g_ghosts)
        left_ly.addWidget(tg_gb)
        left_ly.addStretch()

        # 中央布局
        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central); outer.setContentsMargins(0, 0, 0, 0)
        hly = QHBoxLayout(); hly.setContentsMargins(4, 4, 4, 4)
        splitter = QSplitter(Qt.Horizontal); splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background-color: #555; border: 1px solid #333; }")
        splitter.addWidget(left_w)
        self._grid = GridCanvas(self.state, self.undo_stack); splitter.addWidget(self._grid)
        right = QVBoxLayout()
        self._props = PropertyPanel(self.state, self.undo_stack); right.addWidget(self._props, 1)
        rw = QWidget(); rw.setLayout(right); splitter.addWidget(rw)
        splitter.setSizes([180, 750, 320]); hly.addWidget(splitter, 1); outer.addLayout(hly, 1)
        self._status = QStatusBar(); self.setStatusBar(self._status)
        self._refresh_timer = QTimer(self); self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(200)  # refresh UI every 200ms
        self._autosave_timer = QTimer(self); self._autosave_timer.timeout.connect(self._tick_autosave)
        self._autosave_timer.start(3000)  # auto-save every 3 seconds when dirty

        # 自动打开上次的地图
        last = os.path.join(project_dir, ".last_map")
        if os.path.isfile(last):
            try:
                with open(last) as f:
                    prev = f.read().strip()
                if os.path.isfile(prev):
                    self._load_map(prev)
                    return
            except: pass
        self._status.showMessage("欢迎！新建地图或打开已有地图文件开始编辑。")
        self._sync_mm(); self._sync_scene(); self._sync_test()
    def _refresh_ui(self):
        self._grid.refresh(); self._props.refresh()
        self._sync_scene(); self._sync_test()
        cp = self._grid.mapFromGlobal(self.cursor().pos())
        gx = cp.x() // GridCanvas.CELL_SIZE; gy = cp.y() // GridCanvas.CELL_SIZE
        gw, gh = self.state.grid.shape
        if 0 <= gx < gw and 0 <= gy < gh:
            self._status.showMessage(
                f"({gx},{gy}) 墙壁:{int(self.state.grid[gx,gy])} 工具:{self.state.current_tool} 实体:{len(self.state.entities)}")

    def _on_undo_changed(self, _idx: int):
        """Called on every undo/redo/modification. Mark dirty, refresh UI."""
        self.state.modified = True  # set by commands already, but ensure
        self._update_title()
        if hasattr(self, '_grid'):
            self._grid._dirty = True
            self._grid.refresh()
        if hasattr(self, '_props'):
            self._props.refresh()

    def _auto_save(self):
        """Save current state to disk. Auto-generate filename for new maps."""
        st = self.state
        if not st.map_path:
            i = 0
            while True:
                name = f"untitled_{i}.json" if i > 0 else "untitled.json"
                path = os.path.join(st.project_dir, name)
                if not os.path.exists(path):
                    break
                i += 1
            st.map_path = path
        self._save_to(st.map_path)

    def _tick_autosave(self):
        """Periodic auto-save — only writes if dirty and named."""
        if self.state.modified and self.state.map_path:
            self._auto_save()

    def _prompt_save(self):
        """Save. If map is unnamed, prompt for filename first."""
        st = self.state
        if st.map_path:
            self._save_to(st.map_path)
        else:
            self._save_as()

    def _save_as(self):
        """Save with file dialog — always prompts for filename."""
        st = self.state
        default = st.map_path or os.path.join(st.project_dir, "untitled.json")
        path, _ = QFileDialog.getSaveFileName(self, "另存为", default, "JSON 文件 (*.json);;全部 (*)")
        if path:
            st.map_path = path
            self._save_to(path)

    def _set_tool(self, name):
        self.state.current_tool = name
        for n, a in self._tool_btns.items(): a.setChecked(n == name)
        self.state.selected_entity_idx = -1
        if hasattr(self.state, '_wall_selected'):
            self.state._wall_selected = False
        self._props.refresh()

    def _new_map(self):
        dlg = QDialog(self); dlg.setWindowTitle("新建地图 — 选择模板")
        ly = QFormLayout(dlg); cb = QComboBox(); cb.addItems(list(TEMPLATES.keys())); ly.addRow("模板:", cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); ly.addRow(bb)
        if dlg.exec() != QDialog.Accepted: return
        tmpl = TEMPLATES[cb.currentText()]()
        self.state.grid = np.array(tmpl["grid"], dtype=int).T
        ps = tmpl.get("player_spawn", {}); self.state.player_spawn = (ps.get("x",7.5), ps.get("y",7.5), ps.get("angle",0))
        ex = tmpl.get("exit")
        # migrate old exit format to portal entity
        if ex and isinstance(ex, dict):
            portal_ent = {
                "x": float(ex.get("x", 0)) + 0.5, "y": float(ex.get("y", 0)) + 0.5,
                "kind": "portal",
                "portal_target": {
                    "x": float(ex.get("x", 0)) + 0.5, "y": float(ex.get("y", 0)) + 0.5,
                },
                "size_3d": 150, "width_3d": 0.2, "occlusion": "center",
            }
            if ex.get("target_map"):
                portal_ent["portal_target"]["map"] = ex["target_map"]
            tmpl_entities = tmpl.get("entities", [])
            tmpl_entities.append(portal_ent)
            self.state.entities = tmpl_entities
        else:
            self.state.entities = tmpl.get("entities", [])
        self.state.map_path = None; self.state.modified = False; self.undo_stack.clear()
        self._update_title()
        self._grid._dirty = True; self._grid.resize_to_grid(); self._grid.refresh(); self._props.refresh(); self._sync_mm(); self._sync_scene()

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(self, "打开地图", self.state.project_dir, "JSON 文件 (*.json);;全部 (*)")
        if p: self._load_map(p)

    def _load_map(self, path):
        self._status.showMessage("加载中..."); QApplication.processEvents()
        try: raw = load_raw(path)
        except Exception as e: QMessageBox.critical(self, "错误", f"加载失败:\n{e}"); return
        if not isinstance(raw, dict): QMessageBox.critical(self, "错误", "不是有效的地图文件。"); return
        st = self.state; st.grid = np.array(raw.get("grid",[[1]]), dtype=int).T
        ps = raw.get("player_spawn", {})
        st.player_spawn = (ps.get("x", 7.5), ps.get("y", 7.5), ps.get("angle", 0.0))
        st.entities = raw.get("entities", [])
        for e in st.entities:
            for k, v in [("kind", "item"), ("facing", 0.0), ("preset_idx", 1),
                         ("pickup", False), ("pickup_label", ""),
                         ("invisible", False), ("mm_trigger", False),
                         ("use_facing", False), ("textures", {}),
                         ("name", ""), ("owner", ""), ("metadata", {}),
                         ("capture_for", ""), ("portal_target", None), ("dialogue", "")]:
                e.setdefault(k, v)
        # backward compat: migrate old "exit" field to portal entity
        ex = raw.get("exit")
        if ex and isinstance(ex, dict):
            portal_ent = {
                "x": float(ex.get("x", 0)) + 0.5, "y": float(ex.get("y", 0)) + 0.5,
                "kind": "portal",
                "id": generate_portal_id(st.entities),
                "portal_target": None,
                "size_3d": 150, "width_3d": 0.2, "occlusion": "center",
            }
            if ex.get("text"):
                portal_ent["transition_text"] = ex["text"]
            if ex.get("duration"):
                portal_ent["transition_duration"] = ex["duration"]
            if ex.get("text_size"):
                portal_ent["transition_text_size"] = ex["text_size"]
            if ex.get("text_color"):
                portal_ent["transition_text_color"] = ex["text_color"]
            st.entities.append(portal_ent)
        st.selected_entity_idx = -1
        st.minimap = raw.get("minimap", {"mode": "always", "duration": 0})
        st.test = raw.get("test", {"g_enabled": False})
        # Ensure all 8 wall types have color definitions (merge defaults)
        _default_walls = {
            "1": {"color": [100, 100, 150]}, "2": {"color": [50, 200, 100]},
            "3": {"color": [139, 69, 19]}, "4": {"color": [70, 130, 180]},
            "5": {"color": [150, 50, 50]}, "6": {"color": [50, 150, 150]},
            "7": {"color": [160, 140, 60]}, "8": {"color": [60, 60, 60]},
        }
        st.colors.setdefault("walls", {})
        for k, v in _default_walls.items():
            st.colors["walls"].setdefault(k, v)
        st.map_path = path; st.modified = False; self.undo_stack.clear()
        self._update_title()
        self._grid._dirty = True; self._grid.resize_to_grid(); self._grid.refresh()
        self._props.refresh(); self._map_list.refresh(); self._sync_mm(); self._sync_scene()
        # Validate and clean up ghost entities (out of bounds or on walls)
        from ghostengine.mapfile import validate_entities_on_walls
        val_errors = validate_entities_on_walls(st.grid, st.entities, raw.get("player_spawn"))
        before = len(st.entities)
        gw, gh = st.grid.shape
        st.entities = [e for e in st.entities
                       if 0 <= int(e.get("x",0)) < gw and 0 <= int(e.get("y",0)) < gh]
        removed = before - len(st.entities)
        for err in val_errors:
            self._status.showMessage(f"⚠ {err}")
            print(f"[editor] ⚠ {err}")
        if removed:
            self._status.showMessage(f"🧹 已清理 {removed} 个越界实体")
            print(f"[editor] 🧹 removed {removed} out-of-bounds entities")


    def _save_to(self, path):
        st = self.state
        for e in st.entities:
            if e.get("kind") == "portal" and not e.get("id"):
                e["id"] = generate_portal_id(st.entities)
        data = {"version":3, "grid":st.grid.T.tolist(),
                "player_spawn":{"x":st.player_spawn[0],"y":st.player_spawn[1],"angle":st.player_spawn[2]},
                "entities":st.entities, "colors":st.colors, "minimap":st.minimap, "test":st.test}
        try:
            save_raw(data, path)
            st.map_path = os.path.abspath(path)
            st.modified = False
            self._update_title()
        except Exception as ex: QMessageBox.critical(self, "错误", f"保存失败:\n{ex}"); return
        auto_pair_portals(st.project_dir)
        # Apply defaults to any entities that lack them (no full reload needed)
        for e in st.entities:
            for k, v in [("kind", "item"), ("facing", 0.0),
                         ("pickup", False), ("pickup_label", ""),
                         ("invisible", False), ("mm_trigger", False),
                         ("use_facing", False), ("textures", {}),
                         ("name", ""), ("owner", ""), ("metadata", {}),
                         ("capture_for", ""), ("portal_target", None), ("dialogue", "")]:
                e.setdefault(k, v)
        try:
            with open(os.path.join(self.state.project_dir, ".last_map"), "w") as f:
                f.write(st.map_path)
        except: pass
        # Refresh property panel to reflect auto-pairing changes
        if hasattr(self, '_props'):
            self._props._last_portal_entity_idx = -1
            self._props.refresh()
        self._map_list.refresh()
        self._status.showMessage(f"已保存: {os.path.basename(path)}")

    def _update_title(self):
        """Update window title to reflect current map name."""
        st = self.state
        name = os.path.basename(st.map_path) if st.map_path else "未命名"
        mod = " *" if st.modified else ""
        self.setWindowTitle(f"GhostEngine — {name}{mod}")
    def _show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("GhostEngine 地图编辑器 — 使用说明")
        dlg.resize(640, 520)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("""
<h2>🪟 界面布局</h2>
<p><b>左侧栏</b> — 地图列表（双击加载，Delete 删除）、场景颜色、小地图设置。<br>
<b>中央</b> — 网格画布，所见即所得。<br>
<b>右侧栏</b> — 选中实体或墙壁后的属性面板（互斥显示，同一时刻仅显示一种）。<br>
<b>底部状态栏</b> — 当前坐标、工具、实体数量；加载/保存提示。<br>
<b>标题栏</b> — 显示当前地图名，未保存修改标注 <code>*</code>。</p>

<h2>🔧 工具栏</h2>
<table>
<tr><td><b>选择</b></td><td>点击墙壁选中类型（右侧切换颜色）；点击实体查看/编辑属性。右键擦除。</td></tr>
<tr><td><b>墙壁</b></td><td>左键放置/覆盖墙壁（当前选中类型 1–8）。左键拖拽连续放置。右键擦除。</td></tr>
<tr><td><b>物品</b></td><td>放置物品。右侧设置可拾取、拾取标签、动画（悬浮/脉动/旋转）、贴图、遮挡模式。</td></tr>
<tr><td><b>精灵</b></td><td>放置静态精灵（联机时玩家和 Agent 会自动创建精灵，编辑器主要用于放置 NPC 或装饰）。</td></tr>
<tr><td><b>起点</b></td><td>设置玩家出生位置和朝向（不能放在墙壁上）。</td></tr>
<tr><td><b>传送门</b></td><td>放置传送门。右侧下拉框列出<b>项目内所有地图的全部传送门</b>，格式为 <code>[地图名] 传送门ID</code>。不能放在墙壁上。</td></tr>
</table>

<h2>🔗 传送门系统</h2>
<ol>
<li>在任意地图上放置传送门（自动分配 ID）。</li>
<li>选中传送门，在右侧 <b>目标传送门</b> 下拉框中直接选取目标——<b>无需手动指定地图</b>。</li>
<li>选中后<b>立即双向配对</b>：对方传送门自动回指（跨地图写入磁盘）。</li>
<li><b>更换目标</b>时，旧的配对自动断开，旧目标变为未选择。</li>
<li>选择 <b>(未选择)</b> 取消配对——对方传送门同步取消（跨地图双向）。</li>
<li>删除传送门时，所有指向它的配对自动断开。</li>
<li>下拉框中 <b>已配对</b> 传送门灰显并标注 [已配对]；悬停时画布高亮（同图青色，跨图不高亮）。</li>
</ol>
<h2>🚫 墙壁互斥与越界清理</h2>
<ul>
<li>物品、精灵、传送门、出生点<b>不能放在墙壁格子上</b>——点击墙壁时工具无响应。</li>
<li>已有实体的位置<b>不会被覆盖</b>——状态栏提示"此位置已被占用"，需先右键擦除再放置。</li>
<li>加载地图时自动检测：实体与墙壁重叠 → <code>⚠</code> 警告；越界幽灵实体 → <code>🧹</code> 自动清理。</li>
</ul>

<h2>🖱 画布操作</h2>
<table>
<tr><td><b>左键</b></td><td>当前工具主操作（空位放置；墙壁覆盖；已有实体提示占用）</td></tr>
</table>

<h2>💾 保存</h2>
<ul>
<li>编辑器<b>每 3 秒自动保存</b>已命名地图的修改。</li>
<li><b>Ctrl+S</b> — 手动保存；未命名地图弹出命名对话框。</li>
<li><b>Ctrl+Shift+S</b> — 另存为，始终弹出对话框。</li>
<li>撤销 (Ctrl+Z) 和重做 (Ctrl+Y) 提供安全网。</li>
<li>关闭窗口或启动预览前强制即时保存。</li>
</ul>

<h2>⌨ 快捷键</h2>
<table>
<tr><td>Ctrl+N</td><td>新建地图（选择模板）</td></tr>
<tr><td>Ctrl+O</td><td>打开地图</td></tr>
<tr><td>Ctrl+S</td><td>保存（未命名时弹出对话框）</td></tr>
<tr><td>Ctrl+Shift+S</td><td>另存为…</td></tr>
<tr><td>Ctrl+Z / Ctrl+Y</td><td>撤销 / 重做</td></tr>
<tr><td>Ctrl+R</td><td>用预览器打开当前地图</td></tr>
<tr><td>Delete</td><td>删除选中实体或墙壁</td></tr>
</table>

<h2>🎮 预览器操作</h2>
<table>
<tr><td>W / S</td><td>前进 / 后退</td></tr>
<tr><td>A / D</td><td>左平移 / 右平移</td></tr>
<tr><td>← / →</td><td>左右转向</td></tr>
<tr><td>鼠标移动</td><td>转动视角</td></tr>
<tr><td>M</td><td>小地图开关</td></tr>
<tr><td>F</td><td>全屏切换</td></tr>
<tr><td>Space</td><td>暂停</td></tr>
<tr><td>Esc</td><td>退出</td></tr>
</table>

<h2>🗺 地图格式</h2>
<p>地图文件为 JSON（v3），存储在 <code>examples/</code> 目录。<br>
编辑器自动加载同目录下所有 <code>.json</code> 地图，传送门跨图配对无需手动指定路径。<br>
编辑时画布与预览器使用一致的坐标方向（引擎内部自动转置）。</p>
""")
        layout.addWidget(browser)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        layout.addWidget(bb)
        dlg.exec()

    def _run_with_runner(self):
        if self.state.modified or not self.state.map_path:
            self._auto_save()
        if self.state.map_path:
            import ghostengine
            r = os.path.join(os.path.dirname(os.path.abspath(ghostengine.__file__)), "runner.pyw")
            self._status.showMessage(f"正在启动 {os.path.basename(self.state.map_path)}...")
            import subprocess
            try:
                subprocess.Popen([sys.executable, r, os.path.abspath(self.state.map_path)], cwd=os.path.dirname(r))
            except Exception as e:
                QMessageBox.critical(self, "启动失败", f"无法启动查看器:\n{e}")

    def _resize_grid(self):
        dlg = QDialog(self); dlg.setWindowTitle("调整网格大小"); ly = QFormLayout(dlg)
        w, h = self.state.grid.shape
        sw = QSpinBox(); sw.setRange(5, 200); sw.setValue(w); ly.addRow("宽:", sw)
        sh = QSpinBox(); sh.setRange(5, 200); sh.setValue(h); ly.addRow("高:", sh)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); ly.addRow(bb)
        if dlg.exec() != QDialog.Accepted: return
        nw, nh = sw.value(), sh.value()
        new = np.full((nw, nh), 0, dtype=int)
        new[:min(w,nw), :min(h,nh)] = self.state.grid[:min(w,nw), :min(h,nh)]
        self.state.grid = new; self.state.modified = True
        self._grid._dirty = True; self._grid.resize_to_grid(); self._grid.refresh()
        self._status.showMessage(f"网格已调整为 {nw}×{nh}")

    def _sync_test(self):
        t = self.state.test
        self._chk_g_ghosts.blockSignals(True); self._chk_g_ghosts.setChecked(t.get("g_enabled", False)); self._chk_g_ghosts.blockSignals(False)

    def _on_test_changed(self):
        self.state.test["g_enabled"] = self._chk_g_ghosts.isChecked()
        self.state.modified = True

    def _sync_mm(self):
        mm = self.state.minimap
        enabled = mm.get("mode", "always") == "always"
        self._chk_mm_enabled.blockSignals(True)
        self._chk_mm_enabled.setChecked(enabled)
        self._chk_mm_enabled.blockSignals(False)

    def _on_mm_toggled(self, checked: bool):
        self.state.minimap["mode"] = "always" if checked else "disabled"
        self.state.modified = True
    def _sync_scene(self):
        st = self.state
        for key, btn in [("sky_top", self._sky_top_btn), ("sky_bottom", self._sky_bottom_btn), ("floor", self._floor_btn)]:
            c = st.colors.get(key, [128, 128, 128])
            if isinstance(c, list) and len(c) == 3:
                btn.setStyleSheet(f"background-color:rgb({c[0]},{c[1]},{c[2]});border:1px solid #555;")

    def _pick_sky_top(self): self._do_pick_scene("sky_top")
    def _pick_sky_bottom(self): self._do_pick_scene("sky_bottom")
    def _pick_floor(self): self._do_pick_scene("floor")

    def _do_pick_scene(self, key):
        cur_c = self.state.colors.get(key, [128, 128, 128])
        cur = QColor(*cur_c) if isinstance(cur_c, list) and len(cur_c) == 3 else QColor(128, 128, 128)
        color = QColorDialog.getColor(cur, self)
        if color.isValid():
            self.state.colors[key] = [color.red(), color.green(), color.blue()]
            self.state.modified = True
            self._sync_scene()
    def closeEvent(self, event):
        if self.state.modified:
            self._auto_save()
        event.accept()
