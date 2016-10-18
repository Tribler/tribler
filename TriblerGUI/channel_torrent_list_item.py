from urllib import quote_plus
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.dialogs.startdownloaddialog import StartDownloadDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.tribler_window import fc_channel_torrent_list_item
from TriblerGUI.utilities import format_size, get_image_path


class ChannelTorrentListItem(QWidget, fc_channel_torrent_list_item):
    """
    This class is responsible for managing the item in the torrents list of a channel.
    """

    def __init__(self, parent, torrent, show_controls=False, on_remove_clicked=None):
        super(QWidget, self).__init__(parent)

        self.torrent_info = torrent

        self.setupUi(self)
        self.show_controls = show_controls
        self.remove_control_button_container.setHidden(True)
        self.control_buttons_container.setHidden(True)

        self.channel_torrent_name.setText(torrent["name"])
        if torrent["size"] is None:
            self.channel_torrent_description.setText("Size: -")
        else:
            self.channel_torrent_description.setText("Size: %s" % format_size(float(torrent["size"])))

        if torrent["category"]:
            self.channel_torrent_category.setText(torrent["category"])
        else:
            self.channel_torrent_category.setText("Unknown")
        self.thumbnail_widget.initialize(torrent["name"], 24)

        self.torrent_play_button.clicked.connect(self.on_play_button_clicked)
        self.torrent_download_button.clicked.connect(self.on_download_clicked)

        if on_remove_clicked is not None:
            self.remove_torrent_button.clicked.connect(lambda: on_remove_clicked(self))

    def on_download_clicked(self):
        self.dialog = StartDownloadDialog(self.window().stackedWidget, self.torrent_info)
        self.dialog.button_clicked.connect(self.on_start_download_action)
        self.dialog.show()

    def on_start_download_action(self, action):
        if action == 1:
            magnet_link = quote_plus("magnet:?xt=urn:btih:%s&dn=%s" %
                                     (self.torrent_info["infohash"], self.torrent_info["name"]))
            anon_hops = 1 if self.dialog.dialog_widget.anon_download_checkbox.isChecked() else 0
            safe_seeding = 1 if self.dialog.dialog_widget.safe_seed_checkbox.isChecked() else 0
            post_data = str("uri=%s&anon_hops=%d&safe_seeding=%d" % (magnet_link, anon_hops, safe_seeding))
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads", self.on_start_download_request_done,
                                             method='PUT', data=post_data)

        self.dialog.setParent(None)
        self.dialog = None

    def on_start_download_request_done(self, result, response_code):
        self.window().clicked_menu_button_downloads()

    def on_play_button_clicked(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s" % self.torrent_info["infohash"],
                                         self.on_play_request_done, method='PUT')

    def on_play_request_done(self, result, response_code):
        self.window().clicked_menu_button_video_player()
        self.window().video_player_page.set_torrent(self.torrent_info)
        self.window().left_menu_playlist.set_loading()

    def enterEvent(self, event):
        if not self.show_controls:
            self.remove_control_button_container.setHidden(True)
            self.control_buttons_container.setHidden(False)
            self.torrent_play_button.setIcon(QIcon(get_image_path('play.png')))
            self.torrent_download_button.setIcon(QIcon(get_image_path('downloads.png')))
        else:
            self.control_buttons_container.setHidden(True)
            self.remove_control_button_container.setHidden(False)
            self.remove_torrent_button.setIcon(QIcon(get_image_path('delete.png')))

    def leaveEvent(self, event):
        self.remove_control_button_container.setHidden(True)
        self.control_buttons_container.setHidden(True)
