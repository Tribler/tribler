import json
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSize, Qt, pyqtSignal

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, CHANNEL_STATE
from tribler_common.utilities import to_fts_query

from tribler_core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import BITTORRENT_BIRTHDAY, COMMIT_STATUS_TODELETE, HEALTH_CHECKING
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import (
    connect,
    format_size,
    format_votes,
    get_votes_rating_description,
    pretty_date,
    tr,
)

EXPANDING = 0


class Column(Enum):
    ACTIONS = auto()
    CATEGORY = auto()
    NAME = auto()
    SIZE = auto()
    HEALTH = auto()
    UPDATED = auto()
    VOTES = auto()
    STATUS = auto()
    STATE = auto()
    TORRENTS = auto()
    SUBSCRIBED = auto()


@dataclass
class ColumnDefinition:
    dict_key: str
    header: str
    width: int = 50
    tooltip_filter: Callable[[str], str] = field(default_factory=lambda: (lambda tooltip: None))
    display_filter: Callable[[str], str] = field(default_factory=lambda: (lambda txt: txt))
    sortable: bool = True
    qt_flags: Qt.ItemFlags = Qt.ItemIsEnabled | Qt.ItemIsSelectable


def define_columns():
    d = ColumnDefinition
    # fmt:off
    # pylint: disable=line-too-long
    columns_dict = {
        Column.ACTIONS:    d('',           "",               width=60, sortable=False),
        Column.CATEGORY:   d('category',   "",               width=30, tooltip_filter=lambda data: data),
        Column.NAME:       d('',           tr("Name"),       width=EXPANDING),
        Column.SIZE:       d('size',       tr("Size"),       width=90, display_filter=lambda data: (format_size(float(data)) if data != "" else "")),
        Column.HEALTH:     d('health',     tr("Health"),     width=120, tooltip_filter=lambda data: f"{data}" + ('' if data == HEALTH_CHECKING else '\n(Click to recheck)'),),
        Column.UPDATED:    d('updated',    tr("Updated"),    width=120, display_filter=lambda timestamp: pretty_date(timestamp) if timestamp and timestamp > BITTORRENT_BIRTHDAY else 'N/A',),
        Column.VOTES:      d('votes',      tr("Popularity"), width=120, display_filter=format_votes, tooltip_filter=lambda data: get_votes_rating_description(data) if data is not None else None,),
        Column.STATUS:     d('status',     "",               sortable=False),
        Column.STATE:      d('state',      "",               width=80, tooltip_filter=lambda data: data, sortable=False),
        Column.TORRENTS:   d('torrents',   tr("Torrents"),   width=90),
        Column.SUBSCRIBED: d('subscribed', tr("Subscribed"), width=95),
    }
    # pylint: enable=line-too-long
    # fmt:on
    return columns_dict


def get_item_uid(item):
    if 'public_key' in item and 'id' in item:
        return f"{item['public_key']}:{item['id']}"
    return item['infohash']


