from PyQt5.QtCore import QModelIndex, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QMovie
from PyQt5.QtWidgets import QAbstractItemView, QLabel, QTableView

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED
from tribler_gui.utilities import connect, data_item2uri, get_image_path, index2uri
from tribler_gui.widgets.tablecontentdelegate import TriblerContentDelegate


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

    # Probably should add redraw when the mouse leaves the view through the header.
    # Overloading leaveEvent method could be used for that
    mouse_moved = pyqtSignal(QPoint, QModelIndex)

    channel_clicked = pyqtSignal(dict)
    torrent_clicked = pyqtSignal(dict)
    torrent_doubleclicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.setMouseTracking(True)

        self.delegate = TriblerContentDelegate()

        self.setItemDelegate(self.delegate)
        connect(self.mouse_moved, self.delegate.on_mouse_moved)
        connect(self.delegate.redraw_required, self.redraw)

        # Stop triggering editor events on doubleclick, because we already use doubleclick to start downloads.
        # Editing should be started manually, from drop-down menu instead.
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Mix-in connects
        connect(self.clicked, self.on_table_item_clicked)
        connect(self.doubleClicked, lambda item: self.on_table_item_clicked(item, doubleclick=True))

        self.loading_animation_widget = FloatingAnimationWidget(self)
        self.hide_loading_animation()

    def show_loading_animation(self):
        self.loading_animation_widget.qm.start()
        self.loading_animation_widget.setHidden(False)

    def hide_loading_animation(self):
        self.loading_animation_widget.qm.stop()
        self.loading_animation_widget.setHidden(True)

    def mouseMoveEvent(self, event):
        index = QModelIndex(self.indexAt(event.pos()))
        self.mouse_moved.emit(event.pos(), index)

    def redraw(self):
        self.viewport().update()
        # This is required to drop the sensitivity zones of the controls,
        # so there are no invisible controls left over from a previous state of the view
        for control in self.delegate.controls:
            control.rect = QRect()

    def on_subscribe_control_clicked(self, index):
        item = index.model().data_items[index.row()]
        # skip LEGACY entries, regular torrents and personal channel
        if 'subscribed' not in item or item['status'] == 1000 or item['state'] == 'Personal':
            return

        status = int(item['subscribed'])
        # index.model().setData(index, int(not status), role=Qt.EditRole)

        if status:
            self.window().on_channel_unsubscribe(item)
        else:
            self.window().on_channel_subscribe(item)

    def on_table_item_clicked(self, item, doubleclick=False):
        # We don't want to trigger the click-based events on, say, Ctrl-click based selection
        if QGuiApplication.keyboardModifiers() != Qt.NoModifier:
            return
        # Skip emitting click event when the user clicked on some specific columns
        column_position = self.model().column_position
        if item.column() in (
            column_position.get(cname, False) for cname in (ACTION_BUTTONS, 'status', 'votes', 'subscribed', 'health')
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
        for col_num, col in enumerate(self.model().columns):
            self.setColumnWidth(col_num, self.model().column_width.get(col, lambda _: 110)(self.width()))
        self.loading_animation_widget.update_position()

    def start_download_from_index(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def start_download_from_dataitem(self, data_item):
        self.window().start_download_from_uri(data_item2uri(data_item))
