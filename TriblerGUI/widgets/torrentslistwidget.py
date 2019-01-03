from __future__ import absolute_import

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_ui_file_path
from TriblerGUI.widgets.torrentdetailstabwidget import TorrentDetailsTabWidget


class TorrentsListWidget(QWidget):
    on_torrent_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        uic.loadUi(get_ui_file_path('torrents_list.ui'), self)

        self.model = None
        self.details_tab_widget = None

        self.details_tab_widget = self.findChild(TorrentDetailsTabWidget, "details_tab_widget")
        self.details_tab_widget.initialize_details_widget()
        self.details_tab_widget.health_check_clicked.connect(self.on_details_tab_widget_health_check_clicked)

    def on_details_tab_widget_health_check_clicked(self, torrent_info):
        infohash = torrent_info[u'infohash']
        if infohash in self.model.infohashes:
            self.model.check_torrent_health(self.model.index(self.model.infohashes[infohash], 0))

    # def on_table_item_clicked(self, item):
    #     if item.column() == self.content_table.model().column_position[ACTION_BUTTONS]
    #         return
    #     table_entry = self.content_table.model().data_items[item.row()]
    #     if table_entry['type'] == u'torrent':
    #         self.details_tab_widget.update_with_torrent(table_entry)
    #         self.model.check_torrent_health(item)
    #     elif table_entry['type'] == u'channel':
    #         self.on_torrent_clicked.emit(table_entry)
