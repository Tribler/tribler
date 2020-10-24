import json
import uuid

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, CHANNEL_STATE

from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from tribler_gui.defs import ACTION_BUTTONS, BITTORRENT_BIRTHDAY, COMMIT_STATUS_TODELETE, HEALTH_CHECKING
from tribler_gui.i18n import tr
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import format_size, format_votes, get_votes_rating_description, pretty_date


def get_item_uid(item):
    if 'public_key' in item and 'id' in item:
        return f"{item['public_key']}:{item['id']}"
    return item['infohash']


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
        # Unique identifier mapping for items. For torrents, it is infohash and for channels, it is concatenated value
        # of public key and channel id
        self.item_uid_map = {}

        self.data_items = []
        self.item_load_batch = 50
        self.sort_by = self.columns[self.default_sort_column] if self.default_sort_column >= 0 else None
        self.sort_desc = True
        self.saved_header_state = None
        self.saved_scroll_state = None

        # Every remote query must be attributed to its specific model to avoid updating wrong models
        # on receiving a result. We achieve this by maintaining a set of in-flight remote queries.
        # Note that this only applies to results that are returned through the events notification
        # mechanism, because REST requests attribution is maintained by the RequestManager.
        # We do not clean it up after receiving a result because we don't know if the result was the
        # last one. In a sense, the queries' UUIDs play the role of "subscription topics" for the model.
        self.remote_queries = set()

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

    def add_items(self, new_items, on_top=False):
        """
        Adds new items to the table model. All items are mapped to their unique ids to avoid the duplicates.
        If the new items are remote then the items are prepended to the top else appended to the end of the model.
        Note that item_uid_map tracks items twice: once by public_key+id and once by infohash. This is necessary to
        support status updates from TorrentChecker based on infohash only.
        :param new_items: list(item)
        :param on_top: True if new_items should be added on top of the table
        :return: None
        """
        if not new_items:
            return

        # Note: If we want to block the signal like itemChanged, we must use QSignalBlocker object or blockSignals

        # Only add unique items to the table model and reverse mapping from unique ids to rows is built.
        # If items are remote, prepend to the top else append to the end of the model.
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
        if 'first' not in kwargs or 'last' not in kwargs:
            kwargs["first"], kwargs['last'] = self.rowCount() + 1, self.rowCount() + self.item_load_batch

        if self.sort_by is not None:
            kwargs.update({"sort_by": self.sort_by, "sort_desc": self.sort_desc})

        if self.text_filter:
            kwargs.update({"txt_filter": self.text_filter})

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
        # TODO: count remote results
        if not response:
            return False

        # Trigger labels update on the initial table load
        update_labels = len(self.data_items) == 0

        if not remote or (uuid.UUID(response.get('uuid')) in self.remote_queries):
            self.add_items(response['results'], on_top=remote or on_top)
            if "total" in response:
                self.channel_info["total"] = response["total"]
                update_labels = True
            elif remote and uuid.UUID(response.get('uuid')) == CHANNELS_VIEW_UUID:
                # This is a discovered channel (from a remote peer), update the total number of channels and the labels
                if self.channel_info.get("total"):
                    self.channel_info["total"] += len(response["results"])
                update_labels = True
            if update_labels:
                self.info_changed.emit(response['results'])
        return True


