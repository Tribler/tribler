import json
from random import shuffle

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QWidget, QListWidget, QListWidgetItem, QLabel
from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem


class SearchResultsPage(QWidget):

    def initialize_search_results_page(self):
        self.search_results_list = self.findChild(QListWidget, "search_results_list")
        self.search_results_header_label = self.findChild(QLabel, "search_results_header_label")
        self.num_search_results_label = self.findChild(QLabel, "num_search_results_label")
        self.search_results = {}

        self.search_results_tab = self.findChild(QWidget, "search_results_tab")
        self.search_results_tab.initialize()
        self.search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def perform_search(self, query):
        self.num_search_results_label.setText("")
        self.search_results_header_label.setText("Search results for '%s'" % query)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "search_results_all_button":
            self.load_search_results_in_list()
        elif tab_button_name == "search_results_channels_button":
            self.load_search_results_in_list(show_torrents=False)
        elif tab_button_name == "search_results_torrents_button":
            self.load_search_results_in_list(show_channels=False)

    def load_search_results_in_list(self, show_channels=True, show_torrents=True):
        self.num_search_results_label.setText("%d results" % (len(self.search_results['channels']) + len(self.search_results['torrents'])))
        all_items = []
        if show_channels:
            for channel_item in self.search_results['channels']:
                all_items.append((ChannelListItem, channel_item))

        if show_torrents:
            for torrent_item in self.search_results['torrents']:
                all_items.append((ChannelTorrentListItem, torrent_item))

        # Just sort them randomly, channels and torrents mixed
        shuffle(all_items)

        self.search_results_list.set_data_items(all_items)

    def received_search_results(self, results):
        self.search_results = results
        self.load_search_results_in_list()
