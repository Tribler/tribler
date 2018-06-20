import logging
import time

from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size
from TriblerGUI.widgets.ellipsebutton import EllipseButton


class TorrentDetailsTabWidget(QTabWidget):
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
        else:
            self.torrent_detail_health_label.setText("no peers found")

    def update_with_torrent(self, torrent_info):
        self.torrent_info = torrent_info
        self.is_health_checking = False
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
        else:
            self.torrent_detail_health_label.setText("no peers found")

        self.setCurrentIndex(0)
        self.setTabEnabled(1, False)
        self.setTabEnabled(2, False)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("torrents/%s" % self.torrent_info["infohash"], self.on_torrent_info)

    def on_check_health_clicked(self, timeout=15):
        if self.is_health_checking and (time.time() - self.last_health_check_ts < timeout):
            return

        self.is_health_checking = True
        self.torrent_detail_health_label.setText("Checking...")
        self.last_health_check_ts = time.time()
        self.health_request_mgr = TriblerRequestManager()
        self.health_request_mgr.perform_request("torrents/%s/health?timeout=%s&refresh=%d" %
                                                (self.torrent_info["infohash"], timeout, 1),
                                                self.on_health_response, capture_errors=False, priority="LOW",
                                                on_cancel=self.on_cancel_health_check)

    def on_health_response(self, response):
        total_seeders = 0
        total_leechers = 0

        if not response or 'error' in response:
            self.update_health(0, 0)  # Just set the health to 0 seeders, 0 leechers
            return

        for _, status in response['health'].iteritems():
            if 'error' in status:
                continue  # Timeout or invalid status

            total_seeders += int(status['seeders'])
            total_leechers += int(status['leechers'])

        self.is_health_checking = False
        self.update_health(total_seeders, total_leechers)

    def update_health(self, seeders, leechers):
        try:
            if seeders > 0:
                self.torrent_detail_health_label.setText("good health (S%d L%d)" % (seeders, leechers))
            elif leechers > 0:
                self.torrent_detail_health_label.setText("unknown health (found peers)")
            else:
                self.torrent_detail_health_label.setText("no peers found")
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

    def on_cancel_health_check(self):
        self.is_health_checking = False
