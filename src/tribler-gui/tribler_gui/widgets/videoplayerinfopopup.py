from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QStyle, QStyleOption, QWidget

from tribler_gui.utilities import get_ui_file_path


class VideoPlayerInfoPopup(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        uic.loadUi(get_ui_file_path('video_info_popup.ui'), self)

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)
