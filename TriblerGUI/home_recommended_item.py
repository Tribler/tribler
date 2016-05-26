# coding=utf-8
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QPropertyAnimation
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class HomeRecommendedItem(QWidget):

    def __init__(self, parent):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/home_recommended_item.ui', self)

        self.thumbnail_widget.initialize("Pioneer One", 44)
