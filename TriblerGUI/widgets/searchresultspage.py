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
        self.show_torrents = True
        self.show_channels = True

    def initialize_search_results_page(self):
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.window().search_torrents_detail_widget.hide()

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
            self.show_torrents = True
            self.show_channels = True
            self.load_search_results_in_list()
        elif tab_button_name == "search_results_channels_button":
            self.show_torrents = False
            self.show_channels = True
            self.load_search_results_in_list()
        elif tab_button_name == "search_results_torrents_button":
            self.show_torrents = True
            self.show_channels = False
            self.load_search_results_in_list()

    def update_num_search_results(self):
        self.window().num_search_results_label.setText("%d results" %
                                                       (len(self.search_results['channels']) +
                                                        len(self.search_results['torrents'])))

    def clicked_item(self):
        if len(self.window().search_results_list.selectedItems()) != 1:
            self.window().search_torrents_detail_widget.hide()
        else:
            item = self.window().search_results_list.selectedItems()[0]
            list_widget = item.listWidget()
            list_item = list_widget.itemWidget(item)
            if isinstance(list_item, ChannelTorrentListItem):
                self.window().search_torrents_detail_widget.update_with_torrent(list_item.torrent_info)
                self.window().search_torrents_detail_widget.show()
            else:
                self.window().search_torrents_detail_widget.hide()

    def load_search_results_in_list(self):
        all_items = []
        if self.show_channels:
            for channel_item in self.search_results['channels']:
                all_items.append((ChannelListItem, channel_item))

        if self.show_torrents:
            self.search_results['torrents'] = sorted(self.search_results['torrents'],
                                                     key=lambda item: item['relevance_score'],
                                                     reverse=True)
            for torrent_item in self.search_results['torrents']:
                all_items.append((ChannelTorrentListItem, torrent_item))

        self.window().search_results_list.set_data_items(all_items)

    def received_search_result_channel(self, result):
        # Ignore channels that have a small amount of torrents or have no votes
        if result['torrents'] <= 2 or result['votes'] == 0:
            return
        if self.is_duplicate_channel(result):
            return
        channel_index = bisect_right(result, self.search_results['channels'], is_torrent=False)
        if self.show_channels:
            self.window().search_results_list.insert_item(channel_index, (ChannelListItem, result))

        self.search_results['channels'].insert(channel_index, result)
        self.update_num_search_results()

    def received_search_result_torrent(self, result):
        if self.is_duplicate_torrent(result):
            return
        torrent_index = bisect_right(result, self.search_results['torrents'], is_torrent=True)
        num_channels_visible = len(self.search_results['channels']) if self.show_channels else 0
        if self.show_torrents:
            self.window().search_results_list.insert_item(
                torrent_index + num_channels_visible, (ChannelTorrentListItem, result))

        self.search_results['torrents'].insert(torrent_index, result)
        self.update_num_search_results()

    def is_duplicate_channel(self, result):
        for channel_item in self.search_results['channels']:
            if result[u'dispersy_cid'] == channel_item[u'dispersy_cid']:
                return True
        return False

    def is_duplicate_torrent(self, result):
        for torrent_item in self.search_results['torrents']:
            if result[u'infohash'] == torrent_item[u'infohash']:
                return True
        return False
