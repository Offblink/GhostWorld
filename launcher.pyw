"""GhostEngine Metaverse Launcher — PySide6 GUI.

Select player texture, name, and owner before launching.
"""
import os, sys, json, subprocess

try:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox, QGroupBox,
    )
    from PySide6.QtCore import Qt
except ImportError:
    print("PySide6 required: pip install PySide6")
    sys.exit(1)

ROOT = os.path.dirname(os.path.abspath(__file__))
_last = os.path.join(ROOT, "examples", ".last_map")
_default = os.path.join(ROOT, "examples", "demo_metaverse.json")
DEFAULT_MAP = _default
if os.path.isfile(_last):
    try:
        with open(_last) as f:
            p = f.read().strip()
            if p and os.path.isfile(p):
                DEFAULT_MAP = p
    except: pass


class LauncherDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GhostEngine Metaverse Launcher")
        self.setFixedSize(500, 420)

        ly = QVBoxLayout(self)
        ly.setSpacing(16)
        ly.setContentsMargins(24, 20, 24, 20)


        # ── Player settings ──
        pg = QGroupBox("Player 设置")
        pfl = QFormLayout(pg)
        self._player_name = QLineEdit("player"); pfl.addRow("名称:", self._player_name)
        self._player_owner = QLineEdit("human"); pfl.addRow("归属:", self._player_owner)
        tex_row = QHBoxLayout()
        self._player_tex = QLineEdit("")
        tex_row.addWidget(self._player_tex)
        btn = QPushButton("浏览..."); btn.clicked.connect(self._browse_tex); tex_row.addWidget(btn)
        pfl.addRow("贴图:", tex_row)
        ly.addWidget(pg)

        # ── Agent settings ──
        ag = QGroupBox("Agent 设置")
        afl = QFormLayout(ag)
        self._agent_name = QLineEdit("agent"); afl.addRow("名称:", self._agent_name)
        agent_owner = QLabel("agent"); afl.addRow("归属:", agent_owner)
        atex_row = QHBoxLayout()
        self._agent_tex = QLineEdit("")
        atex_row.addWidget(self._agent_tex)
        btn2 = QPushButton("浏览..."); btn2.clicked.connect(self._browse_agent_tex); atex_row.addWidget(btn2)
        afl.addRow("贴图:", atex_row)
        ly.addWidget(ag)

        # ── Map ──
        mg = QGroupBox("地图")
        mfl = QFormLayout(mg)
        map_row = QHBoxLayout()
        self._map_path = QLineEdit(DEFAULT_MAP)
        map_row.addWidget(self._map_path)
        btn = QPushButton("浏览..."); btn.clicked.connect(self._browse_map); map_row.addWidget(btn)
        mfl.addRow("地图:", map_row)
        ly.addWidget(mg)

        ly.addStretch()
        # ── Buttons ──
        btn_row = QHBoxLayout()
        launch = QPushButton("启动元宇宙"); launch.setFixedHeight(32)
        launch.clicked.connect(self._launch); btn_row.addWidget(launch)
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject); btn_row.addWidget(cancel)
        ly.addLayout(btn_row)

    def _browse_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择贴图", "", "图片 (*.png *.jpg *.gif)")
        if p:
            self._player_tex.setText(p)
    def _browse_agent_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择贴图", "", "图片 (*.png *.jpg *.gif)")
        if p:
            self._agent_tex.setText(p)

    def _browse_map(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择地图", ROOT, "JSON (*.json)")
        if p:
            self._map_path.setText(p)

    def _launch(self):
        config = {
            "player_name": self._player_name.text() or "player",
            "player_owner": self._player_owner.text() or "human",
            "player_texture": self._player_tex.text(),
            "agent_texture": self._agent_tex.text(),
            "agent_name": self._agent_name.text() or "agent",
            "map_path": self._map_path.text() or DEFAULT_MAP,
        }
        cfg_path = os.path.join(ROOT, "metaverse", "launch_config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        self.accept()
        # launch metaverse
        subprocess.Popen([sys.executable, "-m", "metaverse.launch", config["map_path"]],
                         cwd=ROOT)


def main():
    app = QApplication(sys.argv)
    dlg = LauncherDialog()
    dlg.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
