"""
This file contains various controllers for table views.
The responsibility of the controller is to populate the table view with some data, contained in a specific model.
"""
from __future__ import absolute_import

import uuid

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAction

from six import text_type

from TriblerGUI.defs import COMMIT_STATUS_COMMITTED, COMMIT_STATUS_UPDATED
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager


def sanitize_for_fts(text):
    return text_type(text).translate({ord(u"\""): u"\"\"", ord(u"\'"): u"\'\'"})


def to_fts_query(text):
    if not text:
        return ""
    words = text.split(" ")

    # TODO: add support for quoted exact searches
    query_list = [u'\"' + sanitize_for_fts(word) + u'\"*' for word in words]

    return " AND ".join(query_list)


class TriblerTableViewController(QObject):
    """
    Base controller for a table view that displays some data.
    """
    count_query_complete = pyqtSignal(dict)

    def __init__(self, model, table_view):
        super(TriblerTableViewController, self).__init__()
        self.model = model
        self.model.on_sort.connect(self._on_view_sort)
        self.table_view = table_view
        self.table_view.setModel(self.model)
        self.table_view.verticalScrollBar().valueChanged.connect(self._on_list_scroll)
        self.query_text = ''
        self.num_results_label = None
        self.request_mgr = None
        self.query_uuid = None

    def _on_view_sort(self, column, ascending):
        if not column:
            self.table_view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
            return
        self.model.reset()
        self.perform_query(first=1, last=50)

    def _on_list_scroll(self, event):
        if self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum() and \
                self.model.data_items:  # workaround for duplicate calls to _on_list_scroll on view creation
            self.perform_query()

    def _get_sort_parameters(self):
        """
        Return a tuple (column_name, sort_asc) that indicates the sorting column/order of the table view.
        """
        sort_column_number = self.table_view.horizontalHeader().sortIndicatorSection()
        # If the column number is set to -1, this means we do not want to do sorting at all
        # We have to set it to something (-1), because QT does not support setting it to "None"
        sort_by = self.model.columns[sort_column_number] if sort_column_number >= 0 else None
        sort_asc = self.table_view.horizontalHeader().sortIndicatorOrder()
        return sort_by, sort_asc

    def perform_query(self, **kwargs):
        """
        Fetch results for a given query.
        """
        if 'first' not in kwargs or 'last' not in kwargs:
            kwargs["first"], kwargs[
                'last'] = self.model.rowCount() + 1, self.model.rowCount() + self.model.item_load_batch

        # Create a new uuid for each new search
        if kwargs['first'] == 1 or not self.query_uuid:
            self.query_uuid = uuid.uuid4().hex
        kwargs.update({"uuid": self.query_uuid})

        sort_by, sort_asc = self._get_sort_parameters()

        if sort_by is not None:
            kwargs.update({"sort_by": sort_by, "sort_asc": sort_asc})

        if 'query_filter' in kwargs:
            kwargs.update({"filter": to_fts_query(kwargs.pop('query_filter'))})
        elif self.query_text:
            kwargs.update({"filter": to_fts_query(self.query_text)})

        if self.model.hide_xxx is not None:
            kwargs.update({"hide_xxx": self.model.hide_xxx})

        rest_endpoint_url = kwargs.pop("rest_endpoint_url")
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(rest_endpoint_url,
                                         self.on_query_results,
                                         url_params=kwargs)

        # If it is the first time we fetch the results, so we must get the total number of items as well
        if self.model.total_items is None:
            self.query_total_count(rest_endpoint_url=rest_endpoint_url, **kwargs)

    def on_total_count_results(self, response):
        # Workaround for possible race condition between simultaneous requests. Sees query_total_count for details.
        if "total" in response:
            self.count_query_complete.emit(response)
            self.model.total_items = response['total']
            # TODO unify this label update with the above count_query_complete signal
            if self.num_results_label:
                self.num_results_label.setText("%d results" % self.model.total_items)
            return False

    def query_total_count(self, **kwargs):
        rest_endpoint_url = kwargs.pop("rest_endpoint_url")
        kwargs.pop("first", None)
        kwargs.pop("last", None)
        kwargs.pop("sort_by", None)
        kwargs.pop("sort_asc", None)
        self.request_mgr2 = TriblerRequestManager()
        # Unfortunately, TriblerRequestManager cannot discern between different requests to the same endpoint.
        # That is why we have to process both count and regular requests by the same callback.
        # Otherwise, there is no guarantee which callback will process which request...
        self.request_mgr2.perform_request(rest_endpoint_url+"/count", self.on_total_count_results, url_params=kwargs)

    def on_query_results(self, response, remote=False):
        """
        Updates the table with the response.
        :param response: List of the items to be added to the model
        :param remote: True if response is from a remote peer. Default: False
        :return: None
        """
        # TODO: count remote results
        if not response:
            return False

        if self.is_new_result(response):
            self.model.add_items(response['results'], remote=remote)

        return True

    def is_new_result(self, response):
        """
        Returns True if the response is a new fresh response else False.
        - If UUID of the response and the last query does not match, then it is a stale response.
        :param response: List of items
        :return: True for fresh response else False
        """
        if self.query_uuid and 'uuid' in response and response['uuid'] != self.query_uuid:
            return False
        return True


