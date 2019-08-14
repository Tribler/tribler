from __future__ import absolute_import

import uuid
from abc import abstractmethod

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from six import text_type

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from TriblerGUI.defs import ACTION_BUTTONS, BITTORRENT_BIRTHDAY, COMMIT_STATUS_TODELETE
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, format_votes, pretty_date


def sanitize_for_fts(text):
    return text_type(text).translate({ord(u"\""): u"\"\"", ord(u"\'"): u"\'\'"})


def to_fts_query(text):
    if not text:
        return ""
    words = text.split(" ")

    # TODO: add support for quoted exact searches
    query_list = [u'\"' + sanitize_for_fts(word) + u'\"*' for word in words]

    return " AND ".join(query_list)


def combine_pk_id(pk, id_):
    return "%s:%s" % (pk, id_)


class RemoteTableModel(QAbstractTableModel):
    info_changed = pyqtSignal(list)
    """
    The base model for the tables in the Tribler GUI.
    It is specifically designed to fetch data from a remote data source, i.e. over a RESTful API.
    """

    default_sort_column = -1

    columns = []
    unsortable_columns = []

    def __init__(self, parent=None):
        super(RemoteTableModel, self).__init__(parent)
        self.data_items = []
        self.item_load_batch = 50

        # Unique identifier mapping for items. For torrents, it is infohash and for channels, it is concatenated value
        # of public key and channel id
        self.item_uid_map = {}

        self.sort_by = self.columns[self.default_sort_column] if self.default_sort_column >= 0 else None
        self.sort_desc = True

        self.query_uuid = None

    @abstractmethod
    def get_item_uid(self, item):
        pass

    def reset(self):
        self.beginResetModel()
        self.data_items = []
        self.item_uid_map = {}
        self.endResetModel()
        self.perform_query()

    def sort(self, column_index, order):
        if self.columns[column_index] in self.unsortable_columns:
            return
        # If the column number is set to -1, this means we do not want to do sorting at all
        # We have to set it to something (-1), because QT does not support setting it to "None"
        self.sort_by = self.columns[column_index] if column_index >= 0 else None
        self.sort_desc = bool(order)
        self.reset()

    def add_items(self, new_items, remote=False):
        """
        Adds new items to the table model. All items are mapped to their unique ids to avoid the duplicates.
        If the new items are remote then the items are prepended to the top else appended to the end of the model.
        :param new_items: list(item)
        :param remote: True if new_items are received from remote peers else False for local items
        :return: None
        """
        if not new_items:
            return

        # Note: If we want to block the signal like itemChanged, we must use QSignalBlocker object

        # Only add unique items to the table model and reverse mapping from unique ids to rows is built.
        # If items are remote, prepend to the top else append to the end of the model.
        new_items_map = {}
        insert_index = len(self.data_items) if not remote else 0
        unique_new_items = []
        for item in new_items:
            item_uid = self.get_item_uid(item)

            if item_uid and item_uid not in self.item_uid_map:
                new_items_map[item_uid] = insert_index
                unique_new_items.append(item)
                insert_index += 1

        # If no new items are found, skip
        if not unique_new_items:
            return

        # Else if remote items, to make space for new unique items update the position of the existing items
        if remote:
            for item in self.data_items:
                old_item_uid = self.get_item_uid(item)
                if old_item_uid in self.item_uid_map:
                    new_items_map[old_item_uid] = insert_index + self.item_uid_map[old_item_uid]

        # Update the table model
        if remote:
            self.beginInsertRows(QModelIndex(), 0, len(unique_new_items) - 1)
            self.data_items = unique_new_items + self.data_items
        else:
            self.beginInsertRows(QModelIndex(), len(self.data_items), len(self.data_items) + len(unique_new_items) - 1)
            self.data_items.extend(unique_new_items)
        self.item_uid_map = new_items_map
        self.endInsertRows()

    def remove_items(self, items):
        uids_to_remove = []
        rows_to_remove = []
        for item in items:
            uid = self.get_item_uid(item)
            row = self.item_uid_map.get(uid, None)
            if row is not None:
                uids_to_remove.append(uid)
                rows_to_remove.append(row)

        if not rows_to_remove:
            return

        # Rows to remove must be grouped into continuous regions.
        # We have to remove the rows in a reversed order because otherwise row indexes
        # would be affected by the previous deletions.
        rows_to_remove.sort(reverse=True)
        groups = []
        for n, row in enumerate(rows_to_remove):
            if n == 0:
                groups.append([row])
            elif row == (rows_to_remove[n - 1] - 1):
                groups[-1].append(row)
            else:
                groups.append([row])

        for uid in uids_to_remove:
            self.item_uid_map.pop(uid)
        for group in groups:
            first, last = group[0], group[-1]
            self.beginRemoveRows(QModelIndex(), first, last)
            for row in group:
                del self.data_items[row]
            self.endRemoveRows()

        # Update uids of the shifted rows
        for n, item in enumerate(self.data_items):
            if n > rows_to_remove[0]:  # start just after the last removed row
                self.item_uid_map[self.get_item_uid(item)] = n

        self.info_changed.emit(items)

    def perform_query(self, **kwargs):
        """
        Fetch results for a given query.
        """
        if 'first' not in kwargs or 'last' not in kwargs:
            kwargs["first"], kwargs['last'] = self.rowCount() + 1, self.rowCount() + self.item_load_batch

        # Create a new uuid for each new search
        if kwargs['first'] == 1 or not self.query_uuid:
            self.query_uuid = uuid.uuid4().hex
        kwargs.update({"uuid": self.query_uuid})

        if self.sort_by is not None:
            kwargs.update({"sort_by": self.sort_by, "sort_desc": self.sort_desc})

        if 'query_filter' in kwargs:
            kwargs.update({"filter": to_fts_query(kwargs.pop('query_filter'))})
        elif self.text_filter:
            kwargs.update({"filter": self.text_filter})

        if self.hide_xxx is not None:
            kwargs.update({"hide_xxx": self.hide_xxx})
        rest_endpoint_url = kwargs.pop("rest_endpoint_url") if "rest_endpoint_url" in kwargs else self.endpoint_url

        self.request_mgr1 = TriblerRequestManager()
        self.request_mgr1.perform_request(rest_endpoint_url, self.on_query_results, url_params=kwargs)

    def on_query_results(self, response, remote=False):
        """
        Updates the table with the response.
        :param response: List of the items to be added to the model
        :param remote: True if response is from a remote peer. Default: False
        :return: True, if response, False otherwise
        """
        # TODO: count remote results
        if not response:
            return False

        if self.is_new_result(response):
            self.add_items(response['results'], remote=remote)
            if "total" in response:
                self.channel_info["total"] = response["total"]
                self.info_changed.emit(response['results'])

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


