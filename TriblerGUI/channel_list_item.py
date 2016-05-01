from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget


class ChannelListItem(QWidget):
    def __init__(self, parent, channel):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_list_item.ui', self)

        self.channel_name.setText(channel["name"])
        self.channel_info.setText("Torrents: " + str(channel["torrents"]) + ", votes: " + str(channel["votes"]))

        placeholder_pix = QPixmap("images/default-placeholder.png")
        placeholder_pix = placeholder_pix.scaled(self.channel_thumbnail.width(), self.channel_thumbnail.height(),
                                                 Qt.KeepAspectRatio)
        self.channel_thumbnail.setPixmap(placeholder_pix)
