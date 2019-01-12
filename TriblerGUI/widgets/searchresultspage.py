from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.tablecontentmodel import SearchResultsContentModel
from TriblerGUI.widgets.triblertablecontrollers import SearchResultsTableViewController


class SearchResultsPage(QWidget):
    """
    This class is responsible for displaying the search results.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.health_timer = None
        self.query = None
        self.controller = None
        self.model = None

    def initialize_search_results_page(self):
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.model = SearchResultsContentModel()
        self.controller = SearchResultsTableViewController(self.model, self.window().search_results_list,
                                                           self.window().search_details_container,
                                                           self.window().num_search_results_label)
        self.window().search_details_container.details_tab_widget.initialize_details_widget()

    def perform_search(self, query):
        self.query = query
        self.model.reset()

        self.window().num_search_results_label.setText("")
        self.window().search_details_container.hide()

        trimmed_query = query if len(query) < 50 else "%s..." % query[:50]
        self.window().search_results_header_label.setText("Search results for: %s" % trimmed_query)

        self.controller.load_search_results(query, 1, 50)

        # Start the health timer that checks the health of the first five results
        """
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
        """

    def set_columns_visibility(self, column_names, hide=True):
        for column_name in column_names:
            self.window().search_page_container.content_table.setColumnHidden(
                self.model_torrents.column_position[column_name], not hide)

    def clicked_tab_button(self, _):
        if self.window().search_results_tab.get_selected_index() == 0:
            self.model.type_filter = None
        elif self.window().search_results_tab.get_selected_index() == 1:
            self.model.type_filter = 'channel'
        elif self.window().search_results_tab.get_selected_index() == 2:
            self.model.type_filter = 'torrent'

        self.perform_search(self.query)
