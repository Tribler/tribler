from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.channelview import ChannelContentsModel
from TriblerGUI.widgets.lazytableview import ACTION_BUTTONS


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
        self.query = None
        self.model_mixed = None
        self.model_channels = None
        self.model_torrents = None
        # TODO: use currentIndex from tab widget instead
        self.tab_state = 'all'

    def initialize_search_results_page(self):
        self.window().search_results_tab.initialize()
        self.window().search_results_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.window().search_page_container.channel_entry_clicked.connect(self.window().on_channel_clicked)

    def perform_search(self, query):
        self.query = query

        self.model_mixed = ChannelContentsModel(parent=None, search_query=query)
        self.model_channels = ChannelContentsModel(parent=None, search_query=query, search_type=u'channel')
        self.model_torrents = ChannelContentsModel(parent=None, search_query=query, search_type=u'torrent')
        self.switch_model()

        self.search_results = {'channels': [], 'torrents': []}
        self.window().num_search_results_label.setText("")

        trimmed_query = query if len(query) < 50 else "%s..." % query[:50]
        self.window().search_results_header_label.setText("Search results for: %s" % trimmed_query)

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
            self.window().search_page_container.torrents_table.setColumnHidden(
                self.model_torrents.column_position[column_name], not hide)

    def switch_model(self):
        # Hide all columns that are hidden by at least one view
        self.window().search_page_container.buttons_container.setHidden(True)
        self.window().search_page_container.top_bar_container.setHidden(True)

        if self.tab_state == 'all':
            self.window().search_page_container.set_model(self.model_mixed)
            self.set_columns_visibility([u'subscribed', u'health', u'commit_status', ACTION_BUTTONS], False)
            self.set_columns_visibility([u'subscribed', u'health', ACTION_BUTTONS], True)
            self.window().search_page_container.details_tab_widget.setHidden(False)

        elif self.tab_state == 'channels':
            self.window().search_page_container.set_model(self.model_channels)
            self.set_columns_visibility([u'subscribed', u'health', u'commit_status', ACTION_BUTTONS], False)
            self.set_columns_visibility([u'subscribed'], True)
            self.window().search_page_container.details_tab_widget.setHidden(True)

        elif self.tab_state == 'torrents':
            self.window().search_page_container.set_model(self.model_torrents)
            self.set_columns_visibility([u'subscribed', u'health', u'commit_status', ACTION_BUTTONS], False)
            self.set_columns_visibility([u'health', ACTION_BUTTONS], True)
            self.window().search_page_container.details_tab_widget.setHidden(False)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "search_results_all_button":
            self.tab_state = 'all'
        elif tab_button_name == "search_results_channels_button":
            self.tab_state = 'channels'
        elif tab_button_name == "search_results_torrents_button":
            self.tab_state = 'torrents'
        self.switch_model()

    def update_num_search_results(self):
        self.window().num_search_results_label.setText("%d results" %
                                                       (len(self.search_results['channels']) +
                                                        len(self.search_results['torrents'])))
