from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.channel_list_item import ChannelListItem
from TriblerGUI.widgets.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.utilities import bisect_right


class SearchResultsPage(QWidget):
    """
    This class is responsible for displaying the search results.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.search_results = {'channels': [], 'torrents': []}
        self.health_timer = None

    def initialize_search_results_page(self):
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def perform_search(self, query):
        self.search_results = {'channels': [], 'torrents': []}
        self.window().num_search_results_label.setText("")
        self.window().search_results_header_label.setText("Search results for '%s'" % query)
        self.window().search_results_list.set_data_items([])  # To clean the list
        self.window().search_results_tab.on_tab_button_click(self.window().search_results_all_button)

        # Start the health timer that checks the health of the first five results
        if self.health_timer:
            self.health_timer.stop()

        self.health_timer = QTimer()
        self.health_timer.setSingleShot(True)
        self.health_timer.timeout.connect(self.check_health_of_results)
        self.health_timer.start(2000)

    def check_health_of_results(self):
        first_torrents = self.window().search_results_list.get_first_items(5, cls=ChannelTorrentListItem)
        for torrent_item in first_torrents:
            torrent_item.check_health()

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "search_results_all_button":
            self.load_search_results_in_list()
        elif tab_button_name == "search_results_channels_button":
            self.load_search_results_in_list(show_torrents=False)
        elif tab_button_name == "search_results_torrents_button":
            self.load_search_results_in_list(show_channels=False)

    def update_num_search_results(self):
        self.window().num_search_results_label.setText("%d results" %
                                                       (len(self.search_results['channels']) +
                                                        len(self.search_results['torrents'])))

    def load_search_results_in_list(self, show_channels=True, show_torrents=True):
        if show_channels and show_torrents:
            torrents_list = [(ChannelTorrentListItem, torrent) for torrent in self.search_results['torrents']]
            channels_list = [(ChannelListItem, channel) for channel in self.search_results['channels']]

            self.window().search_results_list.set_data_items(channels_list + torrents_list)
            return

        all_items = []
        if show_channels:
            for channel_item in self.search_results['channels']:
                all_items.append((ChannelListItem, channel_item))

        if show_torrents:
            for torrent_item in self.search_results['torrents']:
                all_items.append((ChannelTorrentListItem, torrent_item))

        self.window().search_results_list.set_data_items(all_items)

    def received_search_result_channel(self, result):
        # Ignore channels that have a small amount of torrents or have no votes
        if result['torrents'] <= 2 or result['votes'] == 0:
            return

        channel_index = bisect_right(result, self.search_results['channels'], is_torrent=False)
        self.window().search_results_list.insert_item(channel_index, (ChannelListItem, result))
        self.search_results['channels'].insert(channel_index, result)
        self.update_num_search_results()

    def received_search_result_torrent(self, result):
        torrent_index = bisect_right(result, self.search_results['torrents'], is_torrent=True)
        self.search_results['torrents'].insert(torrent_index, result)
        self.window().search_results_list.insert_item(
            torrent_index + len(self.search_results['channels']), (ChannelTorrentListItem, result))
        self.update_num_search_results()
