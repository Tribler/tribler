from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size


class ChannelTorrentListItem(QWidget):
    """
    This class is responsible for managing the item in the torrents list of a channel.
    """

    def __init__(self, parent, torrent, show_controls=False, on_remove_clicked=None):
        super(QWidget, self).__init__(parent)

        self.torrent_info = torrent

        uic.loadUi('qt_resources/channel_torrent_list_item.ui', self)

        self.channel_torrent_name.setText(torrent["name"])
        if torrent["size"] is None:
            self.channel_torrent_description.setText("Size: -")
        else:
            self.channel_torrent_description.setText("Size: %s" % format_size(float(torrent["size"])))

        self.channel_torrent_category.setText(torrent["category"])
        self.thumbnail_widget.initialize(torrent["name"], 24)

        self.torrent_play_button.clicked.connect(self.on_play_button_clicked)

        if not show_controls:
            self.remove_control_button_container.setHidden(True)
        else:
            self.control_buttons_container.setHidden(True)

        if on_remove_clicked is not None:
            self.remove_torrent_button.clicked.connect(lambda: on_remove_clicked(self))

    def on_play_button_clicked(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s" % self.torrent_info["infohash"],
                                         self.on_play_request_done, method='PUT')

    def on_play_request_done(self, result, response_code):
        self.window().clicked_menu_button_video_player()
        self.window().video_player_page.set_torrent(self.torrent_info)
        self.window().left_menu_playlist.set_loading()
