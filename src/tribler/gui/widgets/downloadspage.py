import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QAbstractItemView, QAction, QFileDialog, QWidget

from tribler.core.sentry_reporter.sentry_tools import get_first_item
from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.gui.defs import (
    BUTTON_TYPE_CONFIRM,
    BUTTON_TYPE_NORMAL,
    DOWNLOADS_FILTER_ACTIVE,
    DOWNLOADS_FILTER_ALL,
    DOWNLOADS_FILTER_CHANNELS,
    DOWNLOADS_FILTER_COMPLETED,
    DOWNLOADS_FILTER_DEFINITION,
    DOWNLOADS_FILTER_DOWNLOADING,
    DOWNLOADS_FILTER_INACTIVE, )
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.network.request import REQUEST_ID
from tribler.gui.network.request_manager import request_manager
from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.tribler_action_menu import TriblerActionMenu
from tribler.gui.utilities import connect, format_speed, tr
from tribler.gui.widgets.downloadsdetailstabwidget import DownloadDetailsTabs
from tribler.gui.widgets.downloadwidgetitem import DownloadWidgetItem, LoadingDownloadWidgetItem
from tribler.gui.widgets.loading_list_item import LoadingListItem

REFRESH_DOWNLOADS_SOON_INTERVAL_MSEC = 10  # 0.01s
REFRESH_DOWNLOADS_UI_CHANGE_INTERVAL_MSEC = 2000  # 2s
REFRESH_DOWNLOADS_BACKGROUND_INTERVAL_MSEC = 5000  # 5s

