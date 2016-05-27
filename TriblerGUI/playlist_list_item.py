from PyQt5 import uic
from PyQt5.QtWidgets import QWidget


class PlaylistListItem(QWidget):
    """
    This class is responsible for managing the playlist item widget.
    """

    def __init__(self, parent, playlist):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/playlist_list_item.ui', self)

        self.playlist_name.setText(playlist["name"])
        self.playlist_num_items.setText("%d items" % len(playlist["torrents"]))

        self.thumbnail_widget.initialize(playlist["name"], 24)
