from PyQt5.QtWidgets import QWidget
from TriblerGUI.defs import DOWNLOADS_FILTER_ALL, DOWNLOADS_FILTER_DOWNLOADING, DOWNLOADS_FILTER_COMPLETED, \
    DOWNLOADS_FILTER_ACTIVE, DOWNLOADS_FILTER_INACTIVE, DOWNLOADS_FILTER_DEFINITION, DLSTATUS_STOPPED, \
    DLSTATUS_STOPPED_ON_ERROR
from TriblerGUI.downloadwidgetitem import DownloadWidgetItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class DownloadsPage(QWidget):
    """
    This class is responsible for managing all items on the downloads page.
    The downloads page shows all downloads and specific details about a download.
    """

    def initialize_downloads_page(self):
        self.window().downloads_tab.initialize()
        self.window().downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)
        self.download_widgets = {} # key: infohash, value: QTreeWidgetItem
        self.filter = DOWNLOADS_FILTER_ALL

        self.window().start_download_button.clicked.connect(self.on_start_download_clicked)
        self.window().stop_download_button.clicked.connect(self.on_stop_download_clicked)
        self.window().remove_download_button.clicked.connect(self.on_remove_download_clicked)

        self.window().downloads_list.itemSelectionChanged.connect(self.on_download_item_clicked)

    def load_downloads(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads", self.received_downloads)

    def received_downloads(self, downloads):
        for download in downloads["downloads"]:
            if download["infohash"] in self.download_widgets:
                item = self.download_widgets[download["infohash"]]
            else:
                item = DownloadWidgetItem(self.window().downloads_list)
                self.download_widgets[download["infohash"]] = item
            item.updateWithDownload(download)

        self.update_download_visibility()

    def update_download_visibility(self):
        for i in range(self.window().downloads_list.topLevelItemCount()):
            item = self.window().downloads_list.topLevelItem(i)
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

    def on_download_item_clicked(self):
        item = self.window().downloads_list.selectedItems()[0]
        status = item.download_status_raw
        self.window().start_download_button.setEnabled(status == DLSTATUS_STOPPED)
        self.window().stop_download_button.setEnabled(status != DLSTATUS_STOPPED and status != DLSTATUS_STOPPED_ON_ERROR)
        self.window().remove_download_button.setEnabled(True)

    def on_start_download_clicked(self):
        pass

    def on_stop_download_clicked(self):
        pass

    def on_remove_download_clicked(self):
        pass