button_name2filter = {
    "downloads_all_button": DOWNLOADS_FILTER_ALL,
    "downloads_downloading_button": DOWNLOADS_FILTER_DOWNLOADING,
    "downloads_completed_button": DOWNLOADS_FILTER_COMPLETED,
    "downloads_active_button": DOWNLOADS_FILTER_ACTIVE,
    "downloads_inactive_button": DOWNLOADS_FILTER_INACTIVE,
    "downloads_channels_button": DOWNLOADS_FILTER_CHANNELS,
}


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class DownloadsPage(AddBreadcrumbOnShowMixin, QWidget):
    """
    This class is responsible for managing all items on the downloads page.
    The downloads page shows all downloads and specific details about a download.
    """

    received_downloads = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.export_dir = None
        self.filter = DOWNLOADS_FILTER_ALL
        self.download_widgets: Dict = {}  # key: infohash, value: QTreeWidgetItem
        self.background_refresh_downloads_timer = QTimer()
        self.downloads_last_update = 0
        self.selected_items: List[DownloadWidgetItem] = []
        self.dialog = None
        self.loading_message_widget: Optional[LoadingDownloadWidgetItem] = None
        self.loading_list_item: Optional[LoadingListItem] = None
        self.total_download_speed = 0
        self.total_upload_speed = 0

        # Used to keep track of the last processed request with a purpose of ignoring old requests
        self.last_processed_request_id = 0

    def showEvent(self, QShowEvent):
        """
        When the downloads tab is clicked, we want to update the downloads list immediately.
        """
        super().showEvent(QShowEvent)
        self.schedule_downloads_refresh(REFRESH_DOWNLOADS_SOON_INTERVAL_MSEC)

    def hideEvent(self, QHideEvent):
        super().hideEvent(QHideEvent)
        self.stop_refreshing_downloads()

    def initialize_downloads_page(self):
        self.window().downloads_tab.initialize()
        connect(self.window().downloads_tab.clicked_tab_button, self.on_downloads_tab_button_clicked)

        connect(self.window().start_download_button.clicked, self.on_start_download_clicked)
        connect(self.window().stop_download_button.clicked, self.on_stop_download_clicked)
        connect(self.window().remove_download_button.clicked, self.on_remove_download_clicked)

        connect(self.window().downloads_list.itemSelectionChanged, self.on_selection_change)

        connect(self.window().downloads_list.customContextMenuRequested, self.on_right_click_item)

        self.window().download_details_widget.initialize_details_widget()
        self.window().download_details_widget.hide()

        connect(self.window().downloads_filter_input.textChanged, self.on_filter_text_changed)

        self.window().downloads_list.header().setSortIndicator(12, Qt.AscendingOrder)
        self.window().downloads_list.header().resizeSection(12, 146)

        self.background_refresh_downloads_timer.setSingleShot(True)
        connect(self.background_refresh_downloads_timer.timeout, self.on_background_refresh_downloads_timer)

    def on_filter_text_changed(self, text):
        self.window().downloads_list.clearSelection()
        self.window().download_details_widget.hide()
        self.update_download_visibility()

    def start_loading_downloads(self):
        self.window().downloads_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.loading_message_widget = LoadingDownloadWidgetItem()
        self.loading_list_item = LoadingListItem(self.window().downloads_list)
        self.window().downloads_list.addTopLevelItem(self.loading_message_widget)
        self.window().downloads_list.setItemWidget(self.loading_message_widget, 2, self.loading_list_item)

    def schedule_downloads_refresh(self, interval_msec=REFRESH_DOWNLOADS_BACKGROUND_INTERVAL_MSEC):
        timer = self.background_refresh_downloads_timer
        remaining = timer.remainingTime()
        if timer.isActive():
            interval_msec = min(remaining, interval_msec)
        timer.start(interval_msec)

    def on_background_refresh_downloads_timer(self):
        self.refresh_non_selected_downloads()
        self.refresh_selected_download()
        self.schedule_downloads_refresh()

    def stop_refreshing_downloads(self):
        self.background_refresh_downloads_timer.stop()

    def refresh_selected_download(self):
        details_widget = self.window().download_details_widget
        index = details_widget.currentIndex()

        details_shown = not details_widget.isHidden()
        selected_download = details_widget.current_download

        if not details_shown or selected_download is None:
            return

        infohash = selected_download.get('infohash')
        if not infohash:
            return

        request_manager.get(
            endpoint="downloads",
            url_params={
                'get_pieces': 1,
                'get_peers': int(index == DownloadDetailsTabs.PEERS),
                'get_availability': 1,
                'infohash': infohash
            },
            on_success=self.on_received_selected_download,
        )

        files_list = details_widget.window().download_files_list
        if index != DownloadDetailsTabs.FILES or files_list.pages[0].loaded:
            return

        request_manager.get(
            endpoint=f"downloads/{infohash}/files",
            url_params={
                'view_start_path': Path("."),
                'view_size': files_list.page_size
            },
            on_success=files_list.fill_entries,
        )

    def refresh_non_selected_downloads(self):
        url_params = {}

        details_widget = self.window().download_details_widget
        details_shown = not details_widget.isHidden()
        selected_download = details_widget.current_download
        if details_shown and selected_download:
            if infohash := selected_download.get('infohash'):
                url_params['excluded'] = infohash

        request_manager.get(
            endpoint="downloads",
            url_params=url_params,
            on_success=self.on_received_non_selected_downloads,
        )

    def on_received_selected_download(self, result):
        """ Process the result of the refresh request for the selected download."""

        if not result:
            return
        downloads = result.get("downloads")
        if not downloads or len(downloads) != 1:
            self._logger.warning(
                f'Received unexpected number of downloads ({len(downloads)} instead of 1), ignoring the result.'
            )
            return

        download = downloads[0]
        if download["infohash"] not in self.download_widgets:
            self._logger.warning('Received infohash not in download_widgets, ignoring the result.')
            return

        self.process_refresh_result(result)

    def on_received_non_selected_downloads(self, result):
        """ Process the result of the refresh request for the non-selected downloads."""

        if not result or "downloads" not in result:
            self._logger.warning('Received unexpected result, ignoring it.')
            return  # This might happen when closing Tribler

        request_id = result[REQUEST_ID]
        if self.last_processed_request_id >= request_id:
            # This is an old request, ignore it.
            # It could happen because some of requests processed a bit longer than others
            msg = f'Ignoring old request {request_id} (last processed request id: {self.last_processed_request_id})'
            self._logger.warning(msg)
            return
        self.last_processed_request_id = request_id

        self.process_refresh_result(result)

    def process_refresh_result(self, result):
        """ Process the result of the refresh request.

        The result could consists of multiple downloads.
        Only downloads from the result will be processed.
        """
        checkpoints = result.get('checkpoints', {})
        if checkpoints and self.loading_message_widget:
            # If not all checkpoints are loaded, display the number of the loaded checkpoints
            total = checkpoints['total']
            loaded = checkpoints['loaded']
            if not checkpoints['all_loaded']:
                # The column is too narrow for a long message, probably we should redesign this UI element later
                message = f'{loaded}/{total} checkpoints'
                self._logger.info(f'Loading checkpoints: {message}')
                self.loading_list_item.textlabel.setText(message)
                self.schedule_downloads_refresh()
                return

        loading_widget_index = self.window().downloads_list.indexOfTopLevelItem(self.loading_message_widget)
        if loading_widget_index > -1:
            self.window().downloads_list.takeTopLevelItem(loading_widget_index)
            self.window().downloads_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.total_download_speed = 0
        self.total_upload_speed = 0

        infohash_set = set()
        items = []
        for download in result["downloads"]:
            infohash = download["infohash"]
            self.window().core_manager.events_manager.node_info_updated.emit(
                {"infohash": infohash, "progress": download["progress"]}
            )

            if infohash in self.download_widgets:
                item = self.download_widgets[infohash]
            else:
                item = DownloadWidgetItem()
                self.download_widgets[infohash] = item
                items.append(item)

            item.update_with_download(download)

            self.total_download_speed += download["speed_down"]
            self.total_upload_speed += download["speed_up"]

            infohash_set.add(infohash)

            current_download = self.window().download_details_widget.current_download
            if current_download and current_download["infohash"] == infohash:
                self.window().download_details_widget.update_with_download(download)

        self.window().downloads_list.addTopLevelItems(items)
        for item in items:
            self.window().downloads_list.setItemWidget(item, 2, item.bar_container)

        self.window().tray_set_tooltip(
            f"Down: {format_speed(self.total_download_speed)}, Up: {format_speed(self.total_upload_speed)}"
        )
        self.update_download_visibility()
        self.refresh_top_panel()

        self.received_downloads.emit(result)

    def update_download_visibility(self):
        for i in range(self.window().downloads_list.topLevelItemCount()):
            item = self.window().downloads_list.topLevelItem(i)
            if not isinstance(item, DownloadWidgetItem):
                continue

            filter_match = self.window().downloads_filter_input.text().lower() in item.download_info["name"].lower()
            filtered = DOWNLOADS_FILTER_DEFINITION[self.filter]
            hide = item.get_status() not in filtered or not filter_match
            item.setHidden(hide)

    def on_downloads_tab_button_clicked(self, button_name):
        self.filter = button_name2filter[button_name]

        self.window().downloads_list.clearSelection()
        self.window().download_details_widget.hide()
        self.update_download_visibility()

    @staticmethod
    def start_download_enabled(download_widgets):
        return any(dw.get_status() == DownloadStatus.STOPPED for dw in download_widgets)

    @staticmethod
    def stop_download_enabled(download_widgets):
        stopped = {DownloadStatus.STOPPED, DownloadStatus.STOPPED_ON_ERROR}
        return any(dw.get_status() not in stopped for dw in download_widgets)

    @staticmethod
    def force_recheck_download_enabled(download_widgets):
        recheck = {DownloadStatus.METADATA, DownloadStatus.HASHCHECKING, DownloadStatus.WAITING_FOR_HASHCHECK}
        return any(dw.get_status() not in recheck for dw in download_widgets)

    def on_selection_change(self):
        self.selected_items = self.window().downloads_list.selectedItems()

        # refresh bottom detailed info panel
        if len(self.selected_items) == 1:
            self.window().download_details_widget.update_with_download(self.selected_items[0].download_info)
            self.window().download_details_widget.show()
            self.refresh_selected_download()
        else:
            self.window().download_details_widget.hide()

        self.refresh_top_panel()

    def refresh_top_panel(self):
        if len(self.selected_items) == 0:
            self.window().remove_download_button.setEnabled(False)
            self.window().start_download_button.setEnabled(False)
            self.window().stop_download_button.setEnabled(False)
            return

        self.window().remove_download_button.setEnabled(True)
        self.window().start_download_button.setEnabled(DownloadsPage.start_download_enabled(self.selected_items))
        self.window().stop_download_button.setEnabled(DownloadsPage.stop_download_enabled(self.selected_items))

    def on_start_download_clicked(self, checked):
        for item in self.selected_items:
            request_manager.patch(
                f"downloads/{item.infohash}",
                on_success=self.on_download_resumed,
                data={"state": "resume"}
            )

    def find_item_in_selected(self, infohash) -> Optional[DownloadWidgetItem]:
        return next((it for it in self.selected_items if it.infohash == infohash), None)

    def on_download_resumed(self, json_result):
        if not json_result or 'modified' not in json_result:
            return

        self.schedule_downloads_refresh(REFRESH_DOWNLOADS_UI_CHANGE_INTERVAL_MSEC)

        if item := self.find_item_in_selected(json_result["infohash"]):
            item.update_item()

    def on_stop_download_clicked(self, checked):
        for item in self.selected_items:
            request_manager.patch(
                f"downloads/{item.infohash}",
                on_success=self.on_download_stopped,
                data={"state": "stop"}
            )

    def on_download_stopped(self, json_result):
        if not json_result or "modified" not in json_result:
            return

        self.schedule_downloads_refresh(REFRESH_DOWNLOADS_UI_CHANGE_INTERVAL_MSEC)

        if item := self.find_item_in_selected(json_result["infohash"]):
            item.update_item()

    def on_remove_download_clicked(self, checked):
        self.dialog = ConfirmationDialog(
            self,
            tr("Remove download"),
            tr("Are you sure you want to remove this download?"),
            [
                (tr("remove download"), BUTTON_TYPE_NORMAL),
                (tr("remove download + data"), BUTTON_TYPE_NORMAL),
                (tr("cancel"), BUTTON_TYPE_CONFIRM),
            ],
        )
        connect(self.dialog.button_clicked, self.on_remove_download_dialog)
        self.dialog.show()

    def on_remove_download_dialog(self, action):
        if action != 2:
            for item in self.selected_items:
                current_download = self.window().download_details_widget.current_download
                if current_download and current_download.get('infohash') == item.infohash:
                    self.window().download_details_widget.current_download = None

                request_manager.delete(
                    f"downloads/{item.infohash}",
                    on_success=self.on_download_removed,
                    data={"remove_data": bool(action)}
                )

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

    def on_download_removed(self, json_result):
        if not json_result or "removed" not in json_result:
            return

        infohash = json_result["infohash"]

        if current_download := self.window().download_details_widget.current_download:
            if current_download["infohash"] == infohash:
                self.window().download_details_widget.hide()

        if item := self.download_widgets.get(infohash):
            index = self.window().downloads_list.indexOfTopLevelItem(item)
            self.window().downloads_list.takeTopLevelItem(index)
            del self.download_widgets[infohash]

        self.window().core_manager.events_manager.node_info_updated.emit({"infohash": infohash, "progress": None})

    def on_force_recheck_download(self, checked):
        for item in self.selected_items:
            request_manager.patch(
                f"downloads/{item.infohash}",
                on_success=self.on_forced_recheck,
                data={"state": "recheck"}
            )

    def on_forced_recheck(self, result):
        if not result or "modified" not in result:
            return

        self.schedule_downloads_refresh(REFRESH_DOWNLOADS_UI_CHANGE_INTERVAL_MSEC)

        if item := self.find_item_in_selected(result["infohash"]):
            item.update_item()

    def on_change_anonymity(self, result):
        pass

    def change_anonymity(self, hops):
        for item in self.selected_items:
            request_manager.patch(
                f"downloads/{item.infohash}",
                on_success=self.on_change_anonymity,
                data={"anon_hops": hops}
            )

    def on_explore_files(self, checked):
        # ACHTUNG! To whomever might stumble upon here intending to debug the case
        # when this does not work on Linux: know, my friend, that for some mysterious reason
        # (probably related to Snap disk access rights peculiarities), this DOES NOT work
        # when you run Tribler from PyCharm. However, it works perfectly fine when you
        # run Tribler directly from system console, etc. So, don't spend your time on debugging this,
        # like I did.
        for selected_item in self.selected_items:
            path = os.path.normpath(selected_item.download_info["destination"])
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_move_files(self, checked):
        if len(self.selected_items) != 1:
            return

        dest_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Please select the destination directory"),
            self.selected_items[0].download_info["destination"],
            QFileDialog.ShowDirsOnly,
        )
        if not dest_dir:
            return

        _infohash = self.selected_items[0].infohash
        _name = self.selected_items[0].download_info["name"]

        request_manager.patch(
            f"downloads/{_infohash}",
            on_success=lambda res: self.on_files_moved(res, _name, dest_dir),
            data={"state": "move_storage", "dest_dir": dest_dir}
        )

    def on_files_moved(self, response, name, dest_dir):
        if "modified" in response and response["modified"]:
            self.window().tray_show_message(name, f"Moved to {dest_dir}")

    def on_export_download(self, checked):
        self.export_dir = QFileDialog.getExistingDirectory(
            self, tr("Please select the destination directory"), "", QFileDialog.ShowDirsOnly
        )

        selected_item = self.selected_items[:1]
        if len(self.export_dir) > 0 and selected_item:
            # Show confirmation dialog where we specify the name of the file
            torrent_name = selected_item[0].download_info['name']
            self.dialog = ConfirmationDialog(
                self,
                tr("Export torrent file"),
                tr("Please enter the name of the torrent file:"),
                [(tr("SAVE"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
                show_input=True,
            )
            self.dialog.dialog_widget.dialog_input.setPlaceholderText(tr("Torrent file name"))
            self.dialog.dialog_widget.dialog_input.setText(f"{torrent_name}.torrent")
            self.dialog.dialog_widget.dialog_input.setFocus()
            connect(self.dialog.button_clicked, self.on_export_download_dialog_done)
            self.dialog.show()

    def on_export_download_dialog_done(self, action):
        def on_success(result: Tuple):
            data, _ = result
            self.on_export_download_request_done(filename, data)

        item = get_first_item(self.selected_items)
        if action == 0 and item:
            filename = self.dialog.dialog_widget.dialog_input.text()
            request_manager.get(
                f"downloads/{item.infohash}/torrent",
                on_success=on_success,
                priority=QNetworkRequest.LowPriority,
                raw_response=True
            )

        self.dialog.close_dialog()
        self.dialog = None

    def on_export_download_request_done(self, filename, data):
        dest_path = os.path.join(self.export_dir, filename)
        try:
            torrent_file = open(dest_path, "wb")
            torrent_file.write(data)
            torrent_file.close()
        except OSError as exc:
            ConfirmationDialog.show_error(
                self.window(),
                tr("Error when exporting file"),
                tr("An error occurred when exporting the torrent file: %s") % str(exc),
            )
        else:
            self.window().tray_show_message(
                tr("Torrent file exported"), tr("Torrent file exported to %s") % str(dest_path)
            )

    def on_right_click_item(self, pos):
        item_clicked = self.window().downloads_list.itemAt(pos)
        if not item_clicked or not self.selected_items:
            return

        if item_clicked not in self.selected_items:
            self.selected_items.append(item_clicked)

        menu = TriblerActionMenu(self)

        start_action = QAction(tr("Start"), self)
        stop_action = QAction(tr("Stop"), self)
        remove_download_action = QAction(tr("Remove download"), self)
        force_recheck_action = QAction(tr("Force recheck"), self)
        export_download_action = QAction(tr("Export .torrent file"), self)
        explore_files_action = QAction(tr("Explore files"), self)
        move_files_action = QAction(tr("Move file storage"), self)

        no_anon_action = QAction(tr("No anonymity"), self)
        one_hop_anon_action = QAction(tr("One hop"), self)
        two_hop_anon_action = QAction(tr("Two hops"), self)
        three_hop_anon_action = QAction(tr("Three hops"), self)

        connect(start_action.triggered, self.on_start_download_clicked)
        start_action.setEnabled(DownloadsPage.start_download_enabled(self.selected_items))
        connect(stop_action.triggered, self.on_stop_download_clicked)
        stop_action.setEnabled(DownloadsPage.stop_download_enabled(self.selected_items))
        connect(remove_download_action.triggered, self.on_remove_download_clicked)
        connect(force_recheck_action.triggered, self.on_force_recheck_download)
        force_recheck_action.setEnabled(DownloadsPage.force_recheck_download_enabled(self.selected_items))
        connect(export_download_action.triggered, self.on_export_download)
        connect(explore_files_action.triggered, self.on_explore_files)
        connect(move_files_action.triggered, self.on_move_files)

        connect(no_anon_action.triggered, lambda _: self.change_anonymity(0))
        connect(one_hop_anon_action.triggered, lambda _: self.change_anonymity(1))
        connect(two_hop_anon_action.triggered, lambda _: self.change_anonymity(2))
        connect(three_hop_anon_action.triggered, lambda _: self.change_anonymity(3))

        menu.addAction(start_action)
        menu.addAction(stop_action)

        menu.addSeparator()
        menu.addAction(remove_download_action)
        menu.addSeparator()
        menu.addAction(force_recheck_action)
        menu.addSeparator()

        exclude_states = [
            DownloadStatus.METADATA,
            DownloadStatus.CIRCUITS,
            DownloadStatus.EXIT_NODES,
            DownloadStatus.HASHCHECKING,
            DownloadStatus.WAITING_FOR_HASHCHECK,
        ]
        if len(self.selected_items) == 1 and self.selected_items[0].get_status() not in exclude_states:
            menu.addAction(export_download_action)
        menu.addAction(explore_files_action)
        if len(self.selected_items) == 1:
            menu.addAction(move_files_action)
        menu.addSeparator()

        menu_anon_level = menu.addMenu(tr("Change Anonymity "))
        menu_anon_level.addAction(no_anon_action)
        menu_anon_level.addAction(one_hop_anon_action)
        menu_anon_level.addAction(two_hop_anon_action)
        menu_anon_level.addAction(three_hop_anon_action)

        menu.exec_(self.window().downloads_list.mapToGlobal(pos))
