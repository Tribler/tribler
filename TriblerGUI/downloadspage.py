from PyQt5.QtWidgets import QWidget, QTreeWidget
from TriblerGUI.defs import DOWNLOADS_FILTER_ALL, DOWNLOADS_FILTER_DOWNLOADING, DOWNLOADS_FILTER_COMPLETED, \
    DOWNLOADS_FILTER_ACTIVE, DOWNLOADS_FILTER_INACTIVE, DOWNLOADS_FILTER_DEFINITION
from TriblerGUI.downloadwidgetitem import DownloadWidgetItem


class DownloadsPage(QWidget):

    def initialize_downloads_page(self):
        self.downloads_tab = self.findChild(QWidget, "downloads_tab")
        self.downloads_tab.initialize()
        self.downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)
        self.download_widgets = {} # key: infohash, value: QTreeWidgetItem
        self.filter = DOWNLOADS_FILTER_ALL

        self.downloads_list = self.findChild(QTreeWidget, "downloads_list")

    def received_download_status(self, downloads):
        for download in downloads:
            if download["infohash"] in self.download_widgets:
                item = self.download_widgets[download["infohash"]]
            else:
                item = DownloadWidgetItem(self.downloads_list)
                self.download_widgets[download["infohash"]] = item
            item.updateWithDownload(download)

        self.update_download_visibility()

    def update_download_visibility(self):
        for i in range(self.downloads_list.topLevelItemCount()):
            item = self.downloads_list.topLevelItem(i)
            item.setHidden(not item.download_status_raw in DOWNLOADS_FILTER_DEFINITION[self.filter])

    def on_downloads_tab_button_clicked(self, button_name):
        if button_name == "downloads_all_button":
            self.filter = DOWNLOADS_FILTER_ALL
        elif button_name == "downloads_downloading_button":
            self.filter = DOWNLOADS_FILTER_DOWNLOADING
        elif button_name == "downloads_completed_button":
            self.filter = DOWNLOADS_FILTER_COMPLETED
        elif button_name == "downloads_active_button":
            self.filter = DOWNLOADS_FILTER_ACTIVE
        elif button_name == "downloads_inactive_button":
            self.filter = DOWNLOADS_FILTER_INACTIVE

        self.update_download_visibility()
