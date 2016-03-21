from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget
from TriblerGUI.utilities import format_size


class ChannelTorrentListItem(QWidget):
    def __init__(self, parent, torrent):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_torrent_list_item.ui', self)

        self.channel_torrent_name.setText(torrent["name"])
        if torrent["length"] is None:
            self.torrent_size.setText("Size: -")
        else:
            self.torrent_size.setText("Size: %s" % format_size(float(torrent["length"])))

        self.torrent_type.setText("File type: %s" % torrent["category"])

        placeholder_pix = QPixmap("images/download.png")
        placeholder_pix = placeholder_pix.scaled(self.torrent_download_button.width(), self.torrent_download_button.height(), Qt.KeepAspectRatio)
        self.torrent_download_button.setIcon(QIcon(placeholder_pix))
        self.torrent_download_button.setIconSize(QSize(self.torrent_download_button.width(), self.torrent_download_button.height()))
