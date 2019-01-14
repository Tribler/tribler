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
