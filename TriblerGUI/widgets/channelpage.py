from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.widgets.loading_list_item import LoadingListItem
from TriblerGUI.widgets.playlist_list_item import PlaylistListItem
from TriblerGUI.widgets.text_list_item import TextListItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class ChannelPage(QWidget):
    """
    The ChannelPage is the page with an overview of each channel and displays the list of torrents/playlist available.
    """

    def __init__(self):
        QWidget.__init__(self)

        self.playlists = []
        self.torrents = []
        self.loaded_channels = False
        self.loaded_playlists = False
        self.channel_info = None

        self.get_torents_in_channel_manager = None
        self.get_playlists_in_channel_manager = None

    def initialize_with_channel(self, channel_info):
        self.playlists = []
        self.torrents = []
        self.loaded_channels = False
        self.loaded_playlists = False

        self.get_torents_in_channel_manager = None
        self.get_playlists_in_channel_manager = None

        self.channel_info = channel_info

        self.window().channel_torrents_list.set_data_items([(LoadingListItem, None)])
        self.window().channel_torrents_detail_widget.hide()

        self.window().channel_preview_label.setHidden(channel_info['subscribed'])
        self.window().channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))

        self.get_torents_in_channel_manager = TriblerRequestManager()
        self.get_torents_in_channel_manager.perform_request("channels/discovered/%s/torrents" %
                                                            channel_info['dispersy_cid'],
                                                            self.received_torrents_in_channel)

        self.get_playlists_in_channel_manager = TriblerRequestManager()
        self.get_playlists_in_channel_manager.perform_request("channels/discovered/%s/playlists" %
                                                              channel_info['dispersy_cid'],
                                                              self.received_playlists_in_channel)

        # initialize the page about a channel
        self.window().channel_name_label.setText(channel_info['name'])
        self.window().num_subs_label.setText(str(channel_info['votes']))
        self.window().subscription_widget.initialize_with_channel(channel_info)

        self.window().edit_channel_button.setHidden(True)

    def clicked_item(self):
        if len(self.window().channel_torrents_list.selectedItems()) != 1:
            self.window().channel_torrents_detail_widget.hide()
        else:
            item = self.window().channel_torrents_list.selectedItems()[0]
            list_widget = item.listWidget()
            list_item = list_widget.itemWidget(item)
            if isinstance(list_item, ChannelTorrentListItem):
                self.window().channel_torrents_detail_widget.update_with_torrent(list_item.torrent_info)
                self.window().channel_torrents_detail_widget.show()
            else:
                self.window().channel_torrents_detail_widget.hide()

    def update_result_list(self):
        if self.loaded_channels and self.loaded_playlists:
            self.window().channel_torrents_list.set_data_items(self.playlists + self.torrents)

    def received_torrents_in_channel(self, results):
        if not results:
            return
        def sort_key(torrent):
            """ Scoring algorithm for sorting the torrent to show liveness. The score is basically the sum of number
                of seeders and leechers. If swarm info is unknown, we give unknown seeder and leecher as 0.5 & 0.4 so
                that the sum is less than 1 and higher than zero. This means unknown torrents will have higher score
                than dead torrent with no seeders and leechers and lower score than any barely alive torrent with a
                single seeder or leecher.
            """
            seeder_score = torrent['num_seeders'] if torrent['num_seeders'] or torrent['last_tracker_check'] > 0\
                else 0.5
            leecher_score = torrent['num_leechers'] if torrent['num_leechers'] or torrent['last_tracker_check'] > 0\
                else 0.5
            return seeder_score + .5 * leecher_score

        for result in sorted(results['torrents'], key=sort_key, reverse=True):
            self.torrents.append((ChannelTorrentListItem, result))

        if not self.channel_info['subscribed']:
            self.torrents.append((TextListItem, "You're looking at a preview of this channel.\n"
                                                "Subscribe to this channel to see the full content."))

        self.loaded_channels = True
        self.update_result_list()

    def received_playlists_in_channel(self, results):
        if not results:
            return
        for result in results['playlists']:
            self.playlists.append((PlaylistListItem, result))
        self.loaded_playlists = True
        self.update_result_list()

    def on_edit_channel_clicked(self):
        self.window().edit_channel_page.initialize_with_channel_overview(
            {"channel":
                 {"name": self.channel_info["name"],
                  "description": self.channel_info["description"],
                  "identifier": self.channel_info["dispersy_cid"]}})
