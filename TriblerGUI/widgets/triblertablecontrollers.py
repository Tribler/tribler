"""
This file contains various controllers for table views.
The responsibility of the controller is to populate the table view with some data, contained in a specific model.
"""
from __future__ import absolute_import

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAction

from Tribler.Core.Modules.MetadataStore.serialization import REGULAR_TORRENT

from TriblerGUI.tribler_action_menu import TriblerActionMenu


class TriblerTableViewController(QObject):
    """
    Base controller for a table view that displays some data.
    """

    def __init__(self, table_view):
        super(TriblerTableViewController, self).__init__()
        self.model = None
        self.table_view = table_view
        self.table_view.verticalScrollBar().valueChanged.connect(self._on_list_scroll)
        self.request_mgr = None

    def set_model(self, model):
        self.model = model
        self.table_view.horizontalHeader().setSortIndicator(
            model.column_position.get(model.sort_by, None) or model.default_sort_column,
            Qt.DescendingOrder if model.sort_desc else Qt.AscendingOrder,
        )
        self.table_view.setModel(self.model)

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
        self.model.text_filter = self.filter_input.text().lower()
        self.model.reset()


class TableSelectionMixin(object):
    def brain_dead_refresh(self):
        """
        FIXME! Brain-dead way to show the rows covered by a newly-opened details_container
        Note that none of the more civilized ways to fix it work:
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
        if 'type' in torrent_info and torrent_info['type'] != REGULAR_TORRENT:
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
            self.details_container.details_tab_widget.update_health_label(
                update_dict["num_seeders"], update_dict["num_leechers"], update_dict["last_tracker_check"]
            )
            self.model.update_node_info(update_dict)


class ContextMenuMixin(object):
    table_view = None
    model = None

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
        if num_selected == 1:
            self.add_menu_item(menu, ' Download ', item_index, self.table_view.on_download_button_clicked)
            self.add_menu_item(menu, ' Play ', item_index, self.table_view.on_play_button_clicked)

        # Add menu separator for channel stuff
        menu.addSeparator()

        entries = [self.model.data_items[index.row()] for index in self.table_view.selectionModel().selectedRows()]

        def on_add_to_channel(_):
            self.table_view.window().add_to_channel_dialog.copy_entries(entries)

        def on_move(_):
            self.table_view.window().add_to_channel_dialog.move_entries(entries)

        if not self.model.edit_enabled:
            if self.selection_has_torrents():
                self.add_menu_item(menu, ' Add to My Channel ', item_index, on_add_to_channel)
        else:
            self.add_menu_item(menu, ' Move ', item_index, on_move)
            self.add_menu_item(menu, ' Rename ', item_index, self._trigger_name_editor)
            self.add_menu_item(menu, ' Change category ', item_index, self._trigger_category_editor)
            menu.addSeparator()
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


class ContentTableViewController(
    TableSelectionMixin, ContextMenuMixin, TriblerTableViewController, TorrentHealthDetailsMixin
):
    def __init__(self, table_view, details_container, filter_input=None):
        TriblerTableViewController.__init__(self, table_view)
        self.details_container = details_container
        self.filter_input = filter_input
        if self.filter_input:
            self.filter_input.textChanged.connect(self._on_filter_input_change)

        # self.model.row_edited.connect(self._on_row_edited)
        self.enable_context_menu(self.table_view)

    def set_model(self, model):
        super(ContentTableViewController, self).set_model(model)
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def unset_model(self):
        if self.table_view.model:
            self.table_view.selectionModel().selectionChanged.disconnect()
        self.model = None
