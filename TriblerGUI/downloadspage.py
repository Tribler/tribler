from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QWidget, QTreeWidget, QTreeWidgetItem, QProgressBar


class DownloadsPage(QWidget):

    def initialize_downloads_page(self):
        self.downloads_tab = self.findChild(QWidget, "downloads_tab")
        self.downloads_tab.initialize()
        self.downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)

        # TODO Martijn: for now, fill the downloads with some dummy data
        self.downloads_list = self.findChild(QTreeWidget, "downloads_list")

        for i in range(0, 10):
            item = QTreeWidgetItem(self.downloads_list)
            item.setSizeHint(0, QSize(-1, 24))
            item.setSizeHint(2, QSize(-1, 1))
            item.setText(0, "My.test.torrent.HD.iso")
            item.setText(1, "301.1 MB")

            slider = QProgressBar()
            slider.setStyleSheet("""
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
            slider.setValue(58)
            self.downloads_list.setItemWidget(item, 2, slider)

            item.setText(3, "Downloading")
            item.setText(4, "4")
            item.setText(5, "5")
            item.setText(6, "801.3 KB")
            item.setText(7, "0.4 KB")
            item.setText(8, "34:12:03")

    def on_downloads_tab_button_clicked(self, button_name):
        print button_name
