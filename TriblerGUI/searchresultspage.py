from PyQt5.QtWidgets import QWidget
from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.utilities import split_into_keywords, interleave_lists


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
        self.last_channel_index = 4
        self.window().search_results_list.set_data_items([]) # To clean the list

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
        if show_channels and show_torrents:
            torrents_list = [(ChannelTorrentListItem, torrent) for torrent in self.search_results['torrents']]
            channels_list = [(ChannelListItem, channel) for channel in self.search_results['channels']]

            interleaved_list = interleave_lists(torrents_list, channels_list)
            self.window().search_results_list.set_data_items(interleaved_list)
            return

        all_items = []
        if show_channels:
            for channel_item in self.search_results['channels']:
                all_items.append((ChannelListItem, channel_item))

        if show_torrents:
            for torrent_item in self.search_results['torrents']:
                all_items.append((ChannelTorrentListItem, torrent_item))

        self.window().search_results_list.set_data_items(all_items)

    def bisect_right(self, item, list, is_torrent):
        """
        This method inserts a channel/torrent in a sorted list. The sorting is based on relevance score.
        The implementation is based on bisect_right.
        """
        lo = 0
        hi = len(list)
        while lo < hi:
            mid = (lo+hi) // 2
            if item['relevance_score'] == list[mid]['relevance_score'] and is_torrent:
                if len(split_into_keywords(item['name'])) < len(split_into_keywords(list[mid]['name'])):
                    hi = mid
                else:
                    lo = mid + 1
            elif item['relevance_score'] > list[mid]['relevance_score']:
                hi = mid
            else:
                lo = mid + 1
        return lo

    def received_search_result_channel(self, result):
        # Ignore channels that have a small amount of torrents or have no votes
        if result['torrents'] <= 2 or result['votes'] == 0:
            return

        if self.last_channel_index >= len(self.window().search_results_list.data_items):
            self.window().search_results_list.append_item((ChannelListItem, result))
        else:
            self.window().search_results_list.insert_item(self.last_channel_index, (ChannelListItem, result))
            self.last_channel_index += 5

        channel_index = self.bisect_right(result, self.search_results['channels'], is_torrent=False)
        self.search_results['channels'].insert(channel_index, result)
        self.update_num_search_results()

    def received_search_result_torrent(self, result):
        torrent_index = self.bisect_right(result, self.search_results['torrents'], is_torrent=True)
        self.search_results['torrents'].insert(torrent_index, result)
        self.window().search_results_list.insert_item(torrent_index, (ChannelTorrentListItem, result))
        self.update_num_search_results()
