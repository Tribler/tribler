from PyQt5.QtWidgets import QWidget
from TriblerGUI.home_recommended_item import HomeRecommendedChannelItem, HomeRecommendedTorrentItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class HomePage(QWidget):

    def initialize_home_page(self):
        self.window().home_page_table_view.setRowCount(3)
        self.window().home_page_table_view.setColumnCount(3)

        self.window().home_tab.initialize()
        self.window().home_tab.clicked_tab_button.connect(self.clicked_tab_button)

        self.recommended_request_mgr = TriblerRequestManager()
        self.recommended_request_mgr.perform_request("torrents/random", self.received_popular_torrents)

    def clicked_tab_button(self, tab_button_name):
        self.window().home_page_table_view.clear()
        if tab_button_name == "home_tab_channels_button":
            self.recommended_request_mgr = TriblerRequestManager()
            self.recommended_request_mgr.perform_request("channels/popular", self.received_popular_channels)
        elif tab_button_name == "home_tab_torrents_button":
            self.recommended_request_mgr = TriblerRequestManager()
            self.recommended_request_mgr.perform_request("torrents/random", self.received_popular_torrents)

    def received_popular_channels(self, result):
        cur_ind = 0
        for channel in result["channels"]:
            widget_item = HomeRecommendedChannelItem(self, channel)
            self.window().home_page_table_view.setCellWidget(cur_ind % 3, cur_ind / 3, widget_item)
            cur_ind += 1

    def received_popular_torrents(self, result):
        cur_ind = 0
        for torrent in result["torrents"]:
            widget_item = HomeRecommendedTorrentItem(self, torrent)
            self.window().home_page_table_view.setCellWidget(cur_ind % 3, cur_ind / 3, widget_item)
            cur_ind += 1
