from PyQt5.QtWidgets import QWidget
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.defs import PAGE_CHANNEL_DETAILS
from TriblerGUI.playlist_list_item import PlaylistListItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class ChannelPage(QWidget):

    def initialize_with_channel(self, channel_info):
        self.channel_items_list = []
        self.get_torents_in_channel_manager = TriblerRequestManager()
        self.get_torents_in_channel_manager.perform_request("channels/discovered/%s/torrents" % channel_info['dispersy_cid'], self.received_torrents_in_channel)
        #self.get_playlists_in_channel_manager = TriblerRequestManager()
        #self.get_playlists_in_channel_manager.perform_request("channels/discovered/%s/playlists" % channel_info['dispersy_cid'], self.received_playlists_in_channel)

        # initialize the page about a channel
        self.window().channel_name_label.setText(channel_info['name'])
        self.window().channel_num_subs_label.setText(str(channel_info['votes']))

    def received_torrents_in_channel(self, results):
        for result in results['torrents']:
            self.channel_items_list.append((ChannelTorrentListItem, result))
        self.window().channel_torrents_list.set_data_items(self.channel_items_list)

    def received_playlists_in_channel(self, results):
        playlists = []
        for result in results['playlists']:
            playlists.append((PlaylistListItem, result))
        self.window().channel_torrents_list.set_data_items(playlists + self.channel_items_list)
