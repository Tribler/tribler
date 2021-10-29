import json
from typing import List

from PyQt5.QtCore import QEvent, QModelIndex, QRect, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QMouseEvent, QMovie
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QLabel, QTableView

from tribler_core.components.metadata_store.db.orm_bindings.channel_node import LEGACY_ENTRY
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import COMMIT_STATUS_COMMITTED
from tribler_gui.dialogs.addtagsdialog import AddTagsDialog
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, data_item2uri, get_image_path, index2uri
from tribler_gui.widgets.tablecontentdelegate import TriblerContentDelegate
from tribler_gui.widgets.tablecontentmodel import Column, EXPANDING


class FloatingAnimationWidget(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(0, 0, 100, 100)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.qm = QMovie(get_image_path("spinner.gif"))
        self.setMovie(self.qm)

    def update_position(self):
        if hasattr(self.parent(), 'viewport'):
            parent_rect = self.parent().viewport().rect()
        else:
            parent_rect = self.parent().rect()

        if not parent_rect:
            return

        x = parent_rect.width() / 2 - self.width() / 2
        y = parent_rect.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_position()


class TriblerContentTableView(QTableView):
    """
    This table view is designed to support lazy loading.
    When the user reached the end of the table, it will ask the model for more items, and load them dynamically.
    """
    channel_clicked = pyqtSignal(dict)
    torrent_clicked = pyqtSignal(dict)
    torrent_doubleclicked = pyqtSignal(dict)
    edited_tags = pyqtSignal(dict)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.add_tags_dialog = None
        self.setMouseTracking(True)

        self.delegate = TriblerContentDelegate(self)
        self.delegate.font_metrics = self.fontMetrics()  # Required to estimate the height of a row.

        self.setItemDelegate(self.delegate)
        connect(self.delegate.redraw_required, self.redraw)

        # Install an event filter on the horizontal header to catch mouse movements (so we can deselect rows).
        self.horizontalHeader().installEventFilter(self)

        # Stop triggering editor events on doubleclick, because we already use doubleclick to start downloads.
        # Editing should be started manually, from drop-down menu instead.
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Mix-in connects
        connect(self.clicked, self.on_table_item_clicked)
        connect(self.doubleClicked, lambda item: self.on_table_item_clicked(item, doubleclick=True))

        self.loading_animation_widget = FloatingAnimationWidget(self)

        # We add a small delay to show the loading animation to avoid flickering on fast-loaded data
        self.loading_animation_delay_timer = QTimer()
        self.loading_animation_delay_timer.setSingleShot(True)
        self.loading_animation_delay = 100  # Milliseconds
        connect(self.loading_animation_delay_timer.timeout, self.show_loading_animation)

        self.hide_loading_animation()

        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setFixedHeight(40)

    def show_loading_animation_delayed(self):
        self.loading_animation_delay_timer.start(self.loading_animation_delay)

    def show_loading_animation(self):
        self.loading_animation_widget.qm.start()
        self.loading_animation_widget.setHidden(False)

    def hide_loading_animation(self):
        self.loading_animation_delay_timer.stop()
        self.loading_animation_widget.qm.stop()
        self.loading_animation_widget.setHidden(True)

    def eventFilter(self, obj, event):
        if obj == self.horizontalHeader() and event.type() == QEvent.HoverEnter:
            # Deselect rows when the mouse leaves through the table view header.
            self.deselect_all_rows()
        return False

    def wheelEvent(self, event):
        super().wheelEvent(event)

        # We trigger a mouse movement event to make sure that the whole row remains selected when scrolling.
        index = QModelIndex(self.indexAt(event.pos()))
        self.delegate.on_mouse_moved(event.pos(), index)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        should_select_row = True
        index = self.indexAt(event.pos())
        if index != self.delegate.no_index:
            # Check if we are clicking the 'edit tags' button
            if index in index.model().edit_tags_rects:
                rect = index.model().edit_tags_rects[index]
                if rect.contains(event.pos()) and event.button() != Qt.RightButton:
                    should_select_row = False
                    self.on_edit_tags_clicked(index)

        if should_select_row:
            super().mousePressEvent(event)

    def deselect_all_rows(self):
        """
        Deselect all rows in the table view.
        """
        old_selected = self.delegate.hover_index
        self.delegate.hover_index = self.delegate.no_index
        self.redraw(old_selected, True)

    def leaveEvent(self, event):
        """
        The mouse has left the viewport. Make sure that we deselect the currently selected row and redraw.
        Note that this might fail when moving the mouse very fast.
        """
        super().leaveEvent(event)
        self.deselect_all_rows()
        QApplication.restoreOverrideCursor()
        self.delegate.on_mouse_left()

    def mouseMoveEvent(self, event):
        index = QModelIndex(self.indexAt(event.pos()))
        QApplication.restoreOverrideCursor()
        self.delegate.on_mouse_moved(event.pos(), index)

    def redraw(self, index, redraw_whole_row):
        """
        Redraw the cell at a particular index.
        """
        if redraw_whole_row:
            for col_ind in range(self.model().columnCount()):
                index = self.model().index(index.row(), col_ind)
                self.model().dataChanged.emit(index, index, [])
        else:
            self.model().dataChanged.emit(index, index, [])

        # This is required to drop the sensitivity zones of the controls,
        # so there are no invisible controls left over from a previous state of the view
        for control in self.delegate.controls:
            control.rect = QRect()

    def on_subscribe_control_clicked(self, index):
        item = index.model().data_items[index.row()]
        # skip LEGACY entries, regular torrents and personal channel
        if 'subscribed' not in item or item['status'] == LEGACY_ENTRY or item['state'] == 'Personal':
            return

        status = int(item['subscribed'])

        if status:
            self.window().on_channel_unsubscribe(item)
        else:
            self.window().on_channel_subscribe(item)

    def on_edit_tags_clicked(self, index: QModelIndex) -> None:
        data_item = index.model().data_items[index.row()]
        self.add_tags_dialog = AddTagsDialog(self.window(), data_item["infohash"])
        self.add_tags_dialog.index = index
        if data_item.get("tags", ()):
            self.add_tags_dialog.dialog_widget.edit_tags_input.set_tags(data_item.get("tags", ()))
        self.add_tags_dialog.dialog_widget.content_name_label.setText(data_item["name"])
        self.add_tags_dialog.show()
        connect(self.add_tags_dialog.save_button_clicked, self.save_edited_tags)

    def on_table_item_clicked(self, item, doubleclick=False):
        # We don't want to trigger the click-based events on, say, Ctrl-click based selection
        if QGuiApplication.keyboardModifiers() != Qt.NoModifier:
            return
        # Skip emitting click event when the user clicked on some specific columns
        column_position = self.model().column_position
        if item.column() in (
            column_position.get(cname, False)
            for cname in (Column.ACTIONS, Column.STATUS, Column.VOTES, Column.SUBSCRIBED, Column.HEALTH)
        ):
            return

        data_item = self.model().data_items[item.row()]
        # Safely determine if the thing is a channel. A little bit hackish
        if data_item.get('type') in [CHANNEL_TORRENT, COLLECTION_NODE]:
            self.channel_clicked.emit(data_item)

        if data_item.get('type') == REGULAR_TORRENT:
            if not doubleclick:
                self.torrent_clicked.emit(data_item)
            else:
                self.torrent_doubleclicked.emit(data_item)

    def on_torrent_status_updated(self, json_result, index):
        if not json_result:
            return

        if 'success' in json_result and json_result['success']:
            index.model().data_items[index.row()]['status'] = json_result['new_status']

            # Note: this should instead use signal and do not address the widget globally
            # and properly handle entry removal
            self.window().personal_channel_page.channel_dirty = (
                self.table_view.window().edit_channel_page.channel_dirty
                or json_result['new_status'] != COMMIT_STATUS_COMMITTED
            )
            self.window().personal_channel_page.update_channel_commit_views(deleted_index=index)

    def on_delete_button_clicked(self, _index):
        self.model().delete_rows(self.selectionModel().selectedRows())

    def on_move_button_clicked(self, _index):
        self.model().delete_rows(self.selectionModel().selectedRows())

    def resizeEvent(self, _):
        if self.model() is None:
            return
        viewport_width = self.width()
        for col_num, col in enumerate(self.model().columns):
            self.setColumnWidth(
                col_num, col.width if col.width != EXPANDING else viewport_width - self.model().min_columns_width - 20
            )
        self.loading_animation_widget.update_position()

        name_column_pos = self.model().column_position.get(Column.NAME)
        self.model().name_column_width = self.columnWidth(name_column_pos)

    def start_download_from_index(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def start_download_from_dataitem(self, data_item):
        self.window().start_download_from_uri(data_item2uri(data_item))

    def on_tags_edited(self, index, tags):
        if self.add_tags_dialog:
            self.add_tags_dialog.close_dialog()
            self.add_tags_dialog = None

        data_item = self.model().data_items[index.row()]
        data_item["tags"] = tags
        self.redraw(index, True)

        self.edited_tags.emit(data_item)

    def save_edited_tags(self, index: QModelIndex, tags: List[str]):
        data_item = self.model().data_items[index.row()]
        TriblerNetworkRequest(f"tags/{data_item['infohash']}",
                              lambda _, ind=index, tgs=tags: self.on_tags_edited(ind, tgs),
                              raw_data=json.dumps({"tags": tags}),
                              method='PATCH',
        )
