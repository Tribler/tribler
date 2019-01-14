from __future__ import absolute_import

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

from six.moves import xrange

from TriblerGUI.defs import PAGE_CHANNEL_DETAILS
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.home_recommended_item import HomeRecommendedItem


class HomePage(QWidget):
    """
    The HomePage is usually the first page that Tribler users are seeing. It shows some recommended torrents and
    channels in a grid view.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.recommended_request_mgr = None
        self.show_channels = False
        self.resize_event_timer = None

    def initialize_home_page(self):
        self.window().home_page_table_view.cellClicked.connect(self.on_home_page_item_clicked)

        self.window().home_tab.initialize()
        self.window().home_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def load_cells(self, num_items):
        self.window().home_page_table_view.clear()
        for y in xrange(0, 3):
            for x in xrange(0, 3):
                widget_item = HomeRecommendedItem(self)
                self.window().home_page_table_view.setCellWidget(y, x, widget_item)
                if y * 3 + x >= num_items - 1:
                    return

    def load_popular_torrents(self):
        self.recommended_request_mgr = TriblerRequestManager()
        self.recommended_request_mgr.perform_request("metadata/torrents/random?limit=50",
                                                     self.received_popular_torrents)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "home_tab_channels_button":
            self.recommended_request_mgr = TriblerRequestManager()
            self.recommended_request_mgr.perform_request("metadata/channels/popular?limit=50",
                                                         self.received_popular_channels)
        elif tab_button_name == "home_tab_torrents_button":
            self.load_popular_torrents()

    def received_popular_channels(self, result):
        if not result:
            return
        self.show_channels = True

        if len(result["channels"]) == 0:
            self.update_home_page_views(False)
            self.window().home_page_no_items_label.setText("No recommended channels found.")
            return

        cur_ind = 0
        self.update_home_page_views(True)
        self.load_cells(len(result["channels"][:9]))
        for channel in result["channels"][:9]:
            self.window().home_page_table_view.cellWidget(cur_ind / 3, cur_ind % 3).update_with_channel(channel)
            cur_ind += 1

        self.start_resize_timer()

    def update_home_page_views(self, has_results):
        self.window().home_page_table_view.setHidden(not has_results)
        self.window().home_page_no_items_label.setHidden(has_results)

    def received_popular_torrents(self, result):
        if not result:
            return
        self.show_channels = False

        if len(result["torrents"]) == 0:
            self.update_home_page_views(False)
            self.window().home_page_no_items_label.setText("No recommended torrents found.")
            return

        cur_ind = 0
        self.update_home_page_views(True)
        self.load_cells(len(result["torrents"][:9]))
        for torrent in result["torrents"][:9]:
            self.window().home_page_table_view.cellWidget(cur_ind / 3, cur_ind % 3).update_with_torrent(torrent)
            cur_ind += 1

        self.start_resize_timer()

    def start_resize_timer(self):
        """
        For some magic Qt reason, invoking the resizeEvent immediately after loading the cell widgets is not working
        correctly. As a workaround, call the resizeEvent after a small period of time.
        """
        self.resize_event_timer = QTimer()
        self.resize_event_timer.timeout.connect(lambda: self.window().resizeEvent(None))
        self.resize_event_timer.start(100)

    def on_home_page_item_clicked(self, row, col):
        cell_widget = self.window().home_page_table_view.cellWidget(row, col)
        if self.show_channels and isinstance(cell_widget, HomeRecommendedItem):
            channel_info = cell_widget.channel_info
            self.window().channel_page.initialize_with_channel(channel_info)
            self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
            self.window().stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)