class RemoteTableModel(QAbstractTableModel):
    info_changed = pyqtSignal(list)
    query_complete = pyqtSignal()
    query_started = pyqtSignal()
    """
    The base model for the tables in the Tribler GUI.
    It is specifically designed to fetch data from a remote data source, i.e. over a RESTful API.
    """

    default_sort_column = -1

    def __init__(self, parent=None):

        super().__init__(parent)
        # Unique identifier mapping for items. For torrents, it is infohash and for channels, it is concatenated value
        # of public key and channel id
        self.item_uid_map = {}

        # ACHTUNG! The reason why this is here and not in the class variable is, QT i18 only works for
        # tr() entries defined in the class instance constructor
        self.columns_dict = define_columns()

        self.data_items = []
        self.remote_items = []
        self.max_rowid = None
        self.local_total = None
        self.item_load_batch = 50
        self.sort_by = self.columns[self.default_sort_column].dict_key if self.default_sort_column >= 0 else None
        self.sort_desc = True
        self.saved_header_state = None
        self.saved_scroll_state = None
        self.qt_object_destroyed = False

        connect(self.destroyed, self.on_destroy)
        # Every remote query must be attributed to its specific model to avoid updating wrong models
        # on receiving a result. We achieve this by maintaining a set of in-flight remote queries.
        # Note that this only applies to results that are returned through the events notification
        # mechanism, because REST requests attribution is maintained by the RequestManager.
        # We do not clean it up after receiving a result because we don't know if the result was the
        # last one. In a sense, the queries' UUIDs play the role of "subscription topics" for the model.
        self.remote_queries = set()

        self.loaded = False

    @property
    def columns(self):
        return tuple(self.columns_dict[c] for c in self.columns_shown)

    @property
    def min_columns_width(self):
        return sum(c.width for c in self.columns)

    @property
    def all_local_entries_loaded(self):
        return self.local_total is not None and self.local_total <= len(self.data_items)

    def on_destroy(self, *args):
        self.qt_object_destroyed = True

    def reset(self):
        self.beginResetModel()
        self.loaded = False
        self.data_items = []
        self.remote_items = []
        self.max_rowid = None
        self.local_total = None
        self.item_uid_map = {}
        self.endResetModel()
        self.perform_query()

    def sort(self, column_index, order):
        if not self.columns[column_index].sortable:
            return
        # If the column number is set to -1, this means we do not want to do sorting at all
        # We have to set it to something (-1), because QT does not support setting it to "None"
        self.sort_by = self.columns[column_index].dict_key if column_index >= 0 else None
        self.sort_desc = bool(order)
        self.reset()

    def add_items(self, new_items, on_top=False, remote=False):
        """
        Adds new items to the table model. All items are mapped to their unique ids to avoid the duplicates.
        New items are prepended to the end of the model.
        Note that item_uid_map tracks items twice: once by public_key+id and once by infohash. This is necessary to
        support status updates from TorrentChecker based on infohash only.
        :param new_items: list(item)
        :param on_top: True if new_items should be added on top of the table
        :param remote: True if new_items are from a remote peer. Default: False
        :return: None
        """
        if not new_items:
            return

        if remote and not self.all_local_entries_loaded:
            self.remote_items.extend(new_items)
            return

        # Note: If we want to block the signal like itemChanged, we must use QSignalBlocker object or blockSignals

        # Only add unique items to the table model and reverse mapping from unique ids to rows is built.
        insert_index = 0 if on_top else len(self.data_items)
        unique_new_items = []
        for item in new_items:
            item_uid = get_item_uid(item)
            if item_uid not in self.item_uid_map:
                self.item_uid_map[item_uid] = insert_index
                if 'infohash' in item:
                    self.item_uid_map[item['infohash']] = insert_index
                unique_new_items.append(item)
                insert_index += 1

        # If no new items are found, skip
        if not unique_new_items:
            return

        # Else if remote items, to make space for new unique items shift the existing items
        if on_top and insert_index > 0:
            new_items_map = {}
            for item in self.data_items:
                old_item_uid = get_item_uid(item)
                if old_item_uid in self.item_uid_map:
                    shifted_index = insert_index + self.item_uid_map[old_item_uid]
                    new_items_map[old_item_uid] = shifted_index
                    if 'infohash' in item:
                        new_items_map[item['infohash']] = shifted_index
            self.item_uid_map.update(new_items_map)

        # Update the table model
        if on_top:
            self.beginInsertRows(QModelIndex(), 0, len(unique_new_items) - 1)
            self.data_items = unique_new_items + self.data_items
        else:
            self.beginInsertRows(QModelIndex(), len(self.data_items), len(self.data_items) + len(unique_new_items) - 1)
            self.data_items.extend(unique_new_items)
        self.endInsertRows()

        if self.all_local_entries_loaded:
            remote_items = self.remote_items
            self.remote_items = []
            self.add_items(remote_items, remote=True)  # to filter non-unique entries

    def remove_items(self, items):
        uids_to_remove = []
        rows_to_remove = []
        for item in items:
            uid = get_item_uid(item)
            row = self.item_uid_map.get(uid)
            if row is not None:
                uids_to_remove.append(uid)
                rows_to_remove.append(row)

        if not rows_to_remove:
            return

        # Rows to remove must be grouped into continuous regions.
        # We have to remove the rows in a reversed order because otherwise row indexes
        # would be affected by the previous deletions.
        rows_to_remove_reversed = sorted(rows_to_remove, reverse=True)
        groups = []
        for n, row in enumerate(rows_to_remove_reversed):
            if n == 0:
                groups.append([row])
            elif row == (rows_to_remove_reversed[n - 1] - 1):
                groups[-1].append(row)
            else:
                groups.append([row])

        for uid in uids_to_remove:
            self.item_uid_map.pop(uid)
        for group in groups:
            first, last = group[-1], group[0]
            self.beginRemoveRows(QModelIndex(), first, last)
            for row in group:
                del self.data_items[row]
            self.endRemoveRows()

        # Update uids of the shifted rows
        for n, item in enumerate(self.data_items):
            if n >= rows_to_remove[0]:  # start from the first removed row
                self.item_uid_map[get_item_uid(item)] = n

        self.info_changed.emit(items)

    def perform_query(self, **kwargs):
        """
        Fetch results for a given query.
        """
        self.query_started.emit()
        if 'first' not in kwargs or 'last' not in kwargs:
            kwargs["first"], kwargs['last'] = self.rowCount() + 1, self.rowCount() + self.item_load_batch

        if self.sort_by is not None:
            kwargs.update({"sort_by": self.sort_by, "sort_desc": self.sort_desc})

        if self.text_filter:
            kwargs.update({"txt_filter": to_fts_query(self.text_filter)})

        if self.max_rowid is not None:
            kwargs["max_rowid"] = self.max_rowid

        if self.hide_xxx is not None:
            kwargs.update({"hide_xxx": self.hide_xxx})
        rest_endpoint_url = kwargs.pop("rest_endpoint_url") if "rest_endpoint_url" in kwargs else self.endpoint_url

        TriblerNetworkRequest(rest_endpoint_url, self.on_query_results, url_params=kwargs)

    def on_query_results(self, response, remote=False, on_top=False):
        """
        Updates the table with the response.
        :param response: List of the items to be added to the model
        :param remote: True if response is from a remote peer. Default: False
        :param on_top: True if items should be added at the top of the list
        :return: True, if response, False otherwise
        """
        if not response or self.qt_object_destroyed:
            return False

        # Trigger labels update on the initial table load
        update_labels = len(self.data_items) == 0

        if not remote or (uuid.UUID(response.get('uuid')) in self.remote_queries):
            prev_total = self.channel_info.get("total")
            if not remote:
                if "total" in response:
                    self.local_total = response["total"]
                    self.channel_info["total"] = self.local_total + len(self.remote_items)
            elif self.channel_info.get("total"):
                self.channel_info["total"] += len(response["results"])

            if prev_total != self.channel_info.get("total"):
                update_labels = True

            self.add_items(response['results'], on_top=on_top, remote=remote)

            if update_labels:
                self.info_changed.emit(response['results'])

        self.query_complete.emit()
        self.loaded = True
        return True