class ChannelContentModel(RemoteTableModel):

    columns = [ACTION_BUTTONS, u'category', u'name', u'size', u'health', u'updated']
    column_headers = ['', '', tr('Name'), tr('Size'), tr('Health'), tr('Updated')]
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

    column_width = {
        u'state': lambda _: 100,
        u'subscribed': lambda _: 100,
        u'name': lambda table_width: table_width - 450,
        u'action_buttons': lambda _: 50,
        u'category': lambda _: 30,
    }

    column_tooltip_filters = {
        u'state': lambda data: data,
        u'votes': lambda data: get_votes_rating_description(data) if data is not None else None,
        u'category': lambda data: data,
        u'health': lambda data: f"{data}" + ('' if data == HEALTH_CHECKING else '\n(Click to recheck)'),
    }

    column_display_filters = {
        u'size': lambda data: (format_size(float(data)) if data != '' else ''),
        u'votes': format_votes,
        u'updated': lambda timestamp: pretty_date(timestamp)
        if timestamp and timestamp > BITTORRENT_BIRTHDAY
        else 'N/A',
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
            return self.column_headers[num]
        if role == Qt.InitialSortOrderRole and num != self.column_position.get('name'):
            return Qt.DescendingOrder
        elif role == Qt.TextAlignmentRole:
            return (
                Qt.AlignHCenter
                if num in [self.column_position.get('subscribed'), self.column_position.get('torrents')]
                else Qt.AlignLeft
            )

    def rowCount(self, parent=QModelIndex()):
        return len(self.data_items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def flags(self, index):
        return self.column_flags[self.columns[index.column()]]

    def filter_item_txt(self, txt_filter, index, show_default=True):
        # FIXME: dumb workaround for some mysterious race condition
        try:
            item = self.data_items[index.row()]
        except IndexError:
            return ""

        column = self.columns[index.column()]
        data = item.get(column, u'')

        # Print number of torrents in the channel for channel rows in the "size" column
        if (
            column == "size"
            and "torrents" not in self.columns
            and "torrents" in item
            and item["type"] in (CHANNEL_TORRENT, COLLECTION_NODE)
        ):
            return item["torrents"]

        # 'subscribed' column gets special treatment in case of ToolTipRole, because
        # its tooltip uses information from both 'subscribed' and 'state' keys
        # TODO: refactor data, roles and filters to be less hacky and more readable
        if (
            column == 'subscribed'
            and txt_filter == self.column_tooltip_filters
            and 'subscribed' in item
            and 'state' in item
        ):
            state_message = f" ({item['state']})" if item['state'] != CHANNEL_STATE.COMPLETE.value else ""
            tooltip_txt = (
                f"Subscribed.{state_message}\n(Click to unsubscribe)"
                if item['subscribed']
                else "Not subscribed.\n(Click to subscribe)"
            )
            return tooltip_txt

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
            if index.column() == self.column_position.get(u'torrents', -1):
                return Qt.AlignHCenter | Qt.AlignVCenter
        return None

    def reset(self):
        self.item_uid_map.clear()
        super(ChannelContentModel, self).reset()

    def update_node_info(self, update_dict):
        """
        This method updates/inserts rows based on updated_dict. It should be typically invoked
        by a signal from Events endpoint. One special case it when the channel_info of the model
        itself is updated. In that case, info_changed signal is emitted, so the controller/widget knows
        it is time to update the labels.
        """
        # TODO: better mechanism for identifying channel entries for pushing updates

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

    def setData(self, index, new_value, role=None):
        if role != Qt.EditRole:
            return True
        item = self.data_items[index.row()]
        attribute_name = self.columns[index.column()]
        attribute_name = u'tags' if attribute_name == u'category' else attribute_name
        attribute_name = u'title' if attribute_name == u'name' else attribute_name
        attribute_name = u'subscribed' if attribute_name == u'votes' else attribute_name

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

        # TODO: reload the whole row from DB instead of just changing the displayed value
        self.data_items[index.row()][self.columns[index.column()]] = new_value
        return True

    def on_new_entry_received(self, response):
        self.on_query_results(response, remote=True)


class SearchResultsModel(ChannelContentModel):
    pass


class DiscoveredChannelsModel(ChannelContentModel):
    columns = [u'subscribed', u'name', u'state', u'torrents', u'votes', u'updated']
    column_headers = [tr('Subscribed'), tr('Name'), u'', tr('Torrents'), tr('Popularity'), tr('Updated')]

    column_width = dict(ChannelContentModel.column_width, **{u'name': lambda table_width: table_width - 540})
    default_sort_column = columns.index(u'votes')

    def __init__(self, *args, **kwargs):
        super(DiscoveredChannelsModel, self).__init__(*args, **kwargs)
        # Subscribe to new channels updates notified over the Events endpoint
        self.remote_queries.add(CHANNELS_VIEW_UUID)


class PersonalChannelsModel(ChannelContentModel):
    columns = [ACTION_BUTTONS, u'category', u'name', u'size', u'health', u'updated', u'status']
    column_headers = ['', '', tr('Name'), tr('Size'), tr('Health'), tr('Updated'), u'']

    column_flags = dict(ChannelContentModel.column_flags)
    column_flags.update(
        {
            u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
            u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
        }
    )

    def __init__(self, *args, **kwargs):
        kwargs["hide_xxx"] = kwargs.get("hide_xxx", False)
        super(PersonalChannelsModel, self).__init__(*args, **kwargs)

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
            self.remove_items(json_result)
            self.info_changed.emit(json_result)

        if patch_data:
            TriblerNetworkRequest("metadata", on_torrents_deleted, raw_data=json.dumps(patch_data), method='PATCH')
        if delete_data:
            TriblerNetworkRequest("metadata", on_torrents_deleted, raw_data=json.dumps(delete_data), method='DELETE')

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

    def on_query_results(self, response, **kwargs):
        if super(PersonalChannelsModel, self).on_query_results(response, **kwargs):
            if response.get("results"):
                self.info_changed.emit(response["results"])

    def on_create_query_results(self, response, **kwargs):
        # This is a hack to put the newly created object at the top of the table
        kwargs["on_top"] = 1
        self.on_query_results(response, **kwargs)

    @property
    def edit_enabled(self):
        return self.channel_info.get("state", None) == "Personal"


class SimplifiedPersonalChannelsModel(PersonalChannelsModel):
    columns = [ACTION_BUTTONS, u'category', u'name', u'size', u'health', u'updated']
    column_headers = ['', '', tr('Name'), tr('Size'), tr('Health'), tr('Updated')]

    column_width = dict(ChannelContentModel.column_width, **{u'name': lambda table_width: table_width - 440})

    def __init__(self, *args, **kwargs):
        kwargs["exclude_deleted"] = kwargs.get("exclude_deleted", True)
        super(SimplifiedPersonalChannelsModel, self).__init__(*args, **kwargs)
