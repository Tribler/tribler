"""
This file contains various controllers for table views.
The responsibility of the controller is to populate the table view with some data, contained in a specific model.
"""
import time

from PyQt5.QtCore import QObject, QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QAction

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.utilities.json_util import dumps

from tribler_gui.defs import HEALTH_CHECKING, HEALTH_UNCHECKED
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import get_health

HEALTHCHECK_DELAY_MS = 500


def sanitize_for_fts(text):
    return text.translate({ord(u"\""): u"\"\"", ord(u"\'"): u"\'\'"})


def to_fts_query(text):
    if not text:
        return ""
    words = text.strip().split(" ")
    # TODO: add support for quoted exact searches
    query_list = [u'\"' + sanitize_for_fts(word) + u'\"*' for word in words]
    return " AND ".join(query_list)


class TriblerTableViewController(QObject):
    """
    Base controller for a table view that displays some data.
    """

    def __init__(self, table_view, **kwargs):
        super().__init__()

        self.model = None
        self.table_view = table_view
        self.table_view.verticalScrollBar().valueChanged.connect(self._on_list_scroll)

        # FIXME: The M-V-C stuff is a complete mess. It should be refactored in a more structured way.
        self.table_view.delegate.subscribe_control.clicked.connect(self.table_view.on_subscribe_control_clicked)
        self.table_view.delegate.download_button.clicked.connect(self.table_view.start_download_from_index)
        self.table_view.delegate.health_status_widget.clicked.connect(
            lambda index: self.check_torrent_health(index.model().data_items[index.row()], forced=True)
        )
        self.table_view.torrent_clicked.connect(self.check_torrent_health)
        self.table_view.torrent_doubleclicked.connect(self.table_view.start_download_from_dataitem)

    def set_model(self, model):
        self.model = model
        self.table_view.setModel(self.model)
        if self.model.saved_header_state:
            self.table_view.horizontalHeader().restoreState(self.model.saved_header_state)
        if self.model.saved_scroll_state is not None:
            # ACHTUNG! Repeating this line is necessary due to a bug(?) in QT. Otherwise, it has no effect.
            self.table_view.scrollTo(self.model.index(self.model.saved_scroll_state, 0), 1)
            self.table_view.scrollTo(self.model.index(self.model.saved_scroll_state, 0), 1)

    def _on_list_scroll(self, event):
        if (
            self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum()
            and self.model.data_items
        ):  # workaround for duplicate calls to _on_list_scroll on view creation
            self.model.perform_query()

    def _get_sort_parameters(self):
        """
        Return a tuple (column_name, sort_desc) that indicates the sorting column/order of the table view.
        """
        sort_column_number = self.table_view.horizontalHeader().sortIndicatorSection()
        # If the column number is set to -1, this means we do not want to do sorting at all
        # We have to set it to something (-1), because QT does not support setting it to "None"
        sort_by = self.model.columns[sort_column_number] if sort_column_number >= 0 else None
        sort_asc = self.table_view.horizontalHeader().sortIndicatorOrder()
        return sort_by, sort_asc

    def _on_filter_input_change(self, _):
        self.model.text_filter = to_fts_query(self.filter_input.text().lower())
        self.model.reset()


class TableSelectionMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.healthcheck_cooldown = QTimer()
        self.healthcheck_cooldown.setSingleShot(True)

        # When the user stops scrolling and selection settles on a row,
        # trigger the health check.
        self.healthcheck_cooldown.timeout.connect(lambda: self._on_selection_changed(None))

    def set_model(self, model):
        super(TableSelectionMixin, self).set_model(model)
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def unset_model(self):
        if self.table_view.model:
            self.table_view.selectionModel().selectionChanged.disconnect()
        super(TableSelectionMixin, self).unset_model()

    def _on_selection_changed(self, _):
        selected_indices = self.table_view.selectedIndexes()
        if not selected_indices:
            self.table_view.clearSelection()
            return

        data_item = selected_indices[-1].model().data_items[selected_indices[-1].row()]
        if 'type' in data_item and data_item['type'] != REGULAR_TORRENT:
            return

        # Trigger health check if necessary
        # When the user scrolls the list, we only want to trigger health checks on the line
        # that the user stopped on, so we do not generate excessive health checks.
        if data_item['last_tracker_check'] == 0 and data_item.get(u'health') != HEALTH_CHECKING:
            if self.healthcheck_cooldown.isActive():
                self.healthcheck_cooldown.stop()
            else:
                self.check_torrent_health(data_item)
            self.healthcheck_cooldown.start(HEALTHCHECK_DELAY_MS)


