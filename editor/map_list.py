"""GhostEngine 地图编辑器 — 地图列表面板（可折叠）。"""

import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox, QInputDialog, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget, QFileDialog, QMessageBox,
)


class MapList(QListWidget):
    """支持 Delete 键删除的列表。"""
    delete_requested = Signal(int)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            row = self.currentRow()
            if row >= 0:
                self.delete_requested.emit(row)
                return
        super().keyPressEvent(event)
class MapListPanel(QWidget):
    """项目目录中的地图文件列表。双击加载。"""
    map_selected = Signal(str)

    def __init__(self, project_dir: str, parent=None):
        super().__init__(parent)
        self._project_dir = project_dir
        ly = QVBoxLayout(self)

        gb = QGroupBox("地图列表")
        ily = QVBoxLayout(gb)
        self._list = MapList()
        self._list.setMaximumHeight(120); self._list.setMinimumHeight(60)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.delete_requested.connect(self._delete_file)
        ily.addWidget(self._list)

        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.refresh)
        ily.addWidget(btn_refresh)

        btn_open = QPushButton("打开其他...")
        btn_open.clicked.connect(self._open_other)
        ily.addWidget(btn_open)

        ly.addWidget(gb)
        self.refresh()

    def refresh(self):
        self._list.clear()
        if not os.path.isdir(self._project_dir):
            return
        for f in sorted(os.listdir(self._project_dir)):
            if f.endswith(".json") and f != "presets.json":
                item = QListWidgetItem(f)
                item.setData(Qt.UserRole, os.path.join(self._project_dir, f))
                self._list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.map_selected.emit(path)

    def _open_other(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开地图", "", "JSON 文件 (*.json);;全部 (*)")
        if path:
            self.map_selected.emit(path)

    def _delete_file(self, row: int):
        item = self._list.item(row)
        if not item:
            return
        path = item.data(Qt.UserRole)
        fname = item.text()
        r = QMessageBox.question(self, "删除地图", f"确定删除 {fname}？", QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            try:
                os.unlink(path)
                self.refresh()
            except OSError as e:
                QMessageBox.critical(self, "错误", f"删除失败:\n{e}")