class ChannelContentModel(RemoteTableModel):

    columns = [u'category', u'name', u'size', u'health', u'updated', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'Size', u'Health', u'Updated', u'']
    unsortable_columns = [u'status', u'state', ACTION_BUTTONS]
    column_flags = {
        u'subscribed': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'torrents': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'size': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'updated': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'health': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'votes': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'state': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'status': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        ACTION_BUTTONS: Qt.ItemIsEnabled | Qt.ItemIsSelectable,
    }

    column_width = {u'state': lambda _: 20, u'name': lambda table_width: table_width - 600}

    column_tooltip_filters = {
        u'state': lambda data: data,
        u'votes': lambda data: "{0:.0%}".format(float(data)) if data else None,
    }

    column_display_filters = {
        u'size': lambda data: (format_size(float(data)) if data != '' else ''),
        u'votes': format_votes,
        u'state': lambda data: str(data)[:1] if data == u'Downloading' else "",
        u'updated': lambda timestamp: pretty_date(timestamp) if timestamp > BITTORRENT_BIRTHDAY else 'N/A',
    }

    def __init__(
        self,
        channel_info=None,
        hide_xxx=None,
        exclude_deleted=None,
        subscribed_only=None,
        endpoint_url=None,
        text_filter='',
    ):
        RemoteTableModel.__init__(self, parent=None)
        self.column_position = {name: i for i, name in enumerate(self.columns)}

        self.data_items = []

        # Remote query (model) parameters
        self.hide_xxx = hide_xxx
        self.text_filter = text_filter
        self.subscribed_only = subscribed_only
        self.exclude_deleted = exclude_deleted
        self.type_filter = None
        self.category_filter = None

        # Current channel attributes. This is intentionally NOT copied, so local changes
        # can propagate to the origin, e.g. parent channel.
        self.channel_info = channel_info or {"name": "Personal channels root", "status": 123}

        self.endpoint_url_override = endpoint_url
        self.query_uuid = None

        # Load the initial batch of entries
        self.perform_query()

    @property
    def edit_enabled(self):
        return self.channel_info.get("state", None) == "Personal"

    @property
    def endpoint_url(self):
        return self.endpoint_url_override or "channels/%s/%i" % (
            self.channel_info["public_key"],
            self.channel_info["id"],
        )

    def headerData(self, num, orientation, role=None):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.column_headers[num]

    def get_item_uid(self, item):
        item_uid = None
        if "infohash" in item:
            item_uid = item['infohash']
        elif "public_key" in item and "id" in item:
            item_uid = combine_pk_id(item['public_key'], item['id'])
        return item_uid

    def rowCount(self, parent=QModelIndex()):
        return len(self.data_items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def flags(self, index):
        return self.column_flags[self.columns[index.column()]]

    def filter_item_txt(self, txt_filter, index, show_default=True):
        column = self.columns[index.column()]
        item = self.data_items[index.row()]
        data = item.get(column, u'')

        # Print number of torrents in the channel for channel rows in the "size" column
        if (
            column == "size"
            and "torrents" not in self.columns
            and "torrents" in item
            and item["type"] in (CHANNEL_TORRENT, COLLECTION_NODE)
        ):
            return item["torrents"]

        if column in txt_filter:
            display_txt = txt_filter.get(column, str(data))(data)
        elif show_default:
            display_txt = data
        else:
            display_txt = None
        return display_txt

    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self.filter_item_txt(self.column_display_filters, index)
        elif role == Qt.ToolTipRole:
            return self.filter_item_txt(self.column_tooltip_filters, index, show_default=False)
        elif role == Qt.TextAlignmentRole:
            if index.column() == self.column_position.get(u'votes', -1):
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def reset(self):
        self.item_uid_map.clear()
        super(ChannelContentModel, self).reset()

    def update_node_info(self, update_dict):
        row = self.item_uid_map.get(
            update_dict["infohash"]
            if "infohash" in update_dict
            else combine_pk_id(update_dict["public_key"], update_dict["id"])
        )
        if row is not None:
            self.data_items[row].update(**update_dict)
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.columns)), [])

    def perform_query(self, **kwargs):
        """
        Fetch search results.
        """

        if self.type_filter is not None:
            kwargs.update({"metadata_type": self.type_filter})
        if self.subscribed_only is not None:
            kwargs.update({"subscribed": self.subscribed_only})
        if self.exclude_deleted is not None:
            kwargs.update({"exclude_deleted": self.exclude_deleted})
        if self.category_filter is not None:
            if self.category_filter == "Channels":
                kwargs.update({'metadata_type': 'channel'})
            else:
                kwargs.update({"category": self.category_filter})

        if "total" not in self.channel_info:
            # Only include total for the first query to the endpoint
            kwargs.update({"include_total": 1})

        super(ChannelContentModel, self).perform_query(**kwargs)

    def is_torrent_item(self, row_id):
        data_item = self.data_items[row_id]
        if u'infohash' in data_item or (u'type' in data_item and data_item[u'type'] == REGULAR_TORRENT):
            return True
        return False

    def is_channel_item(self, row_id):
        data_item = self.data_items[row_id]
        if u'infohash' in data_item or (u'type' in data_item and data_item[u'type'] == CHANNEL_TORRENT):
            return True
        return False

    def setData(self, index, new_value, role=None):
        if role != Qt.EditRole:
            return True
        public_key = self.data_items[index.row()][u'public_key']
        id_ = self.data_items[index.row()][u'id']
        attribute_name = self.columns[index.column()]
        attribute_name = u'tags' if attribute_name == u'category' else attribute_name
        attribute_name = u'title' if attribute_name == u'name' else attribute_name
        attribute_name = u'subscribed' if attribute_name == u'votes' else attribute_name

        def on_row_update_results(response):
            if not response:
                return
            data_item_dict = index.model().data_items[index.row()]
            for key, _ in data_item_dict.items():
                if key in response:
                    data_item_dict[key] = response[key]
            self.info_changed.emit([data_item_dict])

        self.request_mgr_sd = TriblerRequestManager()
        self.request_mgr_sd.perform_request(
            "metadata/%s/%s" % (public_key, id_),
            on_row_update_results,
            method='PATCH',
            raw_data=json.twisted_dumps({attribute_name: new_value}),
        )

        # TODO: reload the whole row from DB instead of just changing the displayed value
        self.data_items[index.row()][self.columns[index.column()]] = new_value
        return True


