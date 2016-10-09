from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.utilities import get_image_path


class PlaylistPage(QWidget):

    def initialize_with_playlist(self, playlist):
        self.playlist = playlist
        self.window().playlist_name_label.setText(playlist["name"])
        self.window().playlist_num_items_label.setText("%d items" % len(playlist["torrents"]))
        self.window().playlist_back_button.setIcon(QIcon(get_image_path('page_back.png')))

        items = []
        for result in playlist['torrents']:
            items.append((ChannelTorrentListItem, result))
        self.window().playlist_torrents_list.set_data_items(items)
