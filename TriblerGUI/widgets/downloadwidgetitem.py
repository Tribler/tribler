from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QTreeWidgetItem, QProgressBar
from TriblerGUI.defs import *
from TriblerGUI.utilities import format_size, format_speed, duration_to_string


class DownloadWidgetItem(QTreeWidgetItem):
    """
    This class is responsible for managing the item in the downloads list and fills the item with the relevant data.
    """

    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent)
        self.download_info = None
        self.progress_slider = QProgressBar()
        self.progress_slider.setStyleSheet("""
        QProgressBar {
            margin: 8px;
            margin-left: 0;
            background-color: white;
            color: #ddd;
            font-size: 12px;
            text-align: center;
        }

        QProgressBar::chunk {
            background-color: #e67300;
        }
        """)

        parent.setItemWidget(self, 2, self.progress_slider)
        self.setSizeHint(0, QSize(-1, 24))

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
            pass

        self.setText(3, DLSTATUS_STRINGS[eval(self.download_info["status"])])
        self.setText(4, str(self.download_info["num_seeds"]))
        self.setText(5, str(self.download_info["num_peers"]))
        self.setText(6, format_speed(self.download_info["speed_down"]))
        self.setText(7, format_speed(self.download_info["speed_up"]))
        self.setText(8, "yes" if self.download_info["anon_download"] else "no")
        self.setText(9, str(self.download_info["hops"]) if self.download_info["anon_download"] else "-")

        eta_text = "-"
        if self.get_raw_download_status() == DLSTATUS_DOWNLOADING:
            eta_text = duration_to_string(self.download_info["eta"])
        self.setText(10, eta_text)

    def __lt__(self, other):
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
        elif column == 10:
            return float(self.download_info["eta"]) > float(other.download_info["eta"])
        return self.text(column) > other.text(column)
