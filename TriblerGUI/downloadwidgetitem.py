from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QTreeWidgetItem, QProgressBar
from TriblerGUI.defs import DLSTATUS_STRINGS


class DownloadWidgetItem(QTreeWidgetItem):

    def __init__(self, parent):
        super(DownloadWidgetItem, self).__init__(parent)
        self.progress_slider = QProgressBar()
        self.progress_slider.setStyleSheet("""
        QProgressBar {
            margin: 4px;
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
        self.download_status_raw = -1

    def updateWithDownload(self, download):
        self.setText(0, download["name"])
        self.setText(1, download["size"])

        self.progress_slider.setValue(int(download["progress"] * 100))

        self.setText(3, DLSTATUS_STRINGS[download["status"]])
        self.setText(4, str(download["seeds"]))
        self.setText(5, str(download["peers"]))
        self.setText(6, str(download["down_speed"]))
        self.setText(7, str(download["up_speed"]))
        self.setText(8, "-")

        self.download_status_raw = download["status"]
