from __future__ import absolute_import

from abc import abstractmethod

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from TriblerGUI.defs import ACTION_BUTTONS
from TriblerGUI.utilities import format_size, pretty_date


class RemoteTableModel(QAbstractTableModel):
    """
    The base model for the tables in the Tribler GUI.
    It is specifically designed to fetch data from a remote data source, i.e. over a RESTful API.
    """
    on_sort = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(RemoteTableModel, self).__init__(parent)
        self.data_items = []
        self.item_load_batch = 50
        self.total_items = 0  # The total number of items without pagination
        self.infohashes = {}

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
        if not new_data_items:
            return
        # If we want to block the signal like itemChanged, we must use QSignalBlocker object
        old_end = self.rowCount()
        new_end = self.rowCount() + len(new_data_items)
        self.beginInsertRows(QModelIndex(), old_end, new_end - 1)
        self.data_items.extend(new_data_items)
        self.endInsertRows()


class TriblerContentModel(RemoteTableModel):
    column_headers = []
    column_width = {}
    column_flags = {}
    column_display_filters = {}

    def __init__(self, hide_xxx=False):
        RemoteTableModel.__init__(self, parent=None)
        self.data_items = []
        self.column_position = {name: i for i, name in enumerate(self.columns)}
        self.edit_enabled = False
        self.hide_xxx = hide_xxx

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

    def add_items(self, new_data_items):
        super(TriblerContentModel, self).add_items(new_data_items)
        # Build reverse mapping from infohashes to rows
        items_len = len(self.data_items)
        new_items_len = len(new_data_items)
        for i, item in enumerate(new_data_items):
            if "infohash" in item and item['infohash'] not in self.infohashes:
                self.infohashes[item["infohash"]] = items_len - new_items_len + i

    def reset(self):
        self.infohashes.clear()
        super(TriblerContentModel, self).reset()

    def update_torrent_info(self, update_dict):
        row = self.infohashes.get(update_dict["infohash"])
        if row:
            self.data_items[row].update(**update_dict)
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.columns)), [])


class SearchResultsContentModel(TriblerContentModel):
    """
    Model for a list that shows search results.
    """
    columns = [u'category', u'name', u'health', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'health', u'']
    column_flags = {
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'health': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        ACTION_BUTTONS: Qt.ItemIsEnabled | Qt.ItemIsSelectable
    }

    def __init__(self, **kwargs):
        TriblerContentModel.__init__(self, **kwargs)
        self.type_filter = None

    def add_remote_items(self, remote_items):
        new_infohash_map = {}

        # Add new unique items to the top
        insert_index = 0
        unique_items = []
        for item in remote_items:
            if "infohash" in item and item["infohash"] not in self.infohashes:
                new_infohash_map[item["infohash"]] = insert_index
                unique_items.append(item)
                insert_index += 1

        # Shift the rest of the items
        for item in self.data_items:
            if "infohash" in item and item["infohash"] in self.infohashes:
                new_infohash_map[item['infohash']] = insert_index + self.infohashes[item["infohash"]]

        # Update the table
        self.beginInsertRows(QModelIndex(), 0, len(self.data_items) + len(unique_items)-1)
        self.data_items = unique_items + self.data_items
        self.infohashes = new_infohash_map
        self.endInsertRows()


class ChannelsContentModel(TriblerContentModel):
    """
    This model represents a list of channels that can be displayed in a table view.
    """
    columns = [u'name', u'torrents', u'updated', u'subscribed']
    column_headers = [u'Channel name', u'Torrents', u'Updated', u'']
    column_flags = {
        u'name': Qt.ItemIsEnabled,
        u'torrents': Qt.ItemIsEnabled,
        u'updated': Qt.ItemIsEnabled,
        u'subscribed': Qt.ItemIsEnabled,
        ACTION_BUTTONS: Qt.ItemIsEnabled
    }
    column_display_filters = {
        u'updated': pretty_date,
    }

    def __init__(self, subscribed=False, **kwargs):
        TriblerContentModel.__init__(self, **kwargs)
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

    def __init__(self, channel_pk='', **kwargs):
        TriblerContentModel.__init__(self, **kwargs)
        self.channel_pk = channel_pk


class MyTorrentsContentModel(TorrentsContentModel):
    columns = [u'category', u'name', u'size', u'status', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'Size', u'', u'']
    column_flags = {
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'size': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'status': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        ACTION_BUTTONS: Qt.ItemIsEnabled | Qt.ItemIsSelectable
    }

    def __init__(self, channel_pk='', **kwargs):
        TorrentsContentModel.__init__(self, channel_pk=channel_pk, **kwargs)
        self.exclude_deleted = False
        self.edit_enabled = True
