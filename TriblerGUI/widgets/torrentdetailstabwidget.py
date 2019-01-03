from __future__ import absolute_import

import logging

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem

from TriblerGUI.defs import HEALTH_CHECKING
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size
from TriblerGUI.widgets.ellipsebutton import EllipseButton


class TorrentDetailsTabWidget(QTabWidget):
    health_check_clicked = pyqtSignal(dict)
    """
    The TorrentDetailsTabWidget is the tab that provides details about a specific selected torrent. This information
    includes the generic info about the torrent, files and trackers.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.torrent_info = None
        self._logger = logging.getLogger("TriberGUI")

        self.torrent_detail_name_label = None
        self.torrent_detail_category_label = None
        self.torrent_detail_size_label = None
        self.torrent_detail_health_label = None
        self.torrent_detail_files_list = None
        self.torrent_detail_trackers_list = None
        self.check_health_button = None
        self.request_mgr = None
        self.health_request_mgr = None
        self.is_health_checking = False
        self.last_health_check_ts = -1

    def initialize_details_widget(self):
        """
        Initialize the details widget. We need to manually assign these attributes since we're dynamically loading
        this view (using uic.loadUI).
        """
        self.torrent_detail_name_label = self.findChild(QLabel, "torrent_detail_name_label")
        self.torrent_detail_category_label = self.findChild(QLabel, "torrent_detail_category_label")
        self.torrent_detail_size_label = self.findChild(QLabel, "torrent_detail_size_label")
        self.torrent_detail_health_label = self.findChild(QLabel, "torrent_detail_health_label")
        self.torrent_detail_files_list = self.findChild(QTreeWidget, "torrent_detail_files_list")
        self.torrent_detail_trackers_list = self.findChild(QTreeWidget, "torrent_detail_trackers_list")
        self.setCurrentIndex(0)

        self.check_health_button = self.findChild(EllipseButton, "check_health_button")
        self.check_health_button.clicked.connect(lambda: self.on_check_health_clicked(timeout=15))

    def on_torrent_info(self, torrent_info):
        if not torrent_info:
            return
        self.setTabEnabled(1, True)
        self.setTabEnabled(2, True)

        self.torrent_detail_files_list.clear()
        self.torrent_detail_trackers_list.clear()

        for file_info in torrent_info["files"]:
            item = QTreeWidgetItem(self.torrent_detail_files_list)
            item.setText(0, file_info["path"])
            item.setText(1, format_size(float(file_info["size"])))

        for tracker in torrent_info["trackers"]:
            if tracker == 'DHT':
                continue
            item = QTreeWidgetItem(self.torrent_detail_trackers_list)
            item.setText(0, tracker)

        if torrent_info["num_seeders"] > 0:
            self.torrent_detail_health_label.setText("good health (S%d L%d)" % (torrent_info["num_seeders"],
                                                                                torrent_info["num_leechers"]))
        elif torrent_info["num_leechers"] > 0:
            self.torrent_detail_health_label.setText("unknown health (found peers)")
        elif self.is_health_checking or (u'health' in torrent_info and torrent_info[u'health'] == HEALTH_CHECKING):
            self.torrent_detail_health_label.setText("Checking...")
        else:
            self.torrent_detail_health_label.setText("no peers found")

    def update_with_torrent(self, torrent_info):
        self.torrent_info = torrent_info
        self.torrent_detail_name_label.setText(self.torrent_info["name"])
        if self.torrent_info["category"]:
            self.torrent_detail_category_label.setText(self.torrent_info["category"].lower())
        else:
            self.torrent_detail_category_label.setText("unknown")

        if self.torrent_info["size"] is None:
            self.torrent_detail_size_label.setText("Size: -")
        else:
            self.torrent_detail_size_label.setText("%s" % format_size(float(self.torrent_info["size"])))

        if self.torrent_info["num_seeders"] > 0:
            self.torrent_detail_health_label.setText("good health (S%d L%d)" % (self.torrent_info["num_seeders"],
                                                                                self.torrent_info["num_leechers"]))
        elif self.torrent_info["num_leechers"] > 0:
            self.torrent_detail_health_label.setText("unknown health (found peers)")
        elif self.is_health_checking or (u'health' in torrent_info and torrent_info[u'health'] == HEALTH_CHECKING):
            self.torrent_detail_health_label.setText("Checking...")
        else:
            self.torrent_detail_health_label.setText("no peers found")

        self.setCurrentIndex(0)
        self.setTabEnabled(1, False)
        self.setTabEnabled(2, False)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("torrents/%s" % self.torrent_info["infohash"], self.on_torrent_info)

    def on_check_health_clicked(self, timeout=15):
        self.health_check_clicked.emit(self.torrent_info)

    def update_health(self, seeders, leechers, health=None):
        try:
            if seeders > 0:
                self.torrent_detail_health_label.setText("good health (S%d L%d)" % (seeders, leechers))
            elif leechers > 0:
                self.torrent_detail_health_label.setText("unknown health (found peers)")
            elif health == HEALTH_CHECKING:
                self.torrent_detail_health_label.setText("Checking...")
            else:
                self.torrent_detail_health_label.setText("no peers found")
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

    def on_cancel_health_check(self):
        self.is_health_checking = False

    def update_from_model(self, i1, i2, role):
        if not self.torrent_info:
            return

        # We only react to very specific update type that was generated by our actions
        if i1.row() == i2.row():
            torrent_info = i1.model().data_items[i1.row()]
            if self.torrent_info[u'infohash'] == torrent_info[u'infohash']:
                self.is_health_checking = torrent_info[u'health'] == HEALTH_CHECKING
                self.update_health(torrent_info[u'num_seeders'], torrent_info[u'num_leechers'],
                                   health=torrent_info[u'health'])
