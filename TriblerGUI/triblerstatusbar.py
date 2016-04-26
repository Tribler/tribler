# coding=utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QStatusBar, QHBoxLayout
from TriblerGUI.utilities import format_size


class TriblerStatusBar(QStatusBar):
    def __init__(self, parent):
        super(QStatusBar, self).__init__(parent)

        self.free_diskspace = QLabel(self)
        self.free_diskspace.setStyleSheet("color: #eee")
        self.free_diskspace.setText("↓ 0.0 kb/s  ↑ 0.0 kb/s")
        self.free_diskspace.setAlignment(Qt.AlignRight)
        self.addWidget(self.free_diskspace, 1)
