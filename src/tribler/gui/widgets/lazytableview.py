import json
from typing import Dict, List

from PyQt5.QtCore import QEvent, QModelIndex, QRect, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QMouseEvent, QMovie
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QLabel, QTableView

from tribler.core.components.database.db.serialization import SNIPPET
from tribler.gui.dialogs.editmetadatadialog import EditMetadataDialog
from tribler.gui.network.request_manager import request_manager
from tribler.gui.utilities import connect, data_item2uri, get_image_path, index2uri
from tribler.gui.widgets.tablecontentdelegate import TriblerContentDelegate
from tribler.gui.widgets.tablecontentmodel import Column, EXPANDING


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
        self.setGeometry(int(x), int(y), self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_position()


class TriblerContentTableView(QTableView):
    """
    This table view is designed to support lazy loading.
    When the user reached the end of the table, it will ask the model for more items, and load them dynamically.
    """

    torrent_clicked = pyqtSignal(dict)
    torrent_doubleclicked = pyqtSignal(dict)
    edited_metadata = pyqtSignal(dict)

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
        model = index.model()
        if not model:
            return
        data_item = model.data_items[index.row()]
        if data_item["type"] == SNIPPET:
            should_select_row = False

        if index != self.delegate.no_index:
            # Check if we are clicking the 'edit tags' button
            if index in model.edit_tags_rects:
                rect = model.edit_tags_rects[index]
                if rect.contains(event.pos()) and event.button() != Qt.RightButton:
                    should_select_row = False
                    self.on_edit_tags_clicked(index)

            # Check if we are clicking the 'popular content' button
            if index in model.download_popular_content_rects:
                for torrent_index, rect in enumerate(model.download_popular_content_rects[index]):
                    if rect.contains(event.pos()) and event.button() != Qt.RightButton:
                        should_select_row = False
                        self.on_download_popular_torrent_clicked(index, torrent_index)

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
        if not self.model():
            return
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

    def on_edit_tags_clicked(self, index: QModelIndex) -> None:
        self.add_tags_dialog = EditMetadataDialog(self.window(), index)
        self.add_tags_dialog.show()
        connect(self.add_tags_dialog.save_button_clicked, self.save_edited_metadata)

    def on_download_popular_torrent_clicked(self, index: QModelIndex, torrent_index: int) -> None:
        data_item = index.model().data_items[index.row()]
        self.start_download_from_dataitem(data_item["torrents_in_snippet"][torrent_index])

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

        if not doubleclick:
            self.torrent_clicked.emit(data_item)
        else:
            self.torrent_doubleclicked.emit(data_item)

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

    def on_metadata_edited(self, index, statements: List[Dict]):
        if self.add_tags_dialog:
            self.add_tags_dialog.close_dialog()
            self.add_tags_dialog = None

        data_item = self.model().data_items[index.row()]
        data_item["statements"] = statements
        self.redraw(index, True)

        self.edited_metadata.emit(data_item)

    def save_edited_metadata(self, index: QModelIndex, statements: List[Dict]):
        def on_success(_):
            self.on_metadata_edited(index, statements)

        data_item = self.model().data_items[index.row()]
        request_manager.patch(f"knowledge/{data_item['infohash']}", on_success=on_success,
                              data=json.dumps({"statements": statements}))
