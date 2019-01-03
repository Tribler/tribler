from __future__ import absolute_import

import time
from abc import abstractmethod

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from TriblerGUI.defs import ACTION_BUTTONS, HEALTH_CHECKING, HEALTH_DEAD, HEALTH_ERROR, HEALTH_GOOD, HEALTH_MOOT
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size


class RemoteTableModel(QAbstractTableModel):
    """
    The base model for the tables in the Tribler GUI.
    It is specifically designed to fetch data from a remote data source, i.e. over a RESTful API.
    """
    on_sort = pyqtSignal(str, bool)
    columns = []

    def __init__(self, parent=None):
        super(RemoteTableModel, self).__init__(parent)
        self.data_items = []
        self.item_load_batch = 50
        self.total_items = 0  # The total number of items without pagination

    @abstractmethod
    def _get_remote_data(self, start, end, **kwargs):
        # This must call self._on_new_items_received as a callback when data received
        pass

    @abstractmethod
    def _set_remote_data(self):
        pass

    def reset(self):
        self.beginResetModel()
        self.data_items = []
        self.endResetModel()

    def sort(self, column, order):
        self.reset()
        self.on_sort.emit(self.columns[column], bool(order))

    def add_items(self, new_data_items):
        # If we want to block the signal like itemChanged, we must use QSignalBlocker object
        old_end = self.rowCount()
        new_end = self.rowCount() + len(new_data_items)
        if old_end == new_end:
            return
        self.beginInsertRows(QModelIndex(), old_end, new_end - 1)
        self.data_items.extend(new_data_items)
        self.endInsertRows()


class TriblerContentModel(RemoteTableModel):
    column_headers = []
    column_width = {}
    column_flags = {}
    column_display_filters = {}

    def __init__(self):
        RemoteTableModel.__init__(self, parent=None)
        self.data_items = []
        self.column_position = {name: i for i, name in enumerate(self.columns)}

    def headerData(self, num, orientation, role=None):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.column_headers[num]

    def _get_remote_data(self, start, end, **kwargs):
        pass

    def _set_remote_data(self):
        pass

    def rowCount(self, parent=QModelIndex()):
        return len(self.data_items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def flags(self, index):
        return self.column_flags[self.columns[index.column()]]

    def data(self, index, role):
        if role == Qt.DisplayRole:
            column = self.columns[index.column()]
            data = self.data_items[index.row()][column] if column in self.data_items[index.row()] else u'UNDEFINED'
            return self.column_display_filters.get(column, str(data))(data) \
                if column in self.column_display_filters else data


class SearchResultsContentModel(TriblerContentModel):
    """
    Model for a list that shows search results.
    """
    columns = [u'category', u'name', u'health', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'health', u'']
    column_flags = {
        u'category': Qt.ItemIsEnabled,
        u'name': Qt.ItemIsEnabled,
        u'health': Qt.ItemIsEnabled,
        ACTION_BUTTONS: Qt.ItemIsEnabled
    }

    def __init__(self):
        TriblerContentModel.__init__(self)
        self.type_filter = None


class ChannelsContentModel(TriblerContentModel):
    """
    This model represents a list of channels that can be displayed in a table view.
    """
    columns = [u'name', u'torrents', u'subscribed']
    column_headers = [u'Channel name', u'Torrents', u'']
    column_flags = {
        u'name': Qt.ItemIsEnabled,
        u'torrents': Qt.ItemIsEnabled,
        u'subscribed': Qt.ItemIsEnabled,
        ACTION_BUTTONS: Qt.ItemIsEnabled
    }

    def __init__(self, subscribed=False):
        TriblerContentModel.__init__(self)
        self.subscribed = subscribed


class TorrentsContentModel(TriblerContentModel):
    columns = [u'category', u'name', u'size', u'health', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'Size', u'Health', u'']
    column_flags = {
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'size': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'health': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        ACTION_BUTTONS: Qt.ItemIsEnabled | Qt.ItemIsSelectable
    }

    column_display_filters = {
        u'size': lambda data: format_size(float(data)),
    }

    def __init__(self, channel_pk=''):
        TriblerContentModel.__init__(self)

        self.channel_pk = channel_pk

        # This dict keeps the mapping of infohashes in data_items to indexes
        # It is used by Health Checker to track the health status updates across model refreshes
        self.infohashes = {}
        self.last_health_check_ts = {}

    def reset(self):
        # Health Checker related
        # Infohash to data_items mapping should be cleaned each time we refresh the model
        self.infohashes.clear()
        super(TorrentsContentModel, self).reset()

    def update_torrent_health(self, infohash, seeders, leechers, health):
        if infohash in self.infohashes:
            row = self.infohashes[infohash]
            self.data_items[row][u'num_seeders'] = seeders
            self.data_items[row][u'num_leechers'] = leechers
            self.data_items[row][u'health'] = health
            index = self.index(row, self.column_position[u'health'])
            self.dataChanged.emit(index, index, [])

    def check_torrent_health(self, index):
        timeout = 15
        infohash = self.data_items[index.row()][u'infohash']

        # TODO: move timeout check to the endpoint
        if infohash in self.last_health_check_ts and \
                (time.time() - self.last_health_check_ts[infohash] < timeout):
            return
        self.last_health_check_ts[infohash] = time.time()

        def on_cancel_health_check():
            pass

        def on_health_response(response):
            self.last_health_check_ts[infohash] = time.time()
            total_seeders = 0
            total_leechers = 0

            if not response or 'error' in response:
                self.update_torrent_health(infohash, 0, 0, HEALTH_ERROR)  # Just set the health to 0 seeders, 0 leechers
                return

            for _, status in response['health'].iteritems():
                if 'error' in status:
                    continue  # Timeout or invalid status
                total_seeders += int(status['seeders'])
                total_leechers += int(status['leechers'])

            if total_seeders > 0:
                health = HEALTH_GOOD
            elif total_leechers > 0:
                health = HEALTH_MOOT
            else:
                health = HEALTH_DEAD

            self.update_torrent_health(infohash, total_seeders, total_leechers, health)

        self.data_items[index.row()][u'health'] = HEALTH_CHECKING
        index_upd = self.index(index.row(), self.column_position[u'health'])
        self.dataChanged.emit(index_upd, index_upd, [])
        health_request_mgr = TriblerRequestManager()
        health_request_mgr.perform_request("torrents/%s/health?timeout=%s&refresh=%d" %
                                           (infohash, timeout, 1),
                                           on_health_response, capture_errors=False, priority="LOW",
                                           on_cancel=on_cancel_health_check)


class MyTorrentsContentModel(TorrentsContentModel):
    columns = [u'category', u'name', u'size', u'status']
    column_headers = [u'Category', u'Name', u'Size', u'']
    column_flags = {
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'size': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'status': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
    }
