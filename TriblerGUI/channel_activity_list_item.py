from PyQt5 import uic
from PyQt5.QtWidgets import QWidget


class ChannelActivityListItem(QWidget):
    def __init__(self, parent):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_activity_list_item.ui', self)
