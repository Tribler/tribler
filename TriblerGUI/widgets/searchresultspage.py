from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_gui_setting
from TriblerGUI.widgets.tablecontentmodel import SearchResultsContentModel
from TriblerGUI.widgets.triblertablecontrollers import SearchResultsTableViewController


class SearchResultsPage(QWidget):
    """
    This class is responsible for displaying the search results.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.query = None
        self.controller = None
        self.model = None
        self.gui_settings = None

    def initialize_search_results_page(self, gui_settings):
        self.gui_settings = gui_settings
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.model = SearchResultsContentModel(hide_xxx=get_gui_setting(self.gui_settings, "family_filter", True,
                                                                        is_bool=True) if self.gui_settings else True)
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

    def received_search_result(self, response):
        self.controller.load_remote_results(response)