class ChannelContentModel(RemoteTableModel):

    columns_shown = (Column.ACTIONS, Column.CATEGORY, Column.NAME, Column.SIZE, Column.HEALTH, Column.UPDATED)

    def __init__(
        self,
        channel_info=None,
        hide_xxx=None,
        exclude_deleted=None,
        subscribed_only=None,
        endpoint_url=None,
        text_filter='',
        type_filter=None,
    ):
        RemoteTableModel.__init__(self, parent=None)

        self.column_position = {name: i for i, name in enumerate(self.columns_shown)}
        self.name_column_width = 0

        # Remote query (model) parameters
        self.hide_xxx = hide_xxx
        self.text_filter = text_filter
        self.subscribed_only = subscribed_only
        self.exclude_deleted = exclude_deleted
        self.type_filter = type_filter
        self.category_filter = None

        # Stores metadata of the 'edit tags' button in each cell.
        self.edit_tags_rects: Dict[QModelIndex, QRectF] = {}

        # Current channel attributes. This is intentionally NOT copied, so local changes
        # can propagate to the origin, e.g. parent channel.
        self.channel_info = channel_info or {"name": "My channels", "status": 123}

        self.endpoint_url_override = endpoint_url

        # Load the initial batch of entries
        self.perform_query()

    @property
    def edit_enabled(self):
        return False

    @property
    def endpoint_url(self):
        return self.endpoint_url_override or "channels/%s/%i" % (
            self.channel_info["public_key"],
            self.channel_info["id"],
        )

    def headerData(self, num, orientation, role=None):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[num].header
        if role == Qt.InitialSortOrderRole and num != self.column_position.get(Column.NAME):
            return Qt.DescendingOrder
        if role == Qt.TextAlignmentRole:
            alignment = (
                Qt.AlignHCenter
                if num in [self.column_position.get(Column.SUBSCRIBED), self.column_position.get(Column.TORRENTS)]
                else Qt.AlignLeft
            )
            return alignment | Qt.AlignVCenter
        if role == Qt.SizeHintRole:
            # It seems that Qt first queries - this signals that the row height is exclusively decided by the size
            # hints returned by the data() method.
            return QSize(0, 0)
        return super().headerData(num, orientation, role)

    def rowCount(self, *_, **__):
        return len(self.data_items)

    def columnCount(self, *_, **__):
        return len(self.columns)

    def flags(self, index):
        return self.columns[index.column()].qt_flags

    def item_txt(self, index, role):
        # ACHTUNG! Dumb workaround for some mysterious race condition
        try:
            item = self.data_items[index.row()]
        except IndexError:
            return ""

        column = self.columns[index.column()]
        column_type = self.columns_shown[index.column()]
        data = item.get(column.dict_key, '')

        # Print number of torrents in the channel for channel rows in the "size" column
        if (
            column_type == Column.SIZE
            and "torrents" not in self.columns
            and "torrents" in item
            and item["type"] in (CHANNEL_TORRENT, COLLECTION_NODE)
        ):
            return item["torrents"]

        # 'subscribed' column gets special treatment in case of ToolTipRole, because
        # its tooltip uses information from both 'subscribed' and 'state' keys
        if role == Qt.ToolTipRole and column_type == Column.SUBSCRIBED and 'subscribed' in item and 'state' in item:
            state_message = f" ({item['state']})" if item['state'] != CHANNEL_STATE.COMPLETE.value else ""
            tooltip_txt = (
                tr("Subscribed.%s\n(Click to unsubscribe)") % state_message
                if item['subscribed']
                else tr("Not subscribed.\n(Click to subscribe)")
            )
            return tooltip_txt

        return (column.tooltip_filter if role == Qt.ToolTipRole else column.display_filter)(data)

    def data(self, index, role):
        if role in (Qt.DisplayRole, Qt.EditRole, Qt.ToolTipRole):
            return self.item_txt(index, role)
        if role == Qt.TextAlignmentRole:
            if index.column() == self.column_position.get(Column.VOTES, -1):
                return Qt.AlignLeft | Qt.AlignVCenter
            if index.column() == self.column_position.get(Column.TORRENTS, -1):
                return Qt.AlignHCenter | Qt.AlignVCenter
        return None

    def reset(self):
        self.item_uid_map.clear()
        self.edit_tags_rects.clear()
        super().reset()

    def update_node_info(self, update_dict):
        """
        This method updates/inserts rows based on updated_dict. It should be typically invoked
        by a signal from Events endpoint. One special case it when the channel_info of the model
        itself is updated. In that case, info_changed signal is emitted, so the controller/widget knows
        it is time to update the labels.
        """

        if (
            self.channel_info.get("public_key") == update_dict.get("public_key") is not None
            and self.channel_info.get("id") == update_dict.get("id") is not None
        ):
            self.channel_info.update(**update_dict)
            self.info_changed.emit([])
            return

        row = self.item_uid_map.get(get_item_uid(update_dict))
        if row is not None and row < len(self.data_items):
            self.data_items[row].update(**update_dict)
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.columns)), [])

    def perform_query(self, **kwargs):
        """
        Fetch search results.
        """

        if self.type_filter is not None:
            kwargs.update({"metadata_type": self.type_filter})
        else:
            kwargs.update({"metadata_type": [REGULAR_TORRENT, COLLECTION_NODE]})
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

        super().perform_query(**kwargs)

    def setData(self, index, new_value, role=None):
        if role != Qt.EditRole:
            return True
        item = self.data_items[index.row()]
        attribute_name = self.columns[index.column()].dict_key
        attribute_name = 'tags' if attribute_name == 'category' else attribute_name
        attribute_name = 'title' if attribute_name == 'name' else attribute_name

        if attribute_name == 'subscribed':
            return True

        def on_row_update_results(response):
            if not response:
                return
            item_row = self.item_uid_map.get(get_item_uid(item))
            if item_row is None:
                return
            data_item_dict = index.model().data_items[item_row]
            data_item_dict.update(response)
            self.info_changed.emit([data_item_dict])

        TriblerNetworkRequest(
            f"metadata/{item['public_key']}/{item['id']}",
            on_row_update_results,
            method='PATCH',
            raw_data=json.dumps({attribute_name: new_value}),
        )

        # ACHTUNG: instead of reloading the whole row from DB, this line just changes the displayed value!
        self.data_items[index.row()][attribute_name] = new_value
        return True

    def on_new_entry_received(self, response):
        self.on_query_results(response, remote=True)