class FilterInputMixin(object):

    def _on_filter_input_change(self, _):
        self.query_text = self.filter_input.text().lower()
        self.model.reset()
        self.perform_query(start=1, end=50)


class TableSelectionMixin(object):

    def brain_dead_refresh(self):
        """
        FIXME! Brain-dead way to show the rows covered by a newly-opened details_container
        Note that none of then more civilized ways to fix it work:
        various updateGeometry, viewport().update, adjustSize - nothing works!
        """
        window = self.table_view.window()
        window.resize(window.geometry().width() + 1, window.geometry().height())
        window.resize(window.geometry().width() - 1, window.geometry().height())

    def _on_selection_changed(self, _):
        selected_indices = self.table_view.selectedIndexes()
        if not selected_indices:
            self.details_container.hide()
            self.table_view.clearSelection()
            self.brain_dead_refresh()
            return

        torrent_info = selected_indices[0].model().data_items[selected_indices[0].row()]
        if 'type' in torrent_info and torrent_info['type'] == 'channel':
            self.details_container.hide()
            self.brain_dead_refresh()
            return

        first_show = False
        if self.details_container.isHidden():
            first_show = True

        self.details_container.show()
        self.details_container.details_tab_widget.update_with_torrent(selected_indices[0], torrent_info)
        if first_show:
            self.brain_dead_refresh()


class TorrentHealthDetailsMixin(object):

    def update_health_details(self, update_dict):
        if self.details_container.isHidden() or not self.details_container.details_tab_widget.torrent_info:
            return

        if self.details_container.details_tab_widget.torrent_info["infohash"] == update_dict["infohash"]:
            self.details_container.details_tab_widget.torrent_info.update(update_dict)
            self.details_container.details_tab_widget.update_health_label(update_dict["num_seeders"],
                                                                          update_dict["num_leechers"],
                                                                          update_dict["last_tracker_check"])
            self.model.update_node_info(update_dict)


class ContextMenuMixin(object):

    table_view = None
    model = None

    def enable_context_menu(self, widget):
        self.table_view = widget
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        if not self.table_view or not self.model:
            return

        item_index = self.table_view.indexAt(pos)
        if not item_index or item_index.row() < 0:
            return

        menu = TriblerActionMenu(self.table_view)

        # Single selection menu items
        num_selected = len(self.table_view.selectionModel().selectedRows())
        if num_selected == 1:
            self.add_menu_item(menu, ' Download ', item_index, self.table_view.on_download_button_clicked)
            self.add_menu_item(menu, ' Play ', item_index, self.table_view.on_play_button_clicked)

        # Add menu separater for channel stuff
        menu.addSeparator()

        if not isinstance(self, MyTorrentsTableViewController):
            if self.selection_has_torrents():
                self.add_menu_item(menu, ' Add to My Channel ', item_index,
                                   self.table_view.on_add_to_channel_button_clicked)
        else:
            self.add_menu_item(menu, ' Remove from My Channel ', item_index, self.table_view.on_delete_button_clicked)

        menu.exec_(QCursor.pos())

    def add_menu_item(self, menu, name, item_index, callback):
        action = QAction(name, self.table_view)
        action.triggered.connect(lambda _: callback(item_index))
        menu.addAction(action)

    def selection_has_torrents(self):
        for row in self.table_view.selectionModel().selectedRows():
            if row.model().is_torrent_item(row.row()):
                return True
        return False

    def selection_has_channels(self):
        for row in self.table_view.selectionModel().selectedRows():
            if row.model().is_channel_item(row.row()):
                return True
        return False


