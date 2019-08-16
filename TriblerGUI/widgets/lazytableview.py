from __future__ import absolute_import, division

from PyQt5.QtCore import QModelIndex, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QTableView

from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from TriblerGUI.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED
from TriblerGUI.utilities import index2uri
from TriblerGUI.widgets.tablecontentdelegate import TriblerContentDelegate


class TriblerContentTableView(QTableView):
    """
    This table view is designed to support lazy loading.
    When the user reached the end of the table, it will ask the model for more items, and load them dynamically.
    """

    # TODO: add redraw when the mouse leaves the view through the header
    # overloading leaveEvent method could be used for that
    mouse_moved = pyqtSignal(QPoint, QModelIndex)

    channel_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.setMouseTracking(True)

        self.delegate = TriblerContentDelegate()

        self.setItemDelegate(self.delegate)
        self.mouse_moved.connect(self.delegate.on_mouse_moved)
        self.delegate.redraw_required.connect(self.redraw)

        # Mix-in connects
        self.clicked.connect(self.on_table_item_clicked)
        self.delegate.play_button.clicked.connect(self.on_play_button_clicked)
        self.delegate.subscribe_control.clicked.connect(self.on_subscribe_control_clicked)
        self.delegate.rating_control.clicked.connect(self.on_subscribe_control_clicked)
        self.delegate.download_button.clicked.connect(self.on_download_button_clicked)
        # TODO: status changing feature should remain turned off until we fix the undo mess
        self.delegate.delete_button.clicked.connect(self.on_delete_button_clicked)

    def mouseMoveEvent(self, event):
        index = QModelIndex(self.indexAt(event.pos()))
        self.mouse_moved.emit(event.pos(), index)

    def redraw(self):
        self.viewport().update()
        # This is required to drop the sensitivity zones of the controls,
        # so there are no invisible controls left over from a previous state of the view
        for control in self.delegate.controls:
            control.rect = QRect()

    def on_download_button_clicked(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def on_play_button_clicked(self, index):
        infohash = index.model().data_items[index.row()][u'infohash']

        def on_play_request_done(_):
            if not self:
                return
            self.window().left_menu_button_video_player.click()
            self.window().video_player_page.play_media_item(infohash, -1)

        self.window().perform_start_download_request(
            index2uri(index),
            self.window().tribler_settings['download_defaults']['anonymity_enabled'],
            self.window().tribler_settings['download_defaults']['safeseeding_enabled'],
            self.window().tribler_settings['download_defaults']['saveas'],
            [],
            0,
            callback=on_play_request_done,
        )

    def on_subscribe_control_clicked(self, index):
        item = index.model().data_items[index.row()]
        # skip LEGACY entries, regular torrents and personal channel
        if u'subscribed' not in item or item[u'status'] == 1000 or item[u'state'] == u'Personal':
            return

        status = int(item[u'subscribed'])
        index.model().setData(index, int(not status), role=Qt.EditRole)

    def on_table_item_clicked(self, item):
        # We don't want to trigger the click-based events on, say, Ctrl-click based selection
        if QGuiApplication.keyboardModifiers() != Qt.NoModifier:
            return
        column_position = self.model().column_position
        if (
            (ACTION_BUTTONS in column_position and item.column() == column_position[ACTION_BUTTONS])
            or (u'status' in column_position and item.column() == column_position[u'status'])
            or (u'votes' in column_position and item.column() == column_position[u'votes'])
            or (u'subscribed' in column_position and item.column() == column_position[u'subscribed'])
        ):
            return

        content_info = self.model().data_items[item.row()]
        # Safely determine if the thing is a channel. A little bit hackish
        if content_info.get('type', None) in [CHANNEL_TORRENT, COLLECTION_NODE]:
            self.channel_clicked.emit(content_info)

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
        for col_num, col in enumerate(self.model().columns):
            self.setColumnWidth(col_num, self.model().column_width.get(col, lambda _: 100)(self.width()))
