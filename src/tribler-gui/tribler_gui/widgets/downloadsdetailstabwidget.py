from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QTabWidget, QTreeWidgetItem

from tribler_common.simpledefs import dlstatus_strings

from tribler_gui.defs import *
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import compose_magnetlink, connect, copy_to_clipboard, format_size, format_speed
from tribler_gui.widgets.downloadfilewidgetitem import DownloadFileWidgetItem


class DownloadsDetailsTabWidget(QTabWidget):
    """
    The DownloadDetailsTab is the tab that provides details about a specific selected download. This information
    includes the connected peers, tracker status and file information.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.current_download = None
        self.files_widgets = {}  # dict of file name -> widget
        self.selected_files_info = []

    def initialize_details_widget(self):
        connect(self.window().download_files_list.customContextMenuRequested, self.on_right_click_file_item)
        self.window().download_files_list.header().resizeSection(0, 220)
        self.setCurrentIndex(0)
        # make name, infohash and download destination selectable to copy
        self.window().download_detail_infohash_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.window().download_detail_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.window().download_detail_destination_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        connect(self.window().download_detail_copy_magnet_button.clicked, self.on_copy_magnet_clicked)

    def update_with_download(self, download):
        did_change = self.current_download != download
        self.current_download = download
        self.update_pages(new_download=did_change)

    @staticmethod
    def update_file_row(item, file_info):
        item.file_info = file_info
        item.update_item()

    @staticmethod
    def update_tracker_row(item, tracker):
        item.setText(0, tracker["url"])
        item.setText(1, tracker["status"])
        item.setText(2, str(tracker["peers"]))

    @staticmethod
    def update_peer_row(item, peer):
        peer_name = f"{peer['ip']}:{peer['port']}"
        if peer['connection_type'] == 1:
            peer_name += ' [WebSeed]'
        elif peer['connection_type'] == 2:
            peer_name += ' [HTTP Seed]'
        elif peer['connection_type'] == 3:
            peer_name += ' [uTP]'

        state = ""
        if peer['optimistic']:
            state += "O,"
        if peer['uinterested']:
            state += "UI,"
        if peer['uchoked']:
            state += "UC,"
        if peer['uhasqueries']:
            state += "UQ,"
        if not peer['uflushed']:
            state += "UBL,"
        if peer['dinterested']:
            state += "DI,"
        if peer['dchoked']:
            state += "DC,"
        if peer['snubbed']:
            state += "S,"
        state += peer['direction']

        item.setText(0, peer_name)
        item.setText(1, '%d%%' % (peer['completed'] * 100.0))
        item.setText(2, format_speed(peer['downrate']))
        item.setText(3, format_speed(peer['uprate']))
        item.setText(4, state)
        item.setText(5, peer['extended_version'])

    def update_pages(self, new_download=False):
        if self.current_download is None:
            return

        if "files" not in self.current_download:
            self.current_download["files"] = []

        self.window().download_progress_bar.update_with_download(self.current_download)
        self.window().download_detail_name_label.setText(self.current_download['name'])

        if self.current_download["vod_mode"]:
            self.window().download_detail_status_label.setText('Streaming')
        else:
            status_string = DLSTATUS_STRINGS[dlstatus_strings.index(self.current_download["status"])]
            if dlstatus_strings.index(self.current_download["status"]) == DLSTATUS_STOPPED_ON_ERROR:
                status_string += f" (error: {self.current_download['error']})"
            self.window().download_detail_status_label.setText(status_string)

        self.window().download_detail_filesize_label.setText(
            "%s in %d files" % (format_size(float(self.current_download["size"])), len(self.current_download["files"]))
        )
        self.window().download_detail_health_label.setText(
            "%d seeders, %d leechers" % (self.current_download["num_seeds"], self.current_download["num_peers"])
        )
        self.window().download_detail_infohash_label.setText(self.current_download['infohash'])
        self.window().download_detail_destination_label.setText(self.current_download["destination"])
        self.window().download_detail_ratio_label.setText(
            "%.3f, up: %s, down: %s"
            % (
                self.current_download["ratio"],
                format_size(self.current_download["total_up"]),
                format_size(self.current_download["total_down"]),
            )
        )
        self.window().download_detail_availability_label.setText(f"{self.current_download['availability']:.2f}")

        if new_download or len(self.current_download["files"]) != len(self.files_widgets.keys()):

            # (re)populate the files list
            self.window().download_files_list.clear()
            self.files_widgets = {}
            for dfile in self.current_download["files"]:
                item = DownloadFileWidgetItem(self.window().download_files_list, dfile)
                DownloadsDetailsTabWidget.update_file_row(item, dfile)
                self.files_widgets[dfile["name"]] = item

        else:  # No new download, just update data in the lists
            for dfile in self.current_download["files"]:
                DownloadsDetailsTabWidget.update_file_row(self.files_widgets[dfile["name"]], dfile)

        # Populate the trackers list
        self.window().download_trackers_list.clear()
        for tracker in self.current_download["trackers"]:
            item = QTreeWidgetItem(self.window().download_trackers_list)
            DownloadsDetailsTabWidget.update_tracker_row(item, tracker)

        # Populate the peers list if the peer information is available
        self.window().download_peers_list.clear()
        if "peers" in self.current_download:
            for peer in self.current_download["peers"]:
                item = QTreeWidgetItem(self.window().download_peers_list)
                DownloadsDetailsTabWidget.update_peer_row(item, peer)

    def on_right_click_file_item(self, pos):
        num_selected = len(self.window().download_files_list.selectedItems())
        if num_selected == 0:
            return

        item_infos = []  # Array of (item, included, is_selected)
        self.selected_files_info = []

        for i in range(self.window().download_files_list.topLevelItemCount()):
            item = self.window().download_files_list.topLevelItem(i)
            is_selected = item in self.window().download_files_list.selectedItems()
            item_infos.append((item, item.file_info["included"], is_selected))

            if is_selected:
                self.selected_files_info.append(item.file_info)

        item_clicked = self.window().download_files_list.itemAt(pos)
        if not item_clicked or not item_clicked in self.window().download_files_list.selectedItems():
            return

        # Check whether we should enable the 'exclude' button
        num_excludes = 0
        num_includes_selected = 0
        for item_info in item_infos:
            if item_info[1] and item_info[0] in self.window().download_files_list.selectedItems():
                num_includes_selected += 1
            if not item_info[1]:
                num_excludes += 1

        menu = TriblerActionMenu(self)

        include_action = QAction('Include file' + ('(s)' if num_selected > 1 else ''), self)
        exclude_action = QAction('Exclude file' + ('(s)' if num_selected > 1 else ''), self)

        connect(include_action.triggered, self.on_files_included)
        include_action.setEnabled(True)
        connect(exclude_action.triggered, self.on_files_excluded)
        exclude_action.setEnabled(not (num_excludes + num_includes_selected == len(item_infos)))

        menu.addAction(include_action)
        menu.addAction(exclude_action)

        menu.exec_(self.window().download_files_list.mapToGlobal(pos))

    def get_included_file_list(self):
        return [file_info["index"] for file_info in self.current_download["files"] if file_info["included"]]

    def on_files_included(self, *args):
        included_list = self.get_included_file_list()
        for file_data in self.selected_files_info:
            if not file_data["index"] in included_list:
                included_list.append(file_data["index"])

        self.set_included_files(included_list)

    def on_files_excluded(self, *args):
        included_list = self.get_included_file_list()
        for file_data in self.selected_files_info:
            if file_data["index"] in included_list:
                included_list.remove(file_data["index"])

        self.set_included_files(included_list)

    def set_included_files(self, files):
        post_data = {"selected_files": [ind for ind in files]}
        TriblerNetworkRequest(
            f"downloads/{self.current_download['infohash']}", lambda _: None, method='PATCH', data=post_data
        )

    def on_copy_magnet_clicked(self, checked):
        trackers = [
            tr['url'] for tr in self.current_download['trackers'] if 'url' in tr and tr['url'] not in ['[DHT]', '[PeX]']
        ]
        magnet_link = compose_magnetlink(
            self.current_download['infohash'], name=self.current_download.get('name', None), trackers=trackers
        )
        copy_to_clipboard(magnet_link)
        self.window().tray_show_message("Copying magnet link", magnet_link)
