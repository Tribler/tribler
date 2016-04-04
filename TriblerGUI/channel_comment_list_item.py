from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer, QTimeLine, QPropertyAnimation
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect, QSizePolicy


class ChannelCommentListItem(QWidget):
    def __init__(self, parent, level):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_comment_list_item.ui', self)
        comment_left_margin = self.layout().itemAt(0)
        comment_left_margin.changeSize(15 * level + 10, 0, QSizePolicy.Fixed, QSizePolicy.Fixed)
