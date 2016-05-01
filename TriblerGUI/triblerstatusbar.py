# coding=utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QStatusBar


class TriblerStatusBar(QStatusBar):
    """
    This class manages the status bar at the bottom of the screen.
    """

    def __init__(self, parent):
        super(QStatusBar, self).__init__(parent)

        self.download_speed_label = QLabel(self)
        self.download_speed_label.setStyleSheet("color: #eee")
        self.download_speed_label.setText("↓ 0.0 kb/s  ↑ 0.0 kb/s")
        self.download_speed_label.setAlignment(Qt.AlignRight)
        self.addWidget(self.download_speed_label, 1)
