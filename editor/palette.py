"""GhostEngine 地图编辑器 — 墙壁类型调色板（横栏）以及出生点朝向选择。"""
import math

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget
from .model import EditorState

WALL_PALETTE_COLORS = [
    (1, (100, 100, 150), "石墙"), (2, (50, 200, 100), "绿墙"),
    (3, (139, 69, 19), "木板"), (4, (70, 130, 180), "钢铁"),
    (5, (150, 50, 50), "砖墙"), (6, (50, 150, 150), "玻璃"),
    (7, (160, 140, 60), "金墙"), (8, (60, 60, 60), "暗墙"),
]


class WallPalette(QWidget):
    def __init__(self, state: EditorState, parent=None):
        super().__init__(parent)
        self.state = state
        self._window = None
        self._btns: list[QPushButton] = []
        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0); ly.setSpacing(4)
        ly.addWidget(QLabel("墙壁:"))
        for wt, col, name in WALL_PALETTE_COLORS:
            r, g, b = col
            btn = QPushButton(name)
            btn.setFixedSize(68, 28)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: rgb({r},{g},{b}); color: {'white' if sum(col)<400 else 'black'}; "
                f"border: 2px solid #444; font-size: 10px; }}"
                f"QPushButton:hover {{ border-color: #aaa; }}"
                f"QPushButton:checked {{ border-color: #0af; border-width: 3px; }}"
            )
            btn.setCheckable(True)
            btn.clicked.connect(lambda c, w=wt: self._select(w))
            ly.addWidget(btn); self._btns.append(btn)
        ly.addStretch()
        self._select(1)

    def _select(self, wall_type: int):
        self.state.selected_wall_type = wall_type
        for i, b in enumerate(self._btns):
            b.setChecked(WALL_PALETTE_COLORS[i][0] == wall_type)

    def sync_checked(self):
        wt = self.state.selected_wall_type
        for i, b in enumerate(self._btns):
            b.setChecked(WALL_PALETTE_COLORS[i][0] == wt)

SPAWN_DIRECTIONS = [
    (0.0, "→ 东"),
    (math.pi / 2, "↓ 南"),
    (math.pi, "← 西"),
    (math.pi * 3 / 2, "↑ 北"),
]


class SpawnDirectionBar(QWidget):
    """出生点朝向选择横栏，点击起点工具后显示。"""

    def __init__(self, state: EditorState, parent=None):
        super().__init__(parent)
        self.state = state
        self._btns: list[QPushButton] = []
        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0); ly.setSpacing(4)
        ly.addWidget(QLabel("朝向:"))
        for angle, label in SPAWN_DIRECTIONS:
            btn = QPushButton(label)
            btn.setFixedSize(68, 28)
            btn.setStyleSheet(
                "QPushButton { background-color: #1a3a5c; color: #ccc; "
                "border: 2px solid #444; font-size: 10px; }"
                "QPushButton:hover { border-color: #aaa; }"
                "QPushButton:checked { border-color: #0af; border-width: 3px; }"
            )
            btn.setCheckable(True)
            btn.clicked.connect(lambda c, a=angle: self._select(a))
            ly.addWidget(btn); self._btns.append(btn)
        ly.addStretch()
        self._select(0.0)

    def _select(self, angle: float):
        self.state.selected_spawn_angle = angle
        for i, b in enumerate(self._btns):
            b.setChecked(abs(SPAWN_DIRECTIONS[i][0] - angle) < 0.01)

    def sync_checked(self):
        a = self.state.selected_spawn_angle
        for i, b in enumerate(self._btns):
            b.setChecked(abs(SPAWN_DIRECTIONS[i][0] - a) < 0.01)
