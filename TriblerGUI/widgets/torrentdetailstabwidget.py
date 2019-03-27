from __future__ import absolute_import

import logging
import time

from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem

from TriblerGUI.defs import HEALTH_CHECKING, HEALTH_GOOD, HEALTH_MOOT, HEALTH_UNCHECKED
from TriblerGUI.tribler_app import TriblerApplication
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, get_health
from TriblerGUI.widgets.ellipsebutton import EllipseButton


class TorrentDetailsTabWidget(QTabWidget):
    """
    The TorrentDetailsTabWidget is the tab that provides details about a specific selected torrent. This information
    includes the generic info about the torrent and trackers.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.torrent_info = None
        self._logger = logging.getLogger("TriberGUI")

        self.torrent_detail_name_label = None
        self.torrent_detail_infohash_label = None
        self.torrent_detail_category_label = None
        self.torrent_detail_size_label = None
        self.torrent_detail_health_label = None
        self.torrent_detail_trackers_list = None
        self.check_health_button = None
        self.copy_infohash_button = None
        self.request_mgr = None
        self.health_request_mgr = None
        self.is_health_checking = False
        self.index = QModelIndex()

    def initialize_details_widget(self):
        """
        Initialize the details widget. We need to manually assign these attributes since we're dynamically loading
        this view (using uic.loadUI).
        """
        self.torrent_detail_name_label = self.findChild(QLabel, "torrent_detail_name_label")
        self.torrent_detail_infohash_label = self.findChild(QLabel, "torrent_detail_infohash_label")
        self.torrent_detail_category_label = self.findChild(QLabel, "torrent_detail_category_label")
        self.torrent_detail_size_label = self.findChild(QLabel, "torrent_detail_size_label")
        self.torrent_detail_health_label = self.findChild(QLabel, "torrent_detail_health_label")
        self.torrent_detail_trackers_list = self.findChild(QTreeWidget, "torrent_detail_trackers_list")
        self.setCurrentIndex(0)

        self.check_health_button = self.findChild(EllipseButton, "check_health_button")
        self.check_health_button.clicked.connect(self.on_check_health_clicked)
        self.copy_infohash_button = self.findChild(EllipseButton, "copy_infohash_button")
        self.copy_infohash_button.clicked.connect(self.on_copy_infohash_clicked)

    def on_torrent_info(self, torrent_info):
        if not torrent_info or "torrent" not in torrent_info:
            return
        self.setTabEnabled(1, True)

        self.torrent_detail_trackers_list.clear()

        for tracker in torrent_info["torrent"]["trackers"]:
            item = QTreeWidgetItem(self.torrent_detail_trackers_list)
            item.setText(0, tracker)

        if self.is_health_checking:
            self.health_request_mgr.cancel_request()
            self.is_health_checking = False

        self.update_health_label(torrent_info["torrent"]['num_seeders'],
                                 torrent_info["torrent"]['num_leechers'],
                                 torrent_info["torrent"]['last_tracker_check'])

        # If we do not have the health of this torrent, query it
        if torrent_info['torrent']['last_tracker_check'] == 0:
            self.check_torrent_health()

    def update_with_torrent(self, index, torrent_info):
        self.torrent_info = torrent_info
        self.index = index
        self.torrent_detail_name_label.setText(self.torrent_info["name"])
        if self.torrent_info["category"]:
            self.torrent_detail_category_label.setText(self.torrent_info["category"].lower())
        else:
            self.torrent_detail_category_label.setText("unknown")

        if self.torrent_info["size"] is None:
            self.torrent_detail_size_label.setText("Size: -")
        else:
            self.torrent_detail_size_label.setText("%s" % format_size(float(self.torrent_info["size"])))

        self.update_health_label(torrent_info['num_seeders'], torrent_info['num_leechers'],
                                 torrent_info['last_tracker_check'])

        self.torrent_detail_infohash_label.setText(self.torrent_info["infohash"])

        self.setCurrentIndex(0)
        self.setTabEnabled(1, False)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("metadata/torrents/%s" % self.torrent_info["infohash"], self.on_torrent_info)

    def on_check_health_clicked(self):
        if not self.is_health_checking:
            self.check_torrent_health()

    def update_health_label(self, seeders, leechers, last_tracker_check):
        try:
            health = get_health(seeders, leechers, last_tracker_check)

            if health == HEALTH_UNCHECKED:
                self.torrent_detail_health_label.setText("Unknown health")
            elif health == HEALTH_GOOD:
                self.torrent_detail_health_label.setText("Good health (S%d L%d)" % (seeders, leechers))
            elif health == HEALTH_MOOT:
                self.torrent_detail_health_label.setText("Unknown health (found peers)")
            else:
                self.torrent_detail_health_label.setText("No peers found")
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

    def check_torrent_health(self):
        infohash = self.torrent_info[u'infohash']

        def on_cancel_health_check():
            self.is_health_checking = False

        if u'health' in self.index.model().column_position:
            # TODO: DRY this copypaste!
            # Check if details widget is still showing the same entry and the entry still exists in the table
            try:
                data_item = self.index.model().data_items[self.index.row()]
            except IndexError:
                return
            if self.torrent_info["infohash"] != data_item[u'infohash']:
                return
            data_item[u'health'] = HEALTH_CHECKING
            index = self.index.model().index(self.index.row(), self.index.model().column_position[u'health'])
            self.index.model().dataChanged.emit(index, index, [])

        self.torrent_detail_health_label.setText("Checking...")
        self.health_request_mgr = TriblerRequestManager()
        self.health_request_mgr.perform_request("metadata/torrents/%s/health" % infohash,
                                                self.on_health_response,
                                                url_params={"nowait": True,
                                                            "refresh": True},
                                                capture_errors=False, priority="LOW",
                                                on_cancel=on_cancel_health_check)

    def on_health_response(self, response):
        total_seeders = 0
        total_leechers = 0

        if not response or 'error' in response:
            self.update_torrent_health(0, 0)  # Just set the health to 0 seeders, 0 leechers
            return

        if 'checking' in response:
            return
        for _, status in response['health'].items():
            if 'error' in status:
                continue  # Timeout or invalid status
            total_seeders += int(status['seeders'])
            total_leechers += int(status['leechers'])

        self.update_torrent_health(total_seeders, total_leechers)

    def update_torrent_health(self, seeders, leechers):
        # Check if details widget is still showing the same entry and the entry still exists in the table
        try:
            data_item = self.index.model().data_items[self.index.row()]
        except IndexError:
            return
        if self.torrent_info["infohash"] != data_item[u'infohash']:
            return

        data_item[u'num_seeders'] = seeders
        data_item[u'num_leechers'] = leechers
        data_item[u'last_tracker_check'] = time.time()
        data_item[u'health'] = get_health(data_item[u'num_seeders'], data_item[u'num_leechers'],
                                          data_item[u'last_tracker_check'])

        if u'health' in self.index.model().column_position:
            index = self.index.model().index(self.index.row(), self.index.model().column_position[u'health'])
            self.index.model().dataChanged.emit(index, index, [])

        # Update the health label of the detail widget
        self.update_health_label(data_item[u'num_seeders'], data_item[u'num_leechers'],
                                 data_item[u'last_tracker_check'])

    def on_copy_infohash_clicked(self):
        cb = TriblerApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(self.torrent_detail_infohash_label.text(), mode=cb.Clipboard)
