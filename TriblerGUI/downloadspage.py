import os
from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QCursor, QDesktopServices
from PyQt5.QtWidgets import QWidget, QMenu, QAction, QFileDialog, QSystemTrayIcon
from TriblerGUI.TriblerActionMenu import TriblerActionMenu
from TriblerGUI.defs import DOWNLOADS_FILTER_ALL, DOWNLOADS_FILTER_DOWNLOADING, DOWNLOADS_FILTER_COMPLETED, \
    DOWNLOADS_FILTER_ACTIVE, DOWNLOADS_FILTER_INACTIVE, DOWNLOADS_FILTER_DEFINITION, DLSTATUS_STOPPED, \
    DLSTATUS_STOPPED_ON_ERROR, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, DLSTATUS_METADATA, DLSTATUS_HASHCHECKING, \
    DLSTATUS_WAITING4HASHCHECK
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.downloadwidgetitem import DownloadWidgetItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_speed


class DownloadsPage(QWidget):
    """
    This class is responsible for managing all items on the downloads page.
    The downloads page shows all downloads and specific details about a download.
    """
    received_downloads = pyqtSignal(object)

    def initialize_downloads_page(self):
        self.window().downloads_tab.initialize()
        self.window().downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)
        self.download_widgets = {} # key: infohash, value: QTreeWidgetItem
        self.filter = DOWNLOADS_FILTER_ALL

        self.window().start_download_button.clicked.connect(self.on_start_download_clicked)
        self.window().stop_download_button.clicked.connect(self.on_stop_download_clicked)
        self.window().remove_download_button.clicked.connect(self.on_remove_download_clicked)

        self.window().downloads_list.itemSelectionChanged.connect(self.on_download_item_clicked)

        self.window().downloads_list.customContextMenuRequested.connect(self.on_right_click_item)

        self.downloads = None
        self.can_update_items = True
        self.downloads_timer = QTimer()

    def start_loading_downloads(self):
        self.load_downloads()
        self.downloads_timer = QTimer()
        self.downloads_timer.timeout.connect(self.load_downloads)
        self.downloads_timer.start(1000)

    def stop_loading_downloads(self):
        self.downloads_timer.stop()

    def load_downloads(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads", self.on_received_downloads)

    def on_received_downloads(self, downloads):
        total_download = 0
        total_upload = 0
        self.received_downloads.emit(downloads)
        self.downloads = downloads

        download_infohashes = set()
        for download in downloads["downloads"]:
            if download["infohash"] in self.download_widgets:
                item = self.download_widgets[download["infohash"]]
            else:
                item = DownloadWidgetItem(self.window().downloads_list)
                self.download_widgets[download["infohash"]] = item

            if self.can_update_items:
                item.updateWithDownload(download)

            # Update video player with download info
            video_infohash = self.window().video_player_page.active_infohash
            if video_infohash != "" and download["infohash"] == video_infohash:
                self.window().video_player_page.update_with_download_info(download)

            total_download += download["speed_down"]
            total_upload += download["speed_up"]

            download_infohashes.add(download["infohash"])

        # Check whether there are download that should be removed
        toremove = set()
        for infohash, item in self.download_widgets.iteritems():
            if infohash not in download_infohashes:
                index = self.window().downloads_list.indexOfTopLevelItem(item)
                toremove.add((infohash, index))

        for infohash, index in toremove:
            self.window().downloads_list.takeTopLevelItem(index)
            del self.download_widgets[infohash]

        self.window().statusBar.set_speeds(total_download, total_upload)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.window().tray_icon.setToolTip(
                "Down: %s, Up: %s" % (format_speed(total_download), format_speed(total_upload)))
        self.update_download_visibility()

    def update_download_visibility(self):
        for i in range(self.window().downloads_list.topLevelItemCount()):
            item = self.window().downloads_list.topLevelItem(i)
            item.setHidden(not item.getRawDownloadStatus() in DOWNLOADS_FILTER_DEFINITION[self.filter])

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

    def start_download_enabled(self, download_widget):
        return download_widget.getRawDownloadStatus() == DLSTATUS_STOPPED

    def stop_download_enabled(self, download_widget):
        status = download_widget.getRawDownloadStatus()
        return status != DLSTATUS_STOPPED and status != DLSTATUS_STOPPED_ON_ERROR

    def force_recheck_download_enabled(self, download_widget):
        status = download_widget.getRawDownloadStatus()
        return status != DLSTATUS_METADATA and status != DLSTATUS_HASHCHECKING and status != DLSTATUS_WAITING4HASHCHECK

    def on_download_item_clicked(self):
        self.selected_item = self.window().downloads_list.selectedItems()[0]
        self.window().remove_download_button.setEnabled(True)
        self.window().start_download_button.setEnabled(self.start_download_enabled(self.selected_item))
        self.window().stop_download_button.setEnabled(self.stop_download_enabled(self.selected_item))

        self.window().download_details_widget.update_with_download(self.selected_item.download_info)

    def on_start_download_clicked(self):
        infohash = self.selected_item.download_info["infohash"]
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s/resume" % infohash, self.on_download_resumed, method='POST')

    def on_download_resumed(self, json_result):
        if json_result["resumed"]:
            self.selected_item.download_info['status'] = "DLSTATUS_DOWNLOADING"
            self.selected_item.updateItem()
            self.on_download_item_clicked()

    def on_stop_download_clicked(self):
        infohash = self.selected_item.download_info["infohash"]
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s/stop" % infohash, self.on_download_stopped, method='POST')

    def on_download_stopped(self, json_result):
        if json_result["stopped"]:
            self.selected_item.download_info['status'] = "DLSTATUS_STOPPED"
            self.selected_item.updateItem()
            self.on_download_item_clicked()

    def on_remove_download_clicked(self):
        self.dialog = ConfirmationDialog(self, "Remove download", "Are you sure you want to remove this download?", [('remove download', BUTTON_TYPE_NORMAL), ('remove download + data', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_remove_download_dialog)
        self.dialog.show()

    def on_remove_download_dialog(self, action):
        if action != 2:
            infohash = self.selected_item.download_info["infohash"]
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads/%s/remove?remove_data=%d" % (infohash, action == 1), self.on_download_removed, method='DELETE')

        self.dialog.setParent(None)
        self.dialog = None

    def on_download_removed(self, json_result):
        if json_result["removed"]:
            infohash = self.selected_item.download_info["infohash"]
            index = self.window().downloads_list.indexOfTopLevelItem(self.selected_item)
            self.window().downloads_list.takeTopLevelItem(index)
            del self.download_widgets[infohash]

    def on_force_recheck_download(self):
        infohash = self.selected_item.download_info["infohash"]
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s/forcerecheck" % infohash, self.on_forced_recheck, method='POST')

    def on_forced_recheck(self, result):
        if result['forced_recheck']:
            self.selected_item.download_info['status'] = "DLSTATUS_HASHCHECKING"
            self.selected_item.updateItem()
            self.on_download_item_clicked()

    def on_explore_files(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.selected_item.download_info["destination"]))

    def on_export_download(self):
        self.export_dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory", "",
                                               QFileDialog.ShowDirsOnly)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.download_file("downloads/%s/torrent" % self.selected_item.download_info['infohash'],
                                       self.on_export_download_request_done)

    def on_export_download_request_done(self, filename, data):
        dest_path = os.path.join(self.export_dir, filename)
        with open(dest_path, "wb") as torrent_file:
            torrent_file.write(data)

        self.window().tray_icon.showMessage("Torrent file exported", "Torrent file exported to %s" % dest_path)

    def on_right_click_item(self, pos):
        self.selected_item = self.window().downloads_list.selectedItems()[0]

        menu = TriblerActionMenu(self)

        startAction = QAction('Start', self)
        stopAction = QAction('Stop', self)
        removeDownloadAction = QAction('Remove download', self)
        removeDownloadDataAction = QAction('Remove download + data', self)
        forceRecheckAction = QAction('Force recheck', self)
        exportDownloadAction = QAction('Export .torrent file', self)
        exploreFilesAction = QAction('Explore files', self)

        startAction.triggered.connect(self.on_start_download_clicked)
        startAction.setEnabled(self.start_download_enabled(self.selected_item))
        stopAction.triggered.connect(self.on_stop_download_clicked)
        stopAction.setEnabled(self.stop_download_enabled(self.selected_item))
        removeDownloadAction.triggered.connect(lambda: self.on_remove_download_dialog(0))
        removeDownloadDataAction.triggered.connect(lambda: self.on_remove_download_dialog(1))
        forceRecheckAction.triggered.connect(self.on_force_recheck_download)
        forceRecheckAction.setEnabled(self.force_recheck_download_enabled(self.selected_item))
        exportDownloadAction.triggered.connect(self.on_export_download)
        exploreFilesAction.triggered.connect(self.on_explore_files)

        menu.addAction(startAction)
        menu.addAction(stopAction)
        menu.addSeparator()
        menu.addAction(removeDownloadAction)
        menu.addAction(removeDownloadDataAction)
        menu.addSeparator()
        menu.addAction(forceRecheckAction)
        menu.addSeparator()
        menu.addAction(exportDownloadAction)
        menu.addSeparator()
        menu.addAction(exploreFilesAction)

        menu.exec_(self.window().downloads_list.mapToGlobal(pos))
