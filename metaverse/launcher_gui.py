"""The GUI launcher — player/agent settings, then hand the map to the game.

`launcher.pyw` is the double-click entry, but a frozen build cannot import a
`.pyw` module, so the dialog lives in the package and both entries call `main()`.

A `.pyw` has no console: everything worth saying goes into the window.
"""
from __future__ import annotations

import json
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ._paths import app_dir, examples_dir, launch_config_file, seed_examples, startup_lines


def default_map() -> str:
    """The map to preselect: the editor's last one, else the demo (see `launch`)."""
    from .launch import default_map as _default_map

    return _default_map()


class LauncherDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GhostEngine Metaverse Launcher")
        self.setFixedSize(500, 560)

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
        self._map_path = QLineEdit(default_map())
        map_row.addWidget(self._map_path)
        btn = QPushButton("浏览..."); btn.clicked.connect(self._browse_map); map_row.addWidget(btn)
        mfl.addRow("地图:", map_row)
        ly.addWidget(mg)

        # ── 路径：这个入口是 .pyw，没有控制台，路径只能显示在窗口上 ──
        pg_paths = QGroupBox("路径")
        pv = QVBoxLayout(pg_paths)
        self._paths_label = QLabel("\n".join(startup_lines()))
        self._paths_label.setWordWrap(True)
        self._paths_label.setStyleSheet("color:#666; font-size:11px")
        self._paths_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pv.addWidget(self._paths_label)
        ly.addWidget(pg_paths)

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
        p, _ = QFileDialog.getOpenFileName(self, "选择地图", str(examples_dir()), "JSON (*.json)")
        if p:
            self._map_path.setText(p)

    def _launch(self):
        config = {
            "player_name": self._player_name.text() or "player",
            "player_owner": self._player_owner.text() or "human",
            "player_texture": self._player_tex.text(),
            "agent_texture": self._agent_tex.text(),
            "agent_name": self._agent_name.text() or "agent",
            "map_path": self._map_path.text() or default_map(),
        }
        # The game reads this file; both sides go through `_paths` so a frozen
        # install cannot end up with the launcher writing where the game never looks.
        cfg_path = launch_config_file()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        self.accept()
        subprocess.Popen(_game_command(config["map_path"]), cwd=app_dir())


def _game_command(map_path: str) -> list[str]:
    """How to start the game from here — a module in a checkout, the exe when frozen."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--play", map_path]
    return [sys.executable, "-m", "metaverse.launch", map_path]


def main():
    from ._branding import apply_qt_icon, claim_taskbar_identity

    seed_examples()           # frozen builds copy the demo maps out on first run
    claim_taskbar_identity()  # before the first window: taskbar grouping
    app = QApplication(sys.argv)
    apply_qt_icon(app)
    dlg = LauncherDialog()
    dlg.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