class HealthCheckerMixin:
    def check_torrent_health(self, data_item, forced=False):
        # TODO: stop triggering multiple checks over a single infohash by e.g. selection and click signals
        infohash = data_item[u'infohash']

        if u'health' not in self.model.column_position:
            return
        # Check if the entry still exists in the table
        row = self.model.item_uid_map.get(infohash)
        if row is None:
            return
        data_item = self.model.data_items[row]
        if not forced and data_item[u'health'] != HEALTH_UNCHECKED:
            return
        data_item[u'health'] = HEALTH_CHECKING
        health_cell_index = self.model.index(row, self.model.column_position[u'health'])
        self.model.dataChanged.emit(health_cell_index, health_cell_index, [])

        TriblerNetworkRequest(
            "metadata/torrents/%s/health" % infohash,
            self.on_health_response,
            url_params={"nowait": True, "refresh": True},
            capture_core_errors=False,
            priority=QNetworkRequest.LowPriority,
        )

    def on_health_response(self, response):
        total_seeders = 0
        total_leechers = 0

        if not response or 'error' in response or 'checking' in response:
            return

        infohash = response['infohash']
        for _, status in response['health'].items():
            if 'error' in status:
                continue  # Timeout or invalid status
            total_seeders += int(status['seeders'])
            total_leechers += int(status['leechers'])

        self.update_torrent_health(infohash, total_seeders, total_leechers)

    def update_torrent_health(self, infohash, seeders, leechers):
        # Check if details widget is still showing the same entry and the entry still exists in the table
        row = self.model.item_uid_map.get(infohash)
        if row is None:
            return

        data_item = self.model.data_items[row]
        data_item[u'num_seeders'] = seeders
        data_item[u'num_leechers'] = leechers
        data_item[u'last_tracker_check'] = time.time()
        data_item[u'health'] = get_health(
            data_item[u'num_seeders'], data_item[u'num_leechers'], data_item[u'last_tracker_check']
        )

        if u'health' in self.model.column_position:
            index = self.model.index(row, self.model.column_position[u'health'])
            self.model.dataChanged.emit(index, index, [])


class ContextMenuMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_context_menu(self.table_view)

    def enable_context_menu(self, widget):
        self.table_view = widget
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

    def _trigger_name_editor(self, index):
        model = index.model()
        title_index = model.index(index.row(), model.columns.index(u'name'))
        self.table_view.edit(title_index)

    def _trigger_category_editor(self, index):
        model = index.model()
        title_index = model.index(index.row(), model.columns.index(u'category'))
        self.table_view.edit(title_index)

    def _show_context_menu(self, pos):
        if not self.table_view or not self.model:
            return

        item_index = self.table_view.indexAt(pos)
        if not item_index or item_index.row() < 0:
            return

        menu = TriblerActionMenu(self.table_view)

        # Single selection menu items
        num_selected = len(self.table_view.selectionModel().selectedRows())
        if num_selected == 1 and item_index.model().data_items[item_index.row()]["type"] == REGULAR_TORRENT:
            self.add_menu_item(menu, ' Download ', item_index, self.table_view.start_download_from_index)
            self.add_menu_item(
                menu,
                ' Recheck health',
                item_index.model().data_items[item_index.row()],
                lambda x: self.check_torrent_health(x, forced=True),
            )
        if num_selected == 1 and item_index.model().column_position.get('subscribed') is not None:
            data_item = item_index.model().data_items[item_index.row()]
            if data_item["type"] == CHANNEL_TORRENT and data_item["state"] != CHANNEL_STATE.PERSONAL.value:
                self.add_menu_item(
                    menu,
                    f' {"Unsubscribe" if data_item["subscribed"] else "Subscribe"} channel',
                    item_index.model().index(item_index.row(), item_index.model().column_position['subscribed']),
                    self.table_view.delegate.subscribe_control.clicked.emit,
                )

        # Add menu separator for channel stuff
        menu.addSeparator()

        entries = [self.model.data_items[index.row()] for index in self.table_view.selectionModel().selectedRows()]

        def on_add_to_channel(_):
            def on_confirm_clicked(channel_id):
                TriblerNetworkRequest(
                    f"collections/mychannel/{channel_id}/copy",
                    lambda _: self.table_view.window().tray_show_message(
                        "Channel update", "Torrent(s) added to your channel"
                    ),
                    raw_data=dumps(entries),
                    method='POST',
                )

            self.table_view.window().add_to_channel_dialog.show_dialog(on_confirm_clicked, confirm_button_text="Copy")

        def on_move(_):
            def on_confirm_clicked(channel_id):
                changes_list = [
                    {'public_key': entry['public_key'], 'id': entry['id'], 'origin_id': channel_id} for entry in entries
                ]
                TriblerNetworkRequest("metadata", self.model.remove_items, raw_data=dumps(changes_list), method='PATCH')

            self.table_view.window().add_to_channel_dialog.show_dialog(on_confirm_clicked, confirm_button_text="Move")

        if not self.model.edit_enabled:
            if self.selection_can_be_added_to_channel():
                self.add_menu_item(menu, ' Copy into personal channel', item_index, on_add_to_channel)
        else:
            self.add_menu_item(menu, ' Move ', item_index, on_move)
            self.add_menu_item(menu, ' Rename ', item_index, self._trigger_name_editor)
            self.add_menu_item(menu, ' Change category ', item_index, self._trigger_category_editor)
            menu.addSeparator()
            self.add_menu_item(menu, ' Remove from channel', item_index, self.table_view.on_delete_button_clicked)

        menu.exec_(QCursor.pos())

    def add_menu_item(self, menu, name, item_index, callback):
        action = QAction(name, self.table_view)
        action.triggered.connect(lambda _: callback(item_index))
        menu.addAction(action)

    def selection_can_be_added_to_channel(self):
        for row in self.table_view.selectionModel().selectedRows():
            data_item = row.model().data_items[row.row()]
            if 'type' in data_item and data_item['type'] in (REGULAR_TORRENT, CHANNEL_TORRENT, COLLECTION_NODE):
                return True
        return False


class ContentTableViewController(TableSelectionMixin, ContextMenuMixin, HealthCheckerMixin, TriblerTableViewController):
    def __init__(self, *args, filter_input=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.filter_input = filter_input
        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)

    def unset_model(self):
        self.model = None
