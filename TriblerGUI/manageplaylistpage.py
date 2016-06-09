from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QListWidgetItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class ManagePlaylistPage(QWidget):

    def initialize(self, channel_info, playlist_info):
        self.channel_info = channel_info
        self.playlist_info = playlist_info
        self.window().my_channel_details_manage_playlist_header.setText("Manage torrents in playlist '%s'" % playlist_info['name'])

        self.window().playlist_manage_add_to_playlist.clicked.connect(self.on_add_clicked)
        self.window().playlist_manage_remove_from_playlist.clicked.connect(self.on_remove_clicked)
        self.window().my_channel_manage_playlist_save_button.clicked.connect(self.on_save_clicked)

        # Load torrents in your channel
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/discovered/%s/torrents" % channel_info["mychannel"]["identifier"], self.on_received_channel_torrents)

        self.torrents_in_playlist = []
        self.torrents_in_channel = []

        self.torrents_to_create = []
        self.torrents_to_remove = []

        self.requests = []

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

    def remove_torrent_from_list(self, torrent, list):
        index = -1
        for torrent_index in xrange(len(list)):
            if list[torrent_index]['infohash'] == torrent['infohash']:
                index = torrent_index
                break

        if index != -1:
            del list[index]

    def on_received_channel_torrents(self, result):
        self.torrents_in_playlist = self.playlist_info['torrents']

        self.torrents_in_channel = []
        for torrent in result['torrents']:
            if not self.list_contains_torrent(self.torrents_in_playlist, torrent):
                self.torrents_in_channel.append(torrent)

        self.update_lists()

    def list_contains_torrent(self, torrent_list, torrent):
        for playlist_torrent in torrent_list:
            if torrent['infohash'] == playlist_torrent['infohash']:
                return True
        return False

    def on_add_clicked(self):
        for item in self.window().playlist_manage_in_channel_list.selectedItems():
            torrent = item.data(Qt.UserRole)
            self.remove_torrent_from_list(torrent, self.torrents_in_channel)
            self.torrents_in_playlist.append(torrent)

            if self.list_contains_torrent(self.torrents_to_remove, torrent):
                self.remove_torrent_from_list(torrent, self.torrents_to_remove)
            self.torrents_to_create.append(torrent)

        self.update_lists()

    def on_remove_clicked(self):
        for item in self.window().playlist_manage_in_playlist_list.selectedItems():
            torrent = item.data(Qt.UserRole)
            self.remove_torrent_from_list(torrent, self.torrents_in_playlist)
            self.torrents_in_channel.append(torrent)

            if self.list_contains_torrent(self.torrents_to_create, torrent):
                self.remove_torrent_from_list(torrent, self.torrents_to_create)
            self.torrents_to_remove.append(torrent)

        self.update_lists()

    def on_save_clicked(self):
        for torrent in self.torrents_to_create:
            request = TriblerRequestManager()
            request.perform_request("channels/discovered/%s/playlists/%s/%s" % (self.channel_info["mychannel"]["identifier"], self.playlist_info['id'], torrent['infohash']), self.on_torrent_created, method="PUT")
            self.requests.append(request)
        for torrent in self.torrents_to_remove:
            request = TriblerRequestManager()
            request.perform_request("channels/discovered/%s/playlists/%s/%s" % (self.channel_info["mychannel"]["identifier"], self.playlist_info['id'], torrent['infohash']), self.on_torrent_created, method="DELETE")
            self.requests.append(request)

    def on_torrent_removed(self, result):
        print result

    def on_torrent_created(self, result):
        print result
