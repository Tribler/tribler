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
                                                           self.window().num_results_label)
        self.window().search_details_container.details_tab_widget.initialize_details_widget()
        self.window().core_manager.events_manager.node_info_updated.connect(self.model.update_node_info)
        self.window().core_manager.events_manager.torrent_info_updated.connect(self.controller.update_health_details)

        self.set_columns_visibility([u'health', u'updated'], True)
        self.set_columns_visibility([u'torrents'], False)

    def perform_search(self, query):
        self.query = query
        self.model.reset()

        self.window().num_results_label.setText("")
        self.window().search_details_container.hide()

        trimmed_query = query if len(query) < 50 else "%s..." % query[:50]
        self.window().search_results_header_label.setText("Search results for: %s" % trimmed_query)

        self.controller.query_text = query
        self.controller.perform_query(first=1, last=50)

    def set_columns_visibility(self, column_names, hide=False):
        for column_name in column_names:
            self.window().search_results_list.setColumnHidden(
                self.model.column_position[column_name], not hide)

    def clicked_tab_button(self, _):
        if self.window().search_results_tab.get_selected_index() == 0:
            self.model.type_filter = ''
            self.set_columns_visibility([u'votes', u'category', u'health'], True)
            self.set_columns_visibility([u'torrents'], False)
        elif self.window().search_results_tab.get_selected_index() == 1:
            self.model.type_filter = 'channel'
            self.set_columns_visibility([u'votes', u'torrents'], True)
            self.set_columns_visibility([u'size', u'category', u'health'], False)
        elif self.window().search_results_tab.get_selected_index() == 2:
            self.model.type_filter = 'torrent'
            self.set_columns_visibility([u'votes', u'torrents'], False)
            self.set_columns_visibility([u'size', u'category', u'health', u'updated'], True)

        self.perform_search(self.query)

    def received_search_result(self, response):
        self.controller.on_query_results(response, remote=True)
