import math
import operator
from enum import IntEnum
from pathlib import PurePosixPath
from typing import Dict, Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QTabWidget, QTreeWidgetItem

from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.gui.defs import STATUS_STRING
from tribler.gui.utilities import compose_magnetlink, connect, copy_to_clipboard, format_size, format_speed, tr
from tribler.gui.widgets.torrentfiletreewidget import PreformattedTorrentFileTreeWidget

INCLUDED_FILES_CHANGE_DELAY = 1000  # milliseconds

# Disabled, because drawing progress bars with setItemWidget is horribly slow on some systems.
# We must use delegate-based drawing instead
PROGRESS_BAR_DRAW_LIMIT = 0  # Don't draw progress bars for files in torrents that have more than this many files


class DownloadDetailsTabs(IntEnum):
    DETAILS = 0
    FILES = 1
    TRACKERS = 2
    PEERS = 3


def convert_to_files_tree_format(download_info):
    files = download_info['files']
    out = []
    for file in sorted(files, key=operator.itemgetter("index")):
        file_path_parts = PurePosixPath(file['name']).parts
        file_path = [download_info['name'], *file_path_parts]
        if len(files) == 1:
            # Special case of a torrent consisting of a single file
            # ACHTUNG! Some torrents can still put a single file into a path of directories, resulting
            # in a torrent name that contain slashes. This logic supports that case.
            file_path = file_path_parts
        out.append(
            {
                'path': file_path,
                'length': file['size'],
                'included': file['included'],
                'progress': file['progress'],
            }
        )
    return out


class DownloadsDetailsTabWidget(QTabWidget):
    """
    The DownloadDetailsTab is the tab that provides details about a specific selected download. This information
    includes the connected peers, tracker status and file information.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.current_download: Optional[Dict] = None
        self.selected_files_info = []

        # This timer is used to apply files selection changes in batches, to avoid multiple requests to the Core
        # in case of e.g. deselecting a whole directory of files.
        # When the user changes selection of files for download, we restart the timer.
        # Then we apply all the changes in a single batch when it triggers.
        # The same logic is used to batch Channel changes.
        self._batch_changes_timer = QTimer(self)
        self._batch_changes_timer.setSingleShot(True)

    def _restart_changes_timer(self):
        self._batch_changes_timer.stop()
        self._batch_changes_timer.start(INCLUDED_FILES_CHANGE_DELAY)

    def initialize_details_widget(self):
        dl_files_list = PreformattedTorrentFileTreeWidget(self.window().download_files_tab)
        self.window().download_files_tab.layout().addWidget(dl_files_list)
        setattr(self.window(), "download_files_list", dl_files_list)
        self.setCurrentIndex(0)
        # make name, infohash and download destination selectable to copy
        self.window().download_detail_infohash_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.window().download_detail_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.window().download_detail_destination_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        connect(self.window().download_detail_copy_magnet_button.clicked, self.on_copy_magnet_clicked)

    def update_with_download(self, download):
        # If the same infohash gets re-added with different parameters (e.g. different selected files),
        # that's a different download. Thus, we must differ between the old one and the new one, to prevent
        # "caching" the previous parameters. The most reliable way to make difference is by time_added property
        did_change = (
                self.current_download is None
                or self.current_download.get('infohash') != download.get('infohash')
                or self.current_download.get('time_added') != download.get('time_added')
        )
        # When we switch to another download, we want to fixate the changes user did to selected files.
        # Also, we have to stop the change batching time to prevent carrying the event to the new download
        if did_change and self._batch_changes_timer.isActive():
            self._batch_changes_timer.stop()

        self.current_download = download
        self.update_pages(new_download=did_change)

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

        status = DownloadStatus(self.current_download["status_code"])
        status_string = STATUS_STRING[status]
        if status == DownloadStatus.STOPPED_ON_ERROR:
            status_string += f" (error: {self.current_download['error']})"
        self.window().download_detail_status_label.setText(status_string)

        self.window().download_detail_filesize_label.setText(
            tr("%(num_bytes)s in %(num_files)d files")
            % {
                'num_bytes': format_size(float(self.current_download["size"])),
                'num_files': len(self.current_download["files"]),
            }
        )
        self.window().download_detail_health_label.setText(
            tr("%d seeders, %d leechers") % (self.current_download["num_seeds"], self.current_download["num_peers"])
        )
        self.window().download_detail_infohash_label.setText(self.current_download['infohash'])
        self.window().download_detail_destination_label.setText(self.current_download["destination"])
        all_time_upload = format_size(self.current_download['all_time_upload'])
        all_time_download = format_size(self.current_download['all_time_download'])
        all_time_ratio = self.current_download['all_time_ratio']
        all_time_ratio = '∞' if all_time_ratio == math.inf else f'{all_time_ratio:.3f}'
        self.window().download_detail_ratio_label.setText(
            f"{all_time_ratio}, upload: {all_time_upload}, download: {all_time_download}"
        )
        availability = self.current_download.get('availability')
        availability = f"{availability :.2f}" if availability else ''

        self.window().download_detail_availability_label.setText(availability)

        if new_download:
            self.window().download_files_list.clear()
            self.window().download_files_list.initialize(self.current_download['infohash'])

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

    def on_copy_magnet_clicked(self, checked):
        trackers = [
            tk['url'] for tk in self.current_download['trackers'] if 'url' in tk and tk['url'] not in ['[DHT]', '[PeX]']
        ]
        magnet_link = compose_magnetlink(
            self.current_download['infohash'], name=self.current_download.get('name', None), trackers=trackers
        )
        copy_to_clipboard(magnet_link)
        self.window().tray_show_message(tr("Copying magnet link"), magnet_link)
