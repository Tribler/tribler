from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget


class ChannelTorrentListItem(QWidget):
    def __init__(self, parent, torrent):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_torrent_list_item.ui', self)

        self.channel_torrent_name.setText(torrent["name"])

        placeholder_pix = QPixmap("images/play.png")
        placeholder_pix = placeholder_pix.scaled(self.torrent_action_button.width(), self.torrent_action_button.height())
        self.torrent_action_button.setIcon(QIcon(placeholder_pix))
        self.torrent_action_button.setIconSize(QSize(self.torrent_action_button.width(), self.torrent_action_button.height()))