class ChannelPreviewModel(ChannelContentModel):
    def perform_query(self, **kwargs):
        kwargs["remote"] = True
        super().perform_query(**kwargs)


class SearchResultsModel(ChannelContentModel):
    pass


class PopularTorrentsModel(ChannelContentModel):
    columns_shown = (Column.CATEGORY, Column.NAME, Column.SIZE, Column.UPDATED)

    def __init__(self, *args, **kwargs):
        kwargs["endpoint_url"] = 'channels/popular_torrents'
        super().__init__(*args, **kwargs)


class DiscoveredChannelsModel(ChannelContentModel):
    columns_shown = (Column.SUBSCRIBED, Column.NAME, Column.STATE, Column.TORRENTS, Column.VOTES, Column.UPDATED)

    @property
    def default_sort_column(self):
        return self.columns_shown.index(Column.VOTES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Subscribe to new channels updates notified over the Events endpoint
        self.remote_queries.add(CHANNELS_VIEW_UUID)


class PersonalChannelsModel(ChannelContentModel):
    columns_shown = (
        Column.ACTIONS,
        Column.CATEGORY,
        Column.NAME,
        Column.SIZE,
        Column.HEALTH,
        Column.UPDATED,
        Column.STATUS,
    )

    def __init__(self, *args, **kwargs):
        kwargs["hide_xxx"] = kwargs.get("hide_xxx", False)
        super().__init__(*args, **kwargs)
        self.columns[self.column_position[Column.CATEGORY]].qt_flags |= Qt.ItemIsEditable
        self.columns[self.column_position[Column.NAME]].qt_flags |= Qt.ItemIsEditable

    def delete_rows(self, rows):
        patch_data = []
        delete_data = []
        for entry in [row.model().data_items[row.row()] for row in rows]:
            if entry["status"] == NEW:
                delete_data.append({"public_key": entry['public_key'], "id": entry['id']})
            else:
                patch_data.append(
                    {"public_key": entry['public_key'], "id": entry['id'], "status": COMMIT_STATUS_TODELETE}
                )

        # We don't wait for the Core to report back and emit
        # the info_changed signal speculativley to prevent the race condition between
        # Python object deletion and PyQT one. Otherwise, if the users e.g. clicks the back
        # button, by the moment the request callback triggers some actions on the model,
        # QT could have already deleted the underlying model object, which will result in
        # "wrapped C/C++ object has been deleted" error (see e.g. https://github.com/Tribler/tribler/issues/6083)
        for data, method in ((patch_data, "PATCH"), (delete_data, "DELETE")):
            if data:
                self.remove_items(data)
                TriblerNetworkRequest("metadata", lambda _: None, raw_data=json.dumps(data), method=method)

    def create_new_channel(self, channel_name=None):
        url = (
            self.endpoint_url_override or "channels/%s/%i" % (self.channel_info["public_key"], self.channel_info["id"])
        ) + ("/channels" if self.channel_info.get("id", 0) == 0 else "/collections")
        TriblerNetworkRequest(
            url,
            self.on_create_query_results,
            method='POST',
            raw_data=json.dumps({"name": channel_name}) if channel_name else None,
        )

    def on_create_query_results(self, response, **kwargs):
        # This is a hack to put the newly created object at the top of the table
        kwargs["on_top"] = 1
        self.on_query_results(response, **kwargs)
        if not response or self.qt_object_destroyed:
            return False
        self.info_changed.emit(response['results'])

    @property
    def edit_enabled(self):
        return self.channel_info.get("state", None) == "Personal"


class SimplifiedPersonalChannelsModel(PersonalChannelsModel):
    columns_shown = (Column.ACTIONS, Column.CATEGORY, Column.NAME, Column.SIZE, Column.HEALTH, Column.UPDATED)

    def __init__(self, *args, **kwargs):
        kwargs["exclude_deleted"] = kwargs.get("exclude_deleted", True)
        super().__init__(*args, **kwargs)
