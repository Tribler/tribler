"""
This file contains various controllers for table views.
The responsibility of the controller is to populate the table view with some data, contained in a specific model.
"""
from __future__ import absolute_import

from TriblerGUI.tribler_request_manager import TriblerRequestManager


class TriblerTableViewController(object):
    """
    Base controller for a table view that displays some data.
    """

    def __init__(self, model, table_view):
        self.model = model
        self.model.on_sort.connect(self._on_view_sort)
        self.table_view = table_view
        self.table_view.setModel(self.model)
        self.table_view.verticalScrollBar().valueChanged.connect(self._on_list_scroll)
        self.request_mgr = None

    def _on_list_scroll(self, event):
        pass

    def _on_view_sort(self, column, ascending):
        pass

    def _get_sort_parameters(self):
        """
        Return a tuple (column_name, sort_asc) that indicates the sorting column/order of the table view.
        """
        sort_by = self.model.columns[self.table_view.horizontalHeader().sortIndicatorSection()]
        sort_asc = self.table_view.horizontalHeader().sortIndicatorOrder()
        return sort_by, sort_asc


class SearchResultsTableViewController(TriblerTableViewController):
    """
    Controller for the table view that handles search results.
    """

    def __init__(self, model, table_view, num_search_results_label=None):
        TriblerTableViewController.__init__(self, model, table_view)
        self.num_search_results_label = num_search_results_label
        self.query = None

    def _on_view_sort(self, column, ascending):
        self.model.reset()
        self.load_search_results(1, 50)

    def _on_list_scroll(self, event):
        if self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum() and \
                self.model.data_items:  # workaround for duplicate calls to _on_list_scroll on view creation
            self.load_search_results(self.query)

    def load_search_results(self, query, start=None, end=None):
        """
        Fetch search results for a given query.
        """
        self.query = query

        if not start and not end:
            start, end = self.model.rowCount() + 1, self.model.rowCount() + self.model.item_load_batch

        sort_by, sort_asc = self._get_sort_parameters()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(
            "search?q=%s&first=%i&last=%i" % (query, start, end)
            + ('&sort_by=%s' % sort_by)
            + ('&sort_asc=%d' % sort_asc)
            + ('&type=%s' % ('' if not self.model.type_filter else self.model.type_filter)),
            self.on_search_results)

    def on_search_results(self, response):
        if not response:
            return

        self.model.total_items = response['total']

        if self.num_search_results_label:
            self.num_search_results_label.setText("%d results" % response['total'])

        if response['first'] >= self.model.rowCount():
            self.model.add_items(response['results'])


class ChannelsTableViewController(TriblerTableViewController):
    """
    This class manages a list with channels.
    """

    def __init__(self, model, table_view, num_channels_label=None, filter_input=None):
        TriblerTableViewController.__init__(self, model, table_view)
        self.num_channels_label = num_channels_label
        self.filter_input = filter_input

        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)

    def _on_filter_input_change(self, text):
        self.model.reset()
        self.load_channels(1, 50)

    def _on_view_sort(self, column, ascending):
        self.model.reset()
        self.load_channels(1, 50)

    def _on_list_scroll(self, event):
        if self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum() and \
                self.model.data_items:  # workaround for duplicate calls to _on_list_scroll on view creation
            self.load_channels()

    def load_channels(self, start=None, end=None):
        """
        Fetch various channels.
        """
        if not start and not end:
            start, end = self.model.rowCount() + 1, self.model.rowCount() + self.model.item_load_batch

        if self.filter_input and self.filter_input.text().lower():
            filter_text = self.filter_input.text().lower()
        else:
            filter_text = ''

        sort_by, sort_asc = self._get_sort_parameters()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(
            "metadata/channels?first=%i&last=%i" % (start, end)
            + ('&sort_by=%s' % sort_by)
            + ('&sort_asc=%d' % sort_asc)
            + ('&filter=%s' % filter_text)
            + ('&subscribed=%d' % int(self.model.subscribed)),
            self.on_channels)

    def on_channels(self, response):
        if not response:
            return

        self.model.total_items = response['total']

        if self.num_channels_label:
            self.num_channels_label.setText("%d items" % response['total'])

        if response['first'] >= self.model.rowCount():
            self.model.add_items(response['channels'])


class TorrentsTableViewController(TriblerTableViewController):
    """
    This class manages a list with torrents.
    """

    def __init__(self, model, torrents_container, num_torrents_label=None, filter_input=None):
        TriblerTableViewController.__init__(self, model, torrents_container.content_table)
        self.num_torrents_label = num_torrents_label
        self.filter_input = filter_input

        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)

    def _on_filter_input_change(self, text):
        self.model.reset()
        self.load_torrents(1, 50)

    def _on_view_sort(self, column, ascending):
        self.model.reset()
        self.load_torrents(1, 50)

    def _on_list_scroll(self, event):
        if self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum() and \
                self.model.data_items:  # workaround for duplicate calls to _on_list_scroll on view creation
            self.load_torrents()

    def load_torrents(self, start=None, end=None):
        """
        Fetch various torrents.
        """
        if not start and not end:
            start, end = self.model.rowCount() + 1, self.model.rowCount() + self.model.item_load_batch

        if self.filter_input and self.filter_input.text().lower():
            filter_text = self.filter_input.text().lower()
        else:
            filter_text = ''

        sort_by, sort_asc = self._get_sort_parameters()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(
            "metadata/channels/%s/torrents?first=%i&last=%i" % (self.model.channel_pk, start, end)
            + ('&sort_by=%s' % sort_by)
            + ('&sort_asc=%d' % sort_asc)
            + ('&filter=%s' % filter_text),
            self.on_torrents)

    def on_torrents(self, response):
        if not response:
            return

        self.model.total_items = response['total']

        if self.num_torrents_label:
            self.num_torrents_label.setText("%d items" % response['total'])

        if response['first'] >= self.model.rowCount():
            self.model.add_items(response['torrents'])


class MyTorrentsTableViewController(TorrentsTableViewController):
    """
    This class manages the list with your the torrents in your own channel.
    """

    def load_torrents(self, start=None, end=None):
        """
        Fetch various torrents.
        """
        if not start and not end:
            start, end = self.model.rowCount() + 1, self.model.rowCount() + self.model.item_load_batch

        if self.filter_input and self.filter_input.text().lower():
            filter_text = self.filter_input.text().lower()
        else:
            filter_text = ''

        sort_by, sort_asc = self._get_sort_parameters()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(
            "mychannel/torrents?first=%i&last=%i" % (start, end)
            + ('&sort_by=%s' % sort_by)
            + ('&sort_asc=%d' % sort_asc)
            + ('&filter=%s' % filter_text),
            self.on_torrents)

    def on_torrents(self, response):
        if not response:
            return

        self.model.total_items = response['total']

        if self.num_torrents_label:
            self.num_torrents_label.setText("%d items" % response['total'])

        if response['first'] >= self.model.rowCount():
            self.model.add_items(response['torrents'])

        self.table_view.window().dirty_channel_status_bar.setHidden(not response['dirty'])
        self.table_view.window().edit_channel_commit_button.setEnabled(response['dirty'])
