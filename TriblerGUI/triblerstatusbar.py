
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QStatusBar, QHBoxLayout


class TriblerStatusBar(QStatusBar):
    def __init__(self, parent):
        super(QStatusBar, self).__init__(parent)

        free_diskspace = QLabel(self)
        free_diskspace.setStyleSheet("color: #eee")
        free_diskspace.setText("Free space: 34.43GB")
        free_diskspace.setAlignment(Qt.AlignLeft)
        self.addWidget(free_diskspace)