class SearchResultsModel(ChannelContentModel):
    def __init__(self, **kwargs):
        ChannelContentModel.__init__(self, **kwargs)

    def on_new_entry_received(self, response):
        self.on_query_results(response, remote=True)


class DiscoveredChannelsModel(SearchResultsModel):
    columns = [u'state', u'votes', u'name', u'torrents', u'updated']
    column_headers = [u'', u'Popularity', u'Name', u'Torrents', u'Updated']

    column_width = {u'state': lambda _: 20, u'name': lambda table_width: table_width - 320}

    default_sort_column = 1


class PersonalChannelsModel(ChannelContentModel):
    columns = [u'category', u'name', u'size', u'status', ACTION_BUTTONS]
    column_headers = [u'Category', u'Name', u'Size', u'', u'']

    column_flags = dict(ChannelContentModel.column_flags)
    column_flags.update(
        {
            u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
            u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
        }
    )

    def delete_rows(self, rows):

        patch_data = []
        delete_data = []
        for entry in [row.model().data_items[row.row()] for row in rows]:
            if entry["status"] == NEW:
                delete_data.append({"public_key": entry[u'public_key'], "id": entry[u'id']})
            else:
                patch_data.append(
                    {"public_key": entry[u'public_key'], "id": entry[u'id'], "status": COMMIT_STATUS_TODELETE}
                )

        def on_torrents_deleted(json_result):
            if not json_result:
                return
            # TODO: reload only the changed rows
            self.reset()
            self.info_changed.emit(json_result)

        if patch_data:
            request_mgrp = TriblerRequestManager()
            request_mgrp.perform_request(
                "metadata", on_torrents_deleted, raw_data=json.twisted_dumps(patch_data), method='PATCH'
            )
        if delete_data:
            request_mgrp = TriblerRequestManager()
            request_mgrp.perform_request(
                "metadata", on_torrents_deleted, raw_data=json.twisted_dumps(delete_data), method='DELETE'
            )

    def create_new_channel(self):
        self.mgr_nc = TriblerRequestManager()
        url = (
            self.endpoint_url_override or "channels/%s/%i" % (self.channel_info["public_key"], self.channel_info["id"])
        ) + ("/channels" if self.channel_info.get("id", 0) == 0 else "/collections")
        self.mgr_nc.perform_request(url, self.on_query_results, method='POST')

    def on_query_results(self, response, **kwargs):
        if super(PersonalChannelsModel, self).on_query_results(response, **kwargs):
            if response.get("results", None):
                self.info_changed.emit(response["results"])
