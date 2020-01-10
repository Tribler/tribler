import logging
import time

from PyQt5 import uic
from PyQt5.QtCore import QModelIndex, QTimer
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QLabel, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem

from tribler_gui.defs import HEALTH_CHECKING, HEALTH_GOOD, HEALTH_MOOT, HEALTH_UNCHECKED
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import compose_magnetlink, copy_to_clipboard, format_size, get_health, get_ui_file_path
from tribler_gui.widgets.ellipsebutton import EllipseButton

HEALTHCHECK_DELAY = 500


class TorrentDetailsTabWidget(QTabWidget):
    """
    The TorrentDetailsTabWidget is the tab that provides details about a specific selected torrent. This information
    includes the generic info about the torrent and trackers.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        uic.loadUi(get_ui_file_path('torrent_details_container.ui'), self)

        self.torrent_info = None
        self._logger = logging.getLogger("TriberGUI")

        self.torrent_detail_name_label = None
        self.torrent_detail_infohash_label = None
        self.torrent_detail_category_label = None
        self.torrent_detail_size_label = None
        self.torrent_detail_health_label = None
        self.torrent_detail_trackers_list = None
        self.check_health_button = None
        self.copy_magnet_button = None
        self.is_health_checking = False
        self.index = QModelIndex()

        self.healthcheck_timer = QTimer()
        self.healthcheck_timer.setSingleShot(True)
        self.healthcheck_timer.timeout.connect(self.check_torrent_health)
        self.currentChanged.connect(self.on_tab_changed)

        self.rest_request1 = None
        self.rest_request2 = None

    def on_tab_changed(self, index):
        if index == 1 and self.torrent_info:
            if "trackers" in self.torrent_info:
                for tracker in self.torrent_info["trackers"]:
                    item = QTreeWidgetItem(self.torrent_detail_trackers_list)
                    item.setText(0, tracker)
            else:
                self.rest_request1 = TriblerNetworkRequest(
                    "metadata/%s/%s" % (self.torrent_info["public_key"], self.torrent_info["id"]), self.on_torrent_info
                )

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
        self.copy_magnet_button = self.findChild(QToolButton, "copy_magnet_button")
        self.copy_magnet_button.clicked.connect(self.on_copy_magnet_clicked)

    def on_torrent_info(self, torrent_info):
        # TODO: DRY this with on_tab_changed
        if not torrent_info or "infohash" not in torrent_info:
            return

        if self.torrent_info["infohash"] != torrent_info['infohash']:
            return
        self.torrent_info.update(torrent_info)
        for tracker in torrent_info["trackers"]:
            item = QTreeWidgetItem(self.torrent_detail_trackers_list)
            item.setText(0, tracker)

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

        self.update_health_label(
            torrent_info['num_seeders'], torrent_info['num_leechers'], torrent_info['last_tracker_check']
        )

        self.torrent_detail_infohash_label.setText(self.torrent_info["infohash"])

        self.setCurrentIndex(0)
        self.setTabEnabled(1, True)

        # If we do not have the health of this torrent, query it, but do it delayed.
        # When the user scrolls the list, we only want to trigger health checks on the line
        # that the user stopped on, so we do not generate excessive health checks.
        if self.is_health_checking:
            if self.rest_request1:
                self.rest_request1.cancel_request()
            if self.rest_request2:
                self.rest_request2.cancel_request()
            self.is_health_checking = False
        if torrent_info['last_tracker_check'] == 0:
            self.healthcheck_timer.stop()
            self.healthcheck_timer.start(HEALTHCHECK_DELAY)
        self.update_health_label(
            torrent_info['num_seeders'], torrent_info['num_leechers'], torrent_info['last_tracker_check']
        )

        self.torrent_detail_trackers_list.clear()

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
        if not self.torrent_info:
            return
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
        self.rest_request2 = TriblerNetworkRequest(
            "metadata/torrents/%s/health" % infohash,
            self.on_health_response,
            url_params={"nowait": True, "refresh": True},
            capture_errors=False,
            priority=QNetworkRequest.LowPriority,
            on_cancel=on_cancel_health_check,
        )

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
        data_item[u'health'] = get_health(
            data_item[u'num_seeders'], data_item[u'num_leechers'], data_item[u'last_tracker_check']
        )

        if u'health' in self.index.model().column_position:
            index = self.index.model().index(self.index.row(), self.index.model().column_position[u'health'])
            self.index.model().dataChanged.emit(index, index, [])

        # Update the health label of the detail widget
        self.update_health_label(
            data_item[u'num_seeders'], data_item[u'num_leechers'], data_item[u'last_tracker_check']
        )

    def on_copy_magnet_clicked(self):
        magnet_link = compose_magnetlink(
            self.torrent_info['infohash'],
            name=self.torrent_info.get('name', None),
            trackers=self.torrent_info.get('trackers', None),
        )
        copy_to_clipboard(magnet_link)
        self.window().tray_show_message("Copying magnet link", magnet_link)
