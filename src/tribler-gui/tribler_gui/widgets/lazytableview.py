from PyQt5.QtCore import QModelIndex, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QAbstractItemView, QTableView

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED
from tribler_gui.utilities import data_item2uri, index2uri
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
        self.mouse_moved.connect(self.delegate.on_mouse_moved)
        self.delegate.redraw_required.connect(self.redraw)

        # Stop triggering editor events on doubleclick, because we already use doubleclick to start downloads.
        # Editing should be started manually, from drop-down menu instead.
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Mix-in connects
        self.clicked.connect(self.on_table_item_clicked)
        self.doubleClicked.connect(lambda item: self.on_table_item_clicked(item, doubleclick=True))

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
        if u'subscribed' not in item or item[u'status'] == 1000 or item[u'state'] == u'Personal':
            return

        status = int(item[u'subscribed'])
        index.model().setData(index, int(not status), role=Qt.EditRole)

    def on_table_item_clicked(self, item, doubleclick=False):
        # We don't want to trigger the click-based events on, say, Ctrl-click based selection
        if QGuiApplication.keyboardModifiers() != Qt.NoModifier:
            return
        # Skip emitting click event when the user clicked on some specific columns
        column_position = self.model().column_position
        if (
            (ACTION_BUTTONS in column_position and item.column() == column_position[ACTION_BUTTONS])
            or (u'status' in column_position and item.column() == column_position[u'status'])
            or (u'votes' in column_position and item.column() == column_position[u'votes'])
            or (u'subscribed' in column_position and item.column() == column_position[u'subscribed'])
            or (u'health' in column_position and item.column() == column_position[u'health'])
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
            index.model().data_items[index.row()][u'status'] = json_result['new_status']

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
