from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget


class ChannelListItem(QWidget):
    def __init__(self, parent, channel):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_list_item.ui', self)

        self.channel_name.setText(channel["name"])
        self.channel_info.setText("Torrents: " + str(channel["torrents"]))
        self.channel_num_subs_label.setText(str(channel["votes"]))
