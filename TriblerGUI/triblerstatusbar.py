
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QStatusBar, QHBoxLayout
from TriblerGUI.utilities import format_size


class TriblerStatusBar(QStatusBar):
    def __init__(self, parent):
        super(QStatusBar, self).__init__(parent)

        self.free_diskspace = QLabel(self)
        self.free_diskspace.setStyleSheet("color: #eee")
        self.free_diskspace.setText("Free space: -")
        self.free_diskspace.setAlignment(Qt.AlignLeft)
        self.addWidget(self.free_diskspace)

    def set_free_space(self, free_space):
        self.free_diskspace.setText("Free space: " + format_size(free_space))
