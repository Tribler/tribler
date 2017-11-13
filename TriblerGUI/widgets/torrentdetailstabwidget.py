from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size


class TorrentDetailsTabWidget(QTabWidget):
    """
    The TorrentDetailsTabWidget is the tab that provides details about a specific selected torrent. This information
    includes the generic info about the torrent, files and trackers.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.torrent_info = None

        self.torrent_detail_name_label = None
        self.torrent_detail_category_label = None
        self.torrent_detail_size_label = None
        self.torrent_detail_health_label = None
        self.torrent_detail_files_list = None
        self.torrent_detail_trackers_list = None
        self.request_mgr = None

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
        else:
            self.torrent_detail_health_label.setText("no peers found")

        self.setCurrentIndex(0)
        self.setTabEnabled(1, False)
        self.setTabEnabled(2, False)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("torrents/%s" % self.torrent_info["infohash"], self.on_torrent_info)
