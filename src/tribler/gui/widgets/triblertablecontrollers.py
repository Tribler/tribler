"""
This file contains various controllers for table views.
The responsibility of the controller is to populate the table view with some data, contained in a specific model.
"""
import logging

from PyQt5.QtCore import QObject, QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QAction

from tribler.core.components.database.db.serialization import REGULAR_TORRENT
from tribler.gui.defs import HEALTH_CHECKING, HEALTH_UNCHECKED
from tribler.gui.network.request_manager import request_manager
from tribler.gui.tribler_action_menu import TriblerActionMenu
from tribler.gui.utilities import connect, dict_item_is_any_of, tr
from tribler.gui.widgets.tablecontentmodel import Column

HEALTHCHECK_DELAY_MS = 500


class TriblerTableViewController(QObject):
    """
    Base controller for a table view that displays some data.
    """

    def __init__(self, table_view, *args, filter_input=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = None
        self.table_view = table_view
        connect(self.table_view.verticalScrollBar().valueChanged, self._on_list_scroll)

        connect(self.table_view.delegate.download_button.clicked, self.table_view.start_download_from_index)
        connect(self.table_view.torrent_doubleclicked, self.table_view.start_download_from_dataitem)

        self.filter_input = filter_input
        if self.filter_input:
            connect(self.filter_input.returnPressed, self.on_filter_input_return_pressed)

    def set_model(self, model):
        self.model = model
        self.table_view.setModel(self.model)
        if self.model.saved_header_state:
            self.table_view.horizontalHeader().restoreState(self.model.saved_header_state)
        if self.model.saved_scroll_state is not None:
            # ACHTUNG! Repeating this line is necessary due to a bug(?) in QT. Otherwise, it has no effect.
            self.table_view.scrollTo(self.model.index(self.model.saved_scroll_state, 0), 1)
            self.table_view.scrollTo(self.model.index(self.model.saved_scroll_state, 0), 1)

    def _on_list_scroll(self, event):  # pylint: disable=W0613
        if (
                self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum()
                and self.model.data_items
                and not self.model.all_local_entries_loaded
        ):  # workaround for duplicate calls to _on_list_scroll on view creation
            self.model.perform_query()

    def _get_sort_parameters(self):
        """
        Return a tuple (column_name, sort_desc) that indicates the sorting column/order of the table view.
        """
        sort_column_number = self.table_view.horizontalHeader().sortIndicatorSection()
        # If the column number is set to -1, this means we do not want to do sorting at all
        # We have to set it to something (-1), because QT does not support setting it to "None"
        sort_by = self.model.columns[sort_column_number].dict_key if sort_column_number >= 0 else None
        sort_asc = self.table_view.horizontalHeader().sortIndicatorOrder()
        return sort_by, sort_asc

    def on_filter_input_return_pressed(self):
        self.model.text_filter = self.filter_input.text().lower()
        self.model.reset()

    def brain_dead_refresh(self):
        """
        ACHTUNG! Brain-dead refresh is back!
        It shows the rows eaten by a closed channel description widget.
        Note that none of the more civilized ways to fix it work:
        various updateGeometry, viewport().update, adjustSize - nothing works!
        """
        window = self.table_view.window()
        window.resize(window.geometry().width() + 1, window.geometry().height())
        window.resize(window.geometry().width() - 1, window.geometry().height())

    def unset_model(self):
        self.model = None


class TableLoadingAnimationMixin:
    def set_model(self, model):
        if not model.loaded:
            self.table_view.show_loading_animation_delayed()
        connect(model.query_complete, self.table_view.hide_loading_animation)
        connect(model.query_started, self.table_view.show_loading_animation_delayed)
        super().set_model(model)

    def unset_model(self):
        if self.table_view.model:
            self.model.query_complete.disconnect()
            self.model.query_started.disconnect()

        self.table_view.hide_loading_animation()
        super().unset_model()


class TableSelectionMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.healthcheck_cooldown = QTimer()
        self.healthcheck_cooldown.setSingleShot(True)

        # When the user stops scrolling and selection settles on a row,
        # trigger the health check.
        connect(self.healthcheck_cooldown.timeout, lambda: self._on_selection_changed(None, None))

    def set_model(self, model):
        super().set_model(model)
        connect(self.table_view.selectionModel().selectionChanged, self._on_selection_changed)

    def unset_model(self):
        if self.table_view.model:
            self.table_view.selectionModel().selectionChanged.disconnect()
        super().unset_model()

    def _on_selection_changed(self, selected, deselected):  # pylint: disable=W0613
        selected_indices = self.table_view.selectedIndexes()
        if not selected_indices:
            self.table_view.clearSelection()
            return

        data_item = selected_indices[-1].model().data_items[selected_indices[-1].row()]
        if not dict_item_is_any_of(data_item, 'type', [REGULAR_TORRENT]):
            return

        if issubclass(type(self), HealthCheckerMixin):
            # Trigger health check if necessary
            # When the user scrolls the list, we only want to trigger health checks on the line
            # that the user stopped on, so we do not generate excessive health checks.
            if data_item['last_tracker_check'] == 0 and data_item.get('health') != HEALTH_CHECKING:
                if self.healthcheck_cooldown.isActive():
                    self.healthcheck_cooldown.stop()
                else:
                    self.check_torrent_health(data_item)
                self.healthcheck_cooldown.start(HEALTHCHECK_DELAY_MS)


class HealthCheckerMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_checker_logger = logging.getLogger('HealthCheckerMixin')

        connect(
            self.table_view.delegate.health_status_widget.clicked,
            lambda index: self.check_torrent_health(index.model().data_items[index.row()], forced=True),
        )
        connect(self.table_view.torrent_clicked, self.check_torrent_health)

    def check_torrent_health(self, data_item, forced=False):
        if not dict_item_is_any_of(data_item, 'type', [REGULAR_TORRENT]):
            return
        if Column.HEALTH not in self.model.column_position:
            return
        # Check if the entry still exists in the table
        infohash = data_item['infohash']
        row = self.model.item_uid_map.get(infohash)
        if row is None:
            return

        if not forced and data_item.get('health', HEALTH_UNCHECKED) != HEALTH_UNCHECKED:
            return
        data_item['health'] = HEALTH_CHECKING
        health_cell_index = self.model.index(row, self.model.column_position[Column.HEALTH])
        self.model.dataChanged.emit(health_cell_index, health_cell_index, [])
        request_manager.get(
            f"metadata/torrents/{infohash}/health",
            capture_errors=False,
            priority=QNetworkRequest.LowPriority
        )


class ContextMenuMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_context_menu(self.table_view)

    def enable_context_menu(self, widget):
        self.table_view = widget
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        connect(self.table_view.customContextMenuRequested, self._show_context_menu)

    def _trigger_name_editor(self, index):
        model = index.model()
        title_index = model.index(index.row(), model.columns_shown.index(Column.NAME))
        self.table_view.edit(title_index)

    def _trigger_category_editor(self, index):
        model = index.model()
        title_index = model.index(index.row(), model.columns_shown.index(Column.CATEGORY))
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
            self.add_menu_item(menu, tr(" Download "), item_index, self.table_view.start_download_from_index)
            if issubclass(type(self), HealthCheckerMixin):
                self.add_menu_item(
                    menu,
                    tr(" Recheck health"),
                    item_index.model().data_items[item_index.row()],
                    lambda x: self.check_torrent_health(x, forced=True),
                )

        menu.exec_(QCursor.pos())

    def add_menu_item(self, menu, name, item_index, callback):
        action = QAction(name, self.table_view)
        connect(action.triggered, lambda _: callback(item_index))
        menu.addAction(action)


class PopularContentTableViewController(
    TableSelectionMixin, ContextMenuMixin, TableLoadingAnimationMixin, TriblerTableViewController
):
    pass


class ContentTableViewController(
    TableSelectionMixin, ContextMenuMixin, HealthCheckerMixin, TableLoadingAnimationMixin, TriblerTableViewController
):
    pass