class SearchResultsTableViewController(TableSelectionMixin, ContextMenuMixin, TriblerTableViewController,
                                       TorrentHealthDetailsMixin):
    """
    Controller for the table view that handles search results.
    """

    def __init__(self, model, table_view, details_container, num_results_label=None):
        TriblerTableViewController.__init__(self, model, table_view)
        self.num_results_label = num_results_label
        self.details_container = details_container
        table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.enable_context_menu(self.table_view)

    def perform_query(self, **kwargs):
        """
        Fetch search results.
        """
        if "rest_endpoint_url" not in kwargs:
            kwargs.update({"metadata_type": self.model.type_filter})
        kwargs.update({"rest_endpoint_url": "search"})
        super(SearchResultsTableViewController, self).perform_query(**kwargs)


class ChannelsTableViewController(TableSelectionMixin, FilterInputMixin, TriblerTableViewController):
    """
    This class manages a list with channels.
    """

    def __init__(self, model, table_view, num_results_label=None, filter_input=None):
        TriblerTableViewController.__init__(self, model, table_view)
        self.num_results_label = num_results_label
        self.filter_input = filter_input

        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)

    def perform_query(self, **kwargs):
        self.query_text = (self.filter_input.text().lower()
                           if (self.filter_input and self.filter_input.text().lower())
                           else '')
        if "rest_endpoint_url" not in kwargs:
            kwargs.update({"rest_endpoint_url": "metadata/channels"})
        if self.model.subscribed is not None:
            kwargs.update({"subscribed": self.model.subscribed})
        super(ChannelsTableViewController, self).perform_query(**kwargs)


class TorrentsTableViewController(TableSelectionMixin, FilterInputMixin, ContextMenuMixin, TriblerTableViewController,
                                  TorrentHealthDetailsMixin):
    """
    This class manages a list with torrents.
    """

    def __init__(self, model, table_view, details_container, num_results_label=None, filter_input=None):
        TriblerTableViewController.__init__(self, model, table_view)
        self.num_results_label = num_results_label
        self.filter_input = filter_input
        self.details_container = details_container
        table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)
        self.enable_context_menu(self.table_view)

    def perform_query(self, **kwargs):
        # On some systems, URLs containing double slashes are handled incorrectly.
        # To circumvent this limitation, for empty public key we use a special substitute
        if "rest_endpoint_url" not in kwargs:
            kwargs.update({
                "rest_endpoint_url": "metadata/channels/%s/%i/torrents" %
                                     (self.model.channel_pk,
                                      self.model.channel_id)})
        super(TorrentsTableViewController, self).perform_query(**kwargs)

    def fetch_preview(self):
        params = {'query_filter': self.model.channel_pk,
                  'metadata_type': 'torrent',
                  'rest_endpoint_url': 'search',
                  'first': 1,
                  'last': 50}
        super(TorrentsTableViewController, self).perform_query(**params)


class MyTorrentsTableViewController(TorrentsTableViewController):
    """
    This class manages the list with the torrents in your own channel.
    """

    def __init__(self, *args, **kwargs):
        super(MyTorrentsTableViewController, self).__init__(*args, **kwargs)
        self.model.row_edited.connect(self._on_row_edited)

    def _on_row_edited(self, index, new_value):
        # FIXME: check the REST response and update the row from it
        infohash = self.model.data_items[index.row()][u'infohash']
        attribute_name = self.model.columns[index.column()]
        self.model.data_items[index.row()][u'status'] = COMMIT_STATUS_UPDATED
        attribute_name = u'tags' if attribute_name == u'category' else attribute_name
        attribute_name = u'title' if attribute_name == u'name' else attribute_name

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(
            "mychannel/torrents/%s" % infohash,
            self._on_row_update_results,
            method='PATCH',
            data={attribute_name: new_value})

    def _on_row_update_results(self, response):
        if response:
            self.table_view.window().edit_channel_page.channel_dirty = \
                self.table_view.window().edit_channel_page.channel_dirty or \
                (response['new_status'] != COMMIT_STATUS_COMMITTED)
            self.table_view.window().edit_channel_page.update_channel_commit_views()

    def perform_query(self, **kwargs):
        kwargs.update({
            "rest_endpoint_url": "mychannel/torrents",
            "exclude_deleted": self.model.exclude_deleted})
        super(MyTorrentsTableViewController, self).perform_query(**kwargs)
