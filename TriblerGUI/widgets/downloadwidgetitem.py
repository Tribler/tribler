import logging
from PyQt5.QtWidgets import QTreeWidgetItem, QProgressBar
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from datetime import datetime

from TriblerGUI.defs import *
from TriblerGUI.utilities import format_size, format_speed, duration_to_string


class DownloadWidgetItem(QTreeWidgetItem):
    """
    This class is responsible for managing the item in the downloads list and fills the item with the relevant data.
    """

    def __init__(self):
        QTreeWidgetItem.__init__(self)
        self.download_info = None
        self._logger = logging.getLogger('TriblerGUI')

        bar_container = QWidget()
        bar_container.setLayout(QVBoxLayout())
        bar_container.setStyleSheet("background-color: transparent;")

        self.progress_slider = QProgressBar()

        # We have to set a zero pixel border to get the background working on Mac.
        self.progress_slider.setStyleSheet("""
        QProgressBar {
            background-color: white;
            color: black;
            font-size: 12px;
            text-align: center;
            border: 0px solid transparent;
        }

        QProgressBar::chunk {
            background-color: #e67300;
        }
        """)

        bar_container.layout().addWidget(self.progress_slider)
        bar_container.layout().setContentsMargins(4, 4, 8, 4)

        self.progress_slider.setAutoFillBackground(True)
        self.bar_container = bar_container

    def update_with_download(self, download):
        self.download_info = download
        self.update_item()

    def get_raw_download_status(self):
        return eval(self.download_info["status"])

    def update_item(self):
        self.setText(0, self.download_info["name"])
        self.setText(1, format_size(float(self.download_info["size"])))

        try:
            self.progress_slider.setValue(int(self.download_info["progress"] * 100))
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

        if self.download_info["vod_mode"]:
            self.setText(3, "Streaming")
        else:
            self.setText(3, DLSTATUS_STRINGS[eval(self.download_info["status"])])
        self.setText(4, "%s (%s)" % (self.download_info["num_connected_seeds"], self.download_info["num_seeds"]))
        self.setText(5, "%s (%s)" % (self.download_info["num_connected_peers"], self.download_info["num_peers"]))
        self.setText(6, format_speed(self.download_info["speed_down"]))
        self.setText(7, format_speed(self.download_info["speed_up"]))
        self.setText(8, "%.3f" % float(self.download_info["ratio"]))
        self.setText(9, "yes" if self.download_info["anon_download"] else "no")
        self.setText(10, str(self.download_info["hops"]) if self.download_info["anon_download"] else "-")
        self.setText(12, datetime.fromtimestamp(int(self.download_info["time_added"])).strftime('%Y-%m-%d %H:%M'))

        eta_text = "-"
        if self.get_raw_download_status() == DLSTATUS_DOWNLOADING:
            eta_text = duration_to_string(self.download_info["eta"])
        self.setText(11, eta_text)

    def __lt__(self, other):
        # The download info might not be available yet or there could still be loading QTreeWidgetItem
        if not self.download_info or not isinstance(other, DownloadWidgetItem):
            return True
        elif not other.download_info:
            return False

        column = self.treeWidget().sortColumn()
        if column == 1:
            return float(self.download_info["size"]) > float(other.download_info["size"])
        elif column == 2:
            return int(self.download_info["progress"] * 100) > int(other.download_info["progress"] * 100)
        elif column == 4:
            return self.download_info["num_seeds"] > other.download_info["num_seeds"]
        elif column == 5:
            return self.download_info["num_peers"] > other.download_info["num_peers"]
        elif column == 6:
            return float(self.download_info["speed_down"]) > float(other.download_info["speed_down"])
        elif column == 7:
            return float(self.download_info["speed_up"]) > float(other.download_info["speed_up"])
        elif column == 8:
            return float(self.download_info["ratio"]) > float(other.download_info["ratio"])
        elif column == 11:
            # Put finished downloads with an ETA of 0 after all other downloads
            return ((float(self.download_info["eta"]) or float('inf')) >
                    (float(other.download_info["eta"]) or float('inf')))
        elif column == 12:
            return int(self.download_info["time_added"]) > int(other.download_info["time_added"])
        return self.text(column) > other.text(column)
