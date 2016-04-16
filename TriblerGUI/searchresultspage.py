import json
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QWidget, QListWidget, QListWidgetItem
from TriblerGUI.channel_list_item import ChannelListItem


class SearchResultsPage(QWidget):

    def initialize_search_results_page(self):
        self.search_results_list = self.findChild(QListWidget, "search_results_list")
        self.search_results_list.verticalScrollBar().valueChanged.connect(self.on_search_results_list_scroll)
        self.search_results_items_loaded = 0
        self.search_results = []

        # Tab bar buttons
        self.search_results_tab = self.findChild(QWidget, "search_results_tab")
        self.search_results_tab.initialize()
        self.search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "search_results_all_button":
            print "display all search results"
        elif tab_button_name == "search_results_channels_button":
            print "display channels"
        elif tab_button_name == "search_results_torrents_button":
            print "display torrents"

    def on_search_results_list_scroll(self, event):
        if self.search_results_list.verticalScrollBar().value() == self.search_results_list.verticalScrollBar().maximum():
            self.search_results_list()

    def received_search_results(self, json_results):
        self.search_results_list.clear()
        results = json.loads(json_results)

        for result in results['channels']:
            item = QListWidgetItem(self.channels_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelListItem(self.search_results_list, 0, result, should_fade=False)
            self.search_results_list.addItem(item)
            self.search_results_list.setItemWidget(item, widget_item)
