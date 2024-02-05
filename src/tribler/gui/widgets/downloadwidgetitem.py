import logging
import math
from datetime import datetime
from typing import Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QProgressBar, QTreeWidgetItem, QVBoxLayout, QWidget

from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.gui.defs import STATUS_STRING
from tribler.gui.utilities import duration_to_string, format_size, format_speed


class LoadingDownloadWidgetItem(QTreeWidgetItem):
    """
    This class is used for the placeholder "Loading" item for the downloads list
    """

    def __init__(self):
        QTreeWidgetItem.__init__(self)
        self.setFlags(Qt.NoItemFlags)

    def get_raw_download_status(self):
        return "PLACEHOLDER"


def create_progress_bar_widget() -> (QWidget, QProgressBar):
    progress_slider = QProgressBar()

    bar_container = QWidget()
    bar_container.setLayout(QVBoxLayout())
    bar_container.setStyleSheet("background-color: transparent;")

    # We have to set a zero pixel border to get the background working on Mac.
    progress_slider.setStyleSheet(
        """
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
    """
    )

    progress_slider.setAutoFillBackground(True)
    bar_container.layout().addWidget(progress_slider)
    bar_container.layout().setContentsMargins(4, 4, 8, 4)
    return bar_container, progress_slider


class DownloadWidgetItem(QTreeWidgetItem):
    """
    This class is responsible for managing the item in the downloads list and fills the item with the relevant data.
    """

    def __init__(self):
        QTreeWidgetItem.__init__(self)
        self.download_info: Optional[Dict] = None
        self.infohash: Optional[str] = None
        self._logger = logging.getLogger('TriblerGUI')
        self.bar_container, self.progress_slider = create_progress_bar_widget()

    def update_with_download(self, download: Dict):
        self.download_info = download
        self.infohash = download["infohash"]
        self.update_item()

    def get_status(self) -> DownloadStatus:
        return DownloadStatus(self.download_info["status_code"])

    def update_item(self):
        self.setText(0, self.download_info["name"])

        if self.download_info["size"] == 0 and self.get_status() == DownloadStatus.METADATA:
            self.setText(1, "unknown")
        else:
            self.setText(1, format_size(float(self.download_info["size"])))

        try:
            self.progress_slider.setValue(int(self.download_info["progress"] * 100))
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

        status = DownloadStatus(self.download_info["status_code"])
        status_string = STATUS_STRING[status]
        self.setText(3, status_string)
        self.setText(4, f"{self.download_info['num_connected_seeds']} ({self.download_info['num_seeds']})")
        self.setText(5, f"{self.download_info['num_connected_peers']} ({self.download_info['num_peers']})")
        self.setText(6, format_speed(self.download_info["speed_down"]))
        self.setText(7, format_speed(self.download_info["speed_up"]))

        all_time_ratio = self.download_info['all_time_ratio']
        all_time_ratio = '∞' if all_time_ratio == math.inf else f'{all_time_ratio:.3f}'
        self.setText(8, all_time_ratio)

        self.setText(9, "yes" if self.download_info["anon_download"] else "no")
        self.setText(10, str(self.download_info["hops"]) if self.download_info["anon_download"] else "-")
        self.setText(12, datetime.fromtimestamp(int(self.download_info["time_added"])).strftime('%Y-%m-%d %H:%M'))

        eta_text = "-"
        if self.get_status() == DownloadStatus.DOWNLOADING:
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
            return (float(self.download_info["eta"]) or float('inf')) > (
                    float(other.download_info["eta"]) or float('inf')
            )
        elif column == 12:
            return int(self.download_info["time_added"]) > int(other.download_info["time_added"])
        return self.text(column) > other.text(column)
