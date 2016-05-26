from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from TriblerGUI.utilities import format_size


class ChannelTorrentListItem(QWidget):
    """
    This class is responsible for managing the item in the torrents list of a channel.
    """

    def __init__(self, parent, torrent):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_torrent_list_item.ui', self)

        self.channel_torrent_name.setText(torrent["name"])
        if torrent["length"] is None:
            self.channel_torrent_description.setText("Size: -")
        else:
            self.channel_torrent_description.setText("Size: %s" % format_size(float(torrent["length"])))

        self.channel_torrent_category.setText(torrent["category"])
        self.thumbnail_widget.initialize(torrent["name"], 24)
