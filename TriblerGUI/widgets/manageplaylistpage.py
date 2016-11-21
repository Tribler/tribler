from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QListWidgetItem
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class ManagePlaylistPage(QWidget):
    """
    On this page, users can add or remove torrents from/to a playlist.
    """

    playlist_saved = pyqtSignal()

    def __init__(self):
        QWidget.__init__(self)

        self.channel_info = None
        self.playlist_info = None
        self.request_mgr = None

        self.torrents_in_playlist = []
        self.torrents_in_channel = []

        self.torrents_to_create = []
        self.torrents_to_remove = []

        self.pending_requests = []
        self.requests_done = 0

    def initialize(self, channel_info, playlist_info):
        self.channel_info = channel_info
        self.playlist_info = playlist_info
        self.window().edit_channel_details_manage_playlist_header.setText("Manage torrents in playlist '%s'" %
                                                                          playlist_info['name'])
        self.window().manage_channel_playlist_torrents_back.setIcon(QIcon(get_image_path('page_back.png')))

        self.window().playlist_manage_add_to_playlist.clicked.connect(self.on_add_clicked)
        self.window().playlist_manage_remove_from_playlist.clicked.connect(self.on_remove_clicked)
        self.window().edit_channel_manage_playlist_save_button.clicked.connect(self.on_save_clicked)
        self.window().manage_channel_playlist_torrents_back.clicked.connect(self.on_playlist_manage_back_clicked)

        # Load torrents in your channel
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/discovered/%s/torrents" %
                                         channel_info["identifier"], self.on_received_channel_torrents)

        self.torrents_in_playlist = []
        self.torrents_in_channel = []

        self.torrents_to_create = []
        self.torrents_to_remove = []

        self.pending_requests = []
        self.requests_done = 0

    def on_playlist_manage_back_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS)

    def update_lists(self):
        self.window().playlist_manage_in_channel_list.clear()
        self.window().playlist_manage_in_playlist_list.clear()

        for torrent in self.torrents_in_channel:
            item = QListWidgetItem(torrent["name"], self.window().playlist_manage_in_channel_list)
            item.setData(Qt.UserRole, torrent)
            self.window().playlist_manage_in_channel_list.addItem(item)

        for torrent in self.torrents_in_playlist:
            item = QListWidgetItem(torrent["name"], self.window().playlist_manage_in_playlist_list)
            item.setData(Qt.UserRole, torrent)
            self.window().playlist_manage_in_playlist_list.addItem(item)

    @staticmethod
    def remove_torrent_from_list(torrent, remove_from_list):
        index = -1
        for torrent_index in xrange(len(remove_from_list)):
            if remove_from_list[torrent_index]['infohash'] == torrent['infohash']:
                index = torrent_index
                break

        if index != -1:
            del remove_from_list[index]

    def on_received_channel_torrents(self, result):
        self.torrents_in_playlist = self.playlist_info['torrents']

        self.torrents_in_channel = []
        for torrent in result['torrents']:
            if not ManagePlaylistPage.list_contains_torrent(self.torrents_in_playlist, torrent):
                self.torrents_in_channel.append(torrent)

        self.update_lists()

    @staticmethod
    def list_contains_torrent(torrent_list, torrent):
        for playlist_torrent in torrent_list:
            if torrent['infohash'] == playlist_torrent['infohash']:
                return True
        return False

    def on_add_clicked(self):
        for item in self.window().playlist_manage_in_channel_list.selectedItems():
            torrent = item.data(Qt.UserRole)
            ManagePlaylistPage.remove_torrent_from_list(torrent, self.torrents_in_channel)
            self.torrents_in_playlist.append(torrent)

            if ManagePlaylistPage.list_contains_torrent(self.torrents_to_remove, torrent):
                ManagePlaylistPage.remove_torrent_from_list(torrent, self.torrents_to_remove)
            self.torrents_to_create.append(torrent)

        self.update_lists()

    def on_remove_clicked(self):
        for item in self.window().playlist_manage_in_playlist_list.selectedItems():
            torrent = item.data(Qt.UserRole)
            ManagePlaylistPage.remove_torrent_from_list(torrent, self.torrents_in_playlist)
            self.torrents_in_channel.append(torrent)

            if ManagePlaylistPage.list_contains_torrent(self.torrents_to_create, torrent):
                ManagePlaylistPage.remove_torrent_from_list(torrent, self.torrents_to_create)
            self.torrents_to_remove.append(torrent)

        self.update_lists()

    def on_save_clicked(self):
        self.requests_done = 0
        self.pending_requests = []
        for torrent in self.torrents_to_create:
            request = TriblerRequestManager()
            request.perform_request("channels/discovered/%s/playlists/%s/%s" %
                                    (self.channel_info["identifier"], self.playlist_info['id'],
                                     torrent['infohash']), self.on_request_done, method="PUT")
            self.pending_requests.append(request)
        for torrent in self.torrents_to_remove:
            request = TriblerRequestManager()
            request.perform_request("channels/discovered/%s/playlists/%s/%s" %
                                    (self.channel_info["identifier"], self.playlist_info['id'], torrent['infohash']),
                                    self.on_request_done, method="DELETE")
            self.pending_requests.append(request)

    def on_request_done(self, _):
        self.requests_done += 1
        if self.requests_done == len(self.pending_requests):
            self.on_requests_done()

    def on_requests_done(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS)
        self.playlist_saved.emit()
