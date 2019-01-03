from __future__ import absolute_import, division

from PyQt5.QtCore import QModelIndex, QPoint, pyqtSignal
from PyQt5.QtWidgets import QTableView

from TriblerGUI.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED, COMMIT_STATUS_NEW, COMMIT_STATUS_TODELETE, \
    PAGE_CHANNEL_DETAILS
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import index2uri
from TriblerGUI.widgets.tablecontentdelegate import ChannelsButtonsDelegate, SearchResultsDelegate, \
    TorrentsButtonsDelegate
from TriblerGUI.widgets.tablecontentmodel import MyTorrentsContentModel


class LazyTableView(QTableView):
    """
    This table view is designed to support lazy loading.
    When the user reached the end of the table, it will ask the model for more items, and load them dynamically.
    """
    pass


class TriblerContentTableView(LazyTableView):
    # TODO: add redraw when the mouse leaves the view through the header
    # overloading leaveEvent method could be used for that
    mouse_moved = pyqtSignal(QPoint, QModelIndex)

    def __init__(self, parent=None):
        LazyTableView.__init__(self, parent)

        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        index = QModelIndex(self.indexAt(event.pos()))
        self.mouse_moved.emit(event.pos(), index)

    def redraw(self):
        self.viewport().update()


class SearchResultsTableView(TriblerContentTableView):
    """
    This table displays search results, which can be both torrents and channels.
    """
    on_torrent_clicked = pyqtSignal(dict)
    on_channel_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        TriblerContentTableView.__init__(self, parent)

        self.delegate = SearchResultsDelegate()
        self.setItemDelegate(self.delegate)
        self.mouse_moved.connect(self.delegate.on_mouse_moved)
        self.delegate.redraw_required.connect(self.redraw)

        self.clicked.connect(self.on_table_item_clicked)

    def on_table_item_clicked(self, item):
        content_info = self.model().data_items[item.row()]
        if content_info['type'] == 'channel':
            self.window().channel_page.initialize_with_channel(content_info)
            self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
            self.window().stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)
            self.on_channel_clicked.emit(content_info)
        else:
            self.on_torrent_clicked.emit(content_info)

    def resizeEvent(self, _):
        self.setColumnWidth(0, 100)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(1, self.width() - 304)  # Few pixels offset so the horizontal scrollbar does not appear


class TorrentsTableView(TriblerContentTableView):
    """
    This table displays various torrents.
    """
    on_torrent_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        TriblerContentTableView.__init__(self, parent)

        self.delegate = TorrentsButtonsDelegate()
        self.setItemDelegate(self.delegate)
        self.mouse_moved.connect(self.delegate.on_mouse_moved)
        self.delegate.redraw_required.connect(self.redraw)

        self.delegate.play_button.clicked.connect(self.on_play_button_clicked)
        self.delegate.download_button.clicked.connect(self.on_download_button_clicked)
        self.delegate.commit_control.clicked.connect(self.on_commit_control_clicked)

        self.clicked.connect(self.on_table_item_clicked)

    def on_table_item_clicked(self, item):
        if (ACTION_BUTTONS in self.model().column_position and
                item.column() == self.model().column_position[ACTION_BUTTONS]) or \
                (u'status' in self.model().column_position and
                 item.column() == self.model().column_position[u'status']):
            return

        torrent_info = self.model().data_items[item.row()]
        self.on_torrent_clicked.emit(torrent_info)

    def on_play_button_clicked(self, index):
        infohash = index.model().data_items[index.row()][u'infohash']

        def on_play_request_done(_):
            if not self:
                return
            self.window().left_menu_button_video_player.click()
            self.window().video_player_page.play_media_item(infohash, -1)

        self.window().perform_start_download_request(index2uri(index),
                                                     self.window().tribler_settings['download_defaults'][
                                                         'anonymity_enabled'],
                                                     self.window().tribler_settings['download_defaults'][
                                                         'safeseeding_enabled'],
                                                     self.window().tribler_settings['download_defaults']['saveas'],
                                                     [], 0, callback=on_play_request_done)

    def on_download_button_clicked(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def on_commit_control_clicked(self, index):
        infohash = index.model().data_items[index.row()][u'infohash']
        status = index.model().data_items[index.row()][u'status']

        new_status = COMMIT_STATUS_COMMITTED
        if status == COMMIT_STATUS_NEW or status == COMMIT_STATUS_COMMITTED:
            new_status = COMMIT_STATUS_TODELETE

        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/torrents/%s" % infohash,
                                    lambda response: self.on_torrent_status_updated(response, index),
                                    data='status=%d' % new_status, method='PATCH')

    def on_torrent_status_updated(self, json_result, index):
        if not json_result:
            return

        if 'success' in json_result and json_result['success']:
            index.model().data_items[index.row()][u'status'] = json_result['new_status']

    def resizeEvent(self, _):
        if isinstance(self.model(), MyTorrentsContentModel):
            self.setColumnWidth(0, 100)
            self.setColumnWidth(2, 100)
            self.setColumnWidth(3, 100)
            self.setColumnWidth(1, self.width() - 304)  # Few pixels offset so the horizontal scrollbar does not appear
        else:
            self.setColumnWidth(0, 100)
            self.setColumnWidth(2, 100)
            self.setColumnWidth(3, 100)
            self.setColumnWidth(4, 100)
            self.setColumnWidth(1, self.width() - 404)  # Few pixels offset so the horizontal scrollbar does not appear


class ChannelsTableView(TriblerContentTableView):
    """
    This table displays various channels.
    """
    on_channel_clicked = pyqtSignal(dict)
    on_unsubscribed_channel = pyqtSignal(QModelIndex)
    on_subscribed_channel = pyqtSignal(QModelIndex)

    def __init__(self, parent=None):
        TriblerContentTableView.__init__(self, parent)

        delegate = ChannelsButtonsDelegate()
        self.setItemDelegate(delegate)
        self.mouse_moved.connect(delegate.on_mouse_moved)
        delegate.redraw_required.connect(self.redraw)
        delegate.subscribe_control.clicked.connect(self.on_subscribe_control_clicked)

        self.clicked.connect(self.on_table_item_clicked)

    def on_subscribe_control_clicked(self, index):
        status = int(index.model().data_items[index.row()][u'subscribed'])
        if status:
            self.on_unsubscribe_button_clicked(index)
        else:
            self.on_subscribe_button_clicked(index)
        index.model().data_items[index.row()][u'subscribed'] = int(not status)

    def on_subscribe_button_clicked(self, index):
        public_key = index.model().data_items[index.row()][u'public_key']
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("metadata/channels/%s" % public_key,
                                    lambda _: self.on_subscribed_channel.emit(index),
                                    data='subscribe=1', method='POST')

    def on_unsubscribe_button_clicked(self, index):
        public_key = index.model().data_items[index.row()][u'public_key']
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("metadata/channels/%s" % public_key,
                                    lambda _: self.on_unsubscribed_channel.emit(index),
                                    data='subscribe=0', method='POST')

    def on_table_item_clicked(self, item):
        if item.column() == self.model().column_position[u'subscribed']:
            return

        channel_info = self.model().data_items[item.row()]
        self.window().channel_page.initialize_with_channel(channel_info)
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

        self.on_channel_clicked.emit(channel_info)

    def resizeEvent(self, _):
        self.setColumnWidth(1, 150)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(0, self.width() - 254)  # Few pixels offset so the horizontal scrollbar does not appear
