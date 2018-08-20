import logging
import os
import time

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QAbstractItemView, QAction, QFileDialog, QTreeWidgetItem

from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.defs import DOWNLOADS_FILTER_ALL, DOWNLOADS_FILTER_DOWNLOADING, DOWNLOADS_FILTER_COMPLETED, \
    DOWNLOADS_FILTER_ACTIVE, DOWNLOADS_FILTER_INACTIVE, DOWNLOADS_FILTER_CREDITMINING, DOWNLOADS_FILTER_DEFINITION, \
    DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, DLSTATUS_METADATA, \
    DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK, DLSTATUS_CIRCUITS
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.widgets.downloadwidgetitem import DownloadWidgetItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_speed, format_size
from TriblerGUI.widgets.loading_list_item import LoadingListItem


class DownloadsPage(QWidget):
    """
    This class is responsible for managing all items on the downloads page.
    The downloads page shows all downloads and specific details about a download.
    """
    received_downloads = pyqtSignal(object)

    def __init__(self):
        QWidget.__init__(self)
        self.export_dir = None
        self.filter = DOWNLOADS_FILTER_ALL
        self.download_widgets = {}  # key: infohash, value: QTreeWidgetItem
        self.downloads = None
        self.downloads_timer = QTimer()
        self.downloads_timeout_timer = QTimer()
        self.downloads_last_update = 0
        self.selected_items = None
        self.dialog = None
        self.downloads_request_mgr = TriblerRequestManager()
        self.request_mgr = None
        self.loading_message_widget = None

    def showEvent(self, QShowEvent):
        """
        When the downloads tab is clicked, we want to update the downloads list immediately.
        """
        super(DownloadsPage, self).showEvent(QShowEvent)
        self.stop_loading_downloads()
        self.schedule_downloads_timer(True)

    def initialize_downloads_page(self):
        self.window().downloads_tab.initialize()
        self.window().downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)

        self.window().start_download_button.clicked.connect(self.on_start_download_clicked)
        self.window().stop_download_button.clicked.connect(self.on_stop_download_clicked)
        self.window().remove_download_button.clicked.connect(self.on_remove_download_clicked)
        self.window().play_download_button.clicked.connect(self.on_play_download_clicked)

        self.window().downloads_list.itemSelectionChanged.connect(self.on_download_item_clicked)

        self.window().downloads_list.customContextMenuRequested.connect(self.on_right_click_item)

        self.window().download_details_widget.initialize_details_widget()
        self.window().download_details_widget.hide()

        self.window().downloads_filter_input.textChanged.connect(self.on_filter_text_changed)

        self.window().downloads_list.header().resizeSection(12, 146)

        if not self.window().vlc_available:
            self.window().play_download_button.setHidden(True)

    def tray_set_tooltip(self, message):
        """
        Set a tooltip message for the tray icon, if possible.

        :param message: the message to display on hover
        """
        if self.window().tray_icon:
            try:
                self.window().tray_icon.setToolTip(message)
            except RuntimeError as e:
                logging.error("Failed to set tray tooltip: %s", str(e))

    def tray_show_message(self, title, message):
        """
        Show a message at the tray icon, if possible.

        :param title: the title of the message
        :param message: the message to display
        """
        if self.window().tray_icon:
            try:
                self.window().tray_icon.showMessage(title, message)
            except RuntimeError as e:
                logging.error("Failed to set tray message: %s", str(e))


    def on_filter_text_changed(self, text):
        self.window().downloads_list.clearSelection()
        self.window().download_details_widget.hide()
        self.update_download_visibility()

    def start_loading_downloads(self):
        self.window().downloads_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.loading_message_widget = QTreeWidgetItem()
        self.window().downloads_list.addTopLevelItem(self.loading_message_widget)
        self.window().downloads_list.setItemWidget(self.loading_message_widget, 2,
                                                   LoadingListItem(self.window().downloads_list))
        self.schedule_downloads_timer(now=True)

    def schedule_downloads_timer(self, now=False):
        self.downloads_timer = QTimer()
        self.downloads_timer.setSingleShot(True)
        self.downloads_timer.timeout.connect(self.load_downloads)
        self.downloads_timer.start(0 if now else 1000)

        self.downloads_timeout_timer = QTimer()
        self.downloads_timeout_timer.setSingleShot(True)
        self.downloads_timeout_timer.timeout.connect(self.on_downloads_request_timeout)
        self.downloads_timeout_timer.start(16000)

    def on_downloads_request_timeout(self):
        self.downloads_request_mgr.cancel_request()
        self.schedule_downloads_timer()

    def stop_loading_downloads(self):
        self.downloads_timer.stop()
        self.downloads_timeout_timer.stop()

    def load_downloads(self):
        url = "downloads?get_pieces=1"
        if self.window().download_details_widget.currentIndex() == 3:
            url += "&get_peers=1"
        elif self.window().download_details_widget.currentIndex() == 1:
            url += "&get_files=1"

        if not self.isHidden() or (time.time() - self.downloads_last_update > 30):
            # Update if the downloads page is visible or if we haven't updated for longer than 30 seconds
            self.downloads_last_update = time.time()
            priority = "LOW" if self.isHidden() else "HIGH"
            self.downloads_request_mgr.cancel_request()
            self.downloads_request_mgr = TriblerRequestManager()
            self.downloads_request_mgr.perform_request(url, self.on_received_downloads, priority=priority)

    def on_received_downloads(self, downloads):
        if not downloads:
            return  # This might happen when closing Tribler
        loading_widget_index = self.window().downloads_list.indexOfTopLevelItem(self.loading_message_widget)
        if loading_widget_index > -1:
            self.window().downloads_list.takeTopLevelItem(loading_widget_index)
            self.window().downloads_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.downloads = downloads

        self.total_download = 0
        self.total_upload = 0

        download_infohashes = set()

        items = []
        for download in downloads["downloads"]:
            if download["infohash"] in self.download_widgets:
                item = self.download_widgets[download["infohash"]]
            else:
                item = DownloadWidgetItem()
                self.download_widgets[download["infohash"]] = item
                items.append(item)

            item.update_with_download(download)

            # Update video player with download info
            video_infohash = self.window().video_player_page.active_infohash
            if video_infohash != "" and download["infohash"] == video_infohash:
                self.window().video_player_page.update_with_download_info(download)

            self.total_download += download["speed_down"]
            self.total_upload += download["speed_up"]

            download_infohashes.add(download["infohash"])

            if self.window().download_details_widget.current_download is not None and \
                    self.window().download_details_widget.current_download["infohash"] == download["infohash"]:
                self.window().download_details_widget.current_download = download
                self.window().download_details_widget.update_pages()

        self.window().downloads_list.addTopLevelItems(items)
        for item in items:
            self.window().downloads_list.setItemWidget(item, 2, item.bar_container)

        # Check whether there are download that should be removed
        for infohash, item in self.download_widgets.items():
            if infohash not in download_infohashes:
                index = self.window().downloads_list.indexOfTopLevelItem(item)
                self.window().downloads_list.takeTopLevelItem(index)
                del self.download_widgets[infohash]

        self.tray_set_tooltip("Down: %s, Up: %s" % (format_speed(self.total_download), format_speed(self.total_upload)))
        self.update_download_visibility()
        self.schedule_downloads_timer()

        # Update the top download management button if we have a row selected
        if len(self.window().downloads_list.selectedItems()) > 0:
            self.on_download_item_clicked()

        self.update_credit_mining_disk_usage()

        self.received_downloads.emit(downloads)

    def update_download_visibility(self):
        for i in range(self.window().downloads_list.topLevelItemCount()):
            item = self.window().downloads_list.topLevelItem(i)
            filter_match = self.window().downloads_filter_input.text().lower() in item.download_info["name"].lower()
            is_creditmining = item.download_info["credit_mining"]
            if self.filter == DOWNLOADS_FILTER_CREDITMINING:
                item.setHidden(not is_creditmining or not filter_match)
            else:
                item.setHidden(not item.get_raw_download_status() in DOWNLOADS_FILTER_DEFINITION[self.filter] or \
                               not filter_match or is_creditmining)

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
        elif button_name == "downloads_creditmining_button":
            self.filter = DOWNLOADS_FILTER_CREDITMINING

        self.window().downloads_list.clearSelection()
        self.window().download_details_widget.hide()
        self.update_download_visibility()
        self.update_credit_mining_disk_usage()

    def update_credit_mining_disk_usage(self):
        on_credit_mining_tab = self.filter == DOWNLOADS_FILTER_CREDITMINING
        self.window().diskspace_usage.setVisible(on_credit_mining_tab)

        if not on_credit_mining_tab or not self.window().tribler_settings or not self.downloads:
            return

        bytes_max = self.window().tribler_settings["credit_mining"]["max_disk_space"]
        bytes_used = 0
        for download in self.downloads["downloads"]:
            if download["credit_mining"] and \
               download["status"] in ("DLSTATUS_DOWNLOADING", "DLSTATUS_SEEDING",
                                      "DLSTATUS_STOPPED", "DLSTATUS_STOPPED_ON_ERROR"):
                bytes_used += download["progress"] * download["size"]
        self.window().diskspace_usage.setText("Current disk space usage %s / %s" % (format_size(float(bytes_used)),
                                                                                    format_size(float(bytes_max))))

    @staticmethod
    def start_download_enabled(download_widgets):
        return any([download_widget.get_raw_download_status() == DLSTATUS_STOPPED
                    for download_widget in download_widgets])

    @staticmethod
    def stop_download_enabled(download_widgets):
        return any([download_widget.get_raw_download_status() not in [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]
                    for download_widget in download_widgets])

    @staticmethod
    def force_recheck_download_enabled(download_widgets):
        return any([download_widget.get_raw_download_status() not in
                    [DLSTATUS_METADATA, DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]
                    for download_widget in download_widgets])

    def on_download_item_clicked(self):
        selected_count = len(self.window().downloads_list.selectedItems())
        if selected_count == 0:
            self.window().play_download_button.setEnabled(False)
            self.window().remove_download_button.setEnabled(False)
            self.window().start_download_button.setEnabled(False)
            self.window().stop_download_button.setEnabled(False)
            self.window().download_details_widget.hide()
        elif selected_count == 1:
            self.selected_items = self.window().downloads_list.selectedItems()
            self.window().play_download_button.setEnabled(True)
            self.window().remove_download_button.setEnabled(True)
            self.window().start_download_button.setEnabled(DownloadsPage.start_download_enabled(self.selected_items))
            self.window().stop_download_button.setEnabled(DownloadsPage.stop_download_enabled(self.selected_items))

            self.window().download_details_widget.update_with_download(self.selected_items[0].download_info)
            self.window().download_details_widget.show()
        else:
            self.selected_items = self.window().downloads_list.selectedItems()
            self.window().play_download_button.setEnabled(False)
            self.window().remove_download_button.setEnabled(True)
            self.window().start_download_button.setEnabled(DownloadsPage.start_download_enabled(self.selected_items))
            self.window().stop_download_button.setEnabled(DownloadsPage.stop_download_enabled(self.selected_items))
            self.window().download_details_widget.hide()

    def on_start_download_clicked(self):
        for selected_item in self.selected_items:
            infohash = selected_item.download_info["infohash"]
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads/%s" % infohash, self.on_download_resumed,
                                             method='PATCH', data="state=resume")

    def on_download_resumed(self, json_result):
        if json_result and 'modified' in json_result:
            for selected_item in self.selected_items:
                if selected_item.download_info["infohash"] == json_result["infohash"]:
                    selected_item.download_info['status'] = "DLSTATUS_DOWNLOADING"
                    selected_item.update_item()
                    self.on_download_item_clicked()

    def on_stop_download_clicked(self):
        for selected_item in self.selected_items:
            infohash = selected_item.download_info["infohash"]
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads/%s" % infohash, self.on_download_stopped,
                                             method='PATCH', data="state=stop")

    def on_play_download_clicked(self):
        self.window().left_menu_button_video_player.click()
        selected_item = self.selected_items[:1]
        if selected_item and \
           self.window().video_player_page.active_infohash != selected_item[0].download_info["infohash"]:
            self.window().video_player_page.play_media_item(selected_item[0].download_info["infohash"], -1)

    def on_download_stopped(self, json_result):
        if json_result and "modified" in json_result:
            for selected_item in self.selected_items:
                if selected_item.download_info["infohash"] == json_result["infohash"]:
                    selected_item.download_info['status'] = "DLSTATUS_STOPPED"
                    selected_item.update_item()
                    self.on_download_item_clicked()

    def on_remove_download_clicked(self):
        self.dialog = ConfirmationDialog(self, "Remove download", "Are you sure you want to remove this download?",
                                         [('remove download', BUTTON_TYPE_NORMAL),
                                          ('remove download + data', BUTTON_TYPE_NORMAL),
                                          ('cancel', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_remove_download_dialog)
        self.dialog.show()

    def on_remove_download_dialog(self, action):
        if action != 2:
            for selected_item in self.selected_items:
                infohash = selected_item.download_info["infohash"]

                # Reset video player if necessary before doing the actual request
                if self.window().video_player_page.active_infohash == infohash:
                    self.window().video_player_page.reset_player()

                self.request_mgr = TriblerRequestManager()
                self.request_mgr.perform_request("downloads/%s" % infohash, self.on_download_removed,
                                                 method='DELETE', data="remove_data=%d" % action)

        self.dialog.close_dialog()
        self.dialog = None

    def on_download_removed(self, json_result):
        if json_result and "removed" in json_result:
            self.load_downloads()
            self.window().download_details_widget.hide()

    def on_force_recheck_download(self):
        for selected_item in self.selected_items:
            infohash = selected_item.download_info["infohash"]
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads/%s" % infohash, self.on_forced_recheck,
                                             method='PATCH', data='state=recheck')

    def on_forced_recheck(self, result):
        if result and "modified" in result:
            for selected_item in self.selected_items:
                if selected_item.download_info["infohash"] == result["infohash"]:
                    selected_item.download_info['status'] = "DLSTATUS_HASHCHECKING"
                    selected_item.update_item()
                    self.on_download_item_clicked()

    def change_anonymity(self, hops):
        for selected_item in self.selected_items:
            infohash = selected_item.download_info["infohash"]
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads/%s" % infohash, lambda _: None,
                                             method='PATCH', data='anon_hops=%d' % hops)

    def on_explore_files(self):
        for selected_item in self.selected_items:
            path = os.path.normpath(os.path.join(self.window().tribler_settings['download_defaults']['saveas'],
                                                 selected_item.download_info["destination"]))
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_export_download(self):
        self.export_dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory", "",
                                                           QFileDialog.ShowDirsOnly)

        selected_item = self.selected_items[:1]
        if len(self.export_dir) > 0 and selected_item:
            # Show confirmation dialog where we specify the name of the file
            torrent_name = selected_item[0].download_info['name']
            self.dialog = ConfirmationDialog(self, "Export torrent file",
                                             "Please enter the name of the torrent file:",
                                             [('SAVE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                             show_input=True)
            self.dialog.dialog_widget.dialog_input.setPlaceholderText('Torrent file name')
            self.dialog.dialog_widget.dialog_input.setText("%s.torrent" % torrent_name)
            self.dialog.dialog_widget.dialog_input.setFocus()
            self.dialog.button_clicked.connect(self.on_export_download_dialog_done)
            self.dialog.show()

    def on_export_download_dialog_done(self, action):
        selected_item = self.selected_items[:1]
        if action == 0 and selected_item:
            filename = self.dialog.dialog_widget.dialog_input.text()
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.download_file("downloads/%s/torrent" % selected_item[0].download_info['infohash'],
                                           lambda data: self.on_export_download_request_done(filename, data))

        self.dialog.close_dialog()
        self.dialog = None

    def on_export_download_request_done(self, filename, data):
        dest_path = os.path.join(self.export_dir, filename)
        try:
            torrent_file = open(dest_path, "wb")
            torrent_file.write(data)
            torrent_file.close()
        except IOError as exc:
            ConfirmationDialog.show_error(self.window(),
                                          "Error when exporting file",
                                          "An error occurred when exporting the torrent file: %s" % str(exc))
        else:
            self.tray_show_message("Torrent file exported", "Torrent file exported to %s" % dest_path)

    def on_right_click_item(self, pos):
        item_clicked = self.window().downloads_list.itemAt(pos)
        if not item_clicked or self.selected_items is None:
            return

        if item_clicked not in self.selected_items:
            self.selected_items.append(item_clicked)

        menu = TriblerActionMenu(self)

        start_action = QAction('Start', self)
        stop_action = QAction('Stop', self)
        remove_download_action = QAction('Remove download', self)
        force_recheck_action = QAction('Force recheck', self)
        export_download_action = QAction('Export .torrent file', self)
        explore_files_action = QAction('Explore files', self)

        no_anon_action = QAction('No anonymity', self)
        one_hop_anon_action = QAction('One hop', self)
        two_hop_anon_action = QAction('Two hops', self)
        three_hop_anon_action = QAction('Three hops', self)

        start_action.triggered.connect(self.on_start_download_clicked)
        start_action.setEnabled(DownloadsPage.start_download_enabled(self.selected_items))
        stop_action.triggered.connect(self.on_stop_download_clicked)
        stop_action.setEnabled(DownloadsPage.stop_download_enabled(self.selected_items))
        remove_download_action.triggered.connect(self.on_remove_download_clicked)
        force_recheck_action.triggered.connect(self.on_force_recheck_download)
        force_recheck_action.setEnabled(DownloadsPage.force_recheck_download_enabled(self.selected_items))
        export_download_action.triggered.connect(self.on_export_download)
        explore_files_action.triggered.connect(self.on_explore_files)

        no_anon_action.triggered.connect(lambda: self.change_anonymity(0))
        one_hop_anon_action.triggered.connect(lambda: self.change_anonymity(1))
        two_hop_anon_action.triggered.connect(lambda: self.change_anonymity(2))
        three_hop_anon_action.triggered.connect(lambda: self.change_anonymity(3))

        menu.addAction(start_action)
        menu.addAction(stop_action)

        if self.window().vlc_available and len(self.selected_items) == 1:
            play_action = QAction('Play', self)
            play_action.triggered.connect(self.on_play_download_clicked)
            menu.addAction(play_action)
        menu.addSeparator()
        menu.addAction(remove_download_action)
        menu.addSeparator()
        menu.addAction(force_recheck_action)
        menu.addSeparator()

        exclude_states = [DLSTATUS_METADATA, DLSTATUS_CIRCUITS, DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]
        if len(self.selected_items) == 1 and self.selected_items[0].get_raw_download_status() not in exclude_states:
            menu.addAction(export_download_action)
            menu.addSeparator()
        menu_anon_level = menu.addMenu("Change anonymity")
        menu_anon_level.addAction(no_anon_action)
        menu_anon_level.addAction(one_hop_anon_action)
        menu_anon_level.addAction(two_hop_anon_action)
        menu_anon_level.addAction(three_hop_anon_action)
        menu.addAction(explore_files_action)

        menu.exec_(self.window().downloads_list.mapToGlobal(pos))
