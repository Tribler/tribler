from PyQt5.QtCore import QModelIndex, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QAbstractItemView, QTableView

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED
from tribler_gui.utilities import connect, data_item2uri, index2uri
from tribler_gui.widgets.tablecontentdelegate import TriblerContentDelegate


class TriblerContentTableView(QTableView):
    """
    This table view is designed to support lazy loading.
    When the user reached the end of the table, it will ask the model for more items, and load them dynamically.
    """

    # TODO: add redraw when the mouse leaves the view through the header
    # overloading leaveEvent method could be used for that
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
        return True

    def on_table_item_clicked(self, item, doubleclick=False):
        # We don't want to trigger the click-based events on, say, Ctrl-click based selection
        if QGuiApplication.keyboardModifiers() != Qt.NoModifier:
            return
        # Skip emitting click event when the user clicked on some specific columns
        column_position = self.model().column_position
        if (
            (ACTION_BUTTONS in column_position and item.column() == column_position[ACTION_BUTTONS])
            or ('status' in column_position and item.column() == column_position['status'])
            or ('votes' in column_position and item.column() == column_position['votes'])
            or ('subscribed' in column_position and item.column() == column_position['subscribed'])
            or ('health' in column_position and item.column() == column_position['health'])
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

            # FIXME: this should instead use signal and do not address the widget globally
            # FIXME: properly handle entry removal
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

    def start_download_from_index(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def start_download_from_dataitem(self, data_item):
        self.window().start_download_from_uri(data_item2uri(data_item))
