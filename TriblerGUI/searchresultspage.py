from random import shuffle

from PyQt5.QtWidgets import QWidget, QListWidget, QLabel
from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem


class SearchResultsPage(QWidget):
    """
    This class is responsible for displaying the search results.
    """

    def initialize_search_results_page(self):
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def perform_search(self, query):
        self.search_results = {'channels': [], 'torrents': []}
        self.window().num_search_results_label.setText("")
        self.window().search_results_header_label.setText("Search results for '%s'" % query)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "search_results_all_button":
            self.load_search_results_in_list()
        elif tab_button_name == "search_results_channels_button":
            self.load_search_results_in_list(show_torrents=False)
        elif tab_button_name == "search_results_torrents_button":
            self.load_search_results_in_list(show_channels=False)

    def update_num_search_results(self):
        self.window().num_search_results_label.setText("%d results" % (len(self.search_results['channels']) + len(self.search_results['torrents'])))

    def load_search_results_in_list(self, show_channels=True, show_torrents=True):

        all_items = []
        if show_channels:
            for channel_item in self.search_results['channels']:
                all_items.append((ChannelListItem, channel_item))

        if show_torrents:
            for torrent_item in self.search_results['torrents']:
                all_items.append((ChannelTorrentListItem, torrent_item))

        # TODO Martijn: just sort them randomly for now, channels and torrents mixed
        shuffle(all_items)

        self.window().search_results_list.set_data_items(all_items)

    def received_search_result_channel(self, result):
        self.window().search_results_list.append_item((ChannelListItem, result))
        self.search_results['channels'].append(result)
        self.update_num_search_results()

    def received_search_result_torrent(self, result):
        self.window().search_results_list.append_item((ChannelTorrentListItem, result))
        self.search_results['torrents'].append(result)
        self.update_num_search_results()
