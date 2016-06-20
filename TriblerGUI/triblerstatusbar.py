# coding=utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QStatusBar
from TriblerGUI.utilities import format_speed


class TriblerStatusBar(QStatusBar):
    """
    This class manages the status bar at the bottom of the screen.
    """

    def __init__(self, parent):
        super(QStatusBar, self).__init__(parent)

        self.speed_label = QLabel(self)
        self.speed_label.setStyleSheet("color: #eee")
        self.set_speeds(0, 0)
        self.speed_label.setAlignment(Qt.AlignRight)
        self.addWidget(self.speed_label, 1)

    def set_speeds(self, download, upload):
        self.speed_label.setText("↓ %s  ↑ %s" % (format_speed(download), format_speed(upload)))
