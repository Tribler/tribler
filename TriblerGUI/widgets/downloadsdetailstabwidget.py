from urllib import quote_plus

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabWidget, QTreeWidgetItem, QAction

from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.defs import *
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, format_speed


class DownloadsDetailsTabWidget(QTabWidget):
    """
    The DownloadDetailsTab is the tab that provides details about a specific selected download. This information
    includes the connected peers, tracker status and file information.
    """

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.current_download = None
        self.request_mgr = None
        self.files_widgets = {}    # dict of file name -> widget
        self.tracker_widgets = {}  # dict of tracker URL -> widget

    def initialize_details_widget(self):
        self.window().download_files_list.customContextMenuRequested.connect(self.on_right_click_file_item)

    def update_with_download(self, download):
        self.current_download = download
        self.update_pages(new_download=True)

    @staticmethod
    def update_file_row(item, file_info):
        item.setText(0, file_info["name"])
        item.setText(1, format_size(float(file_info["size"])))
        item.setText(2, '{percent:.1%}'.format(percent=file_info["progress"]))
        item.setText(3, "yes" if file_info["included"] else "no")
        item.setData(0, Qt.UserRole, file_info)

    @staticmethod
    def update_tracker_row(item, tracker):
        item.setText(0, tracker["url"])
        item.setText(1, tracker["status"])
        item.setText(2, str(tracker["peers"]))

    @staticmethod
    def update_peer_row(item, peer):
        peer_name = "%s:%s" % (peer["ip"], peer["port"])
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

        self.window().download_progress_bar.update_with_download(self.current_download)
        self.window().download_detail_name_label.setText(self.current_download['name'])
        self.window().download_detail_status_label.setText(DLSTATUS_STRINGS[eval(self.current_download["status"])])
        self.window().download_detail_filesize_label.setText("%s in %d files" %
                                                             (format_size(float(self.current_download["size"])),
                                                              len(self.current_download["files"])))
        self.window().download_detail_health_label.setText("%d seeders, %d leechers" %
                                                           (self.current_download["num_seeds"],
                                                            self.current_download["num_peers"]))
        self.window().download_detail_infohash_label.setText(self.current_download['infohash'])
        self.window().download_detail_destination_label.setText(self.current_download["destination"])
        self.window().download_detail_availability_label.setText("%.2f" % self.current_download['availability'])

        if new_download:  # When we have a new download, clear all pages and draw new widgets

            # Populate the files list
            self.window().download_files_list.clear()
            self.files_widgets = {}
            for dfile in self.current_download["files"]:
                item = QTreeWidgetItem(self.window().download_files_list)
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
            self.tracker_widgets[tracker["url"]] = item

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
        selected_files_info = []

        for i in range(self.window().download_files_list.topLevelItemCount()):
            item = self.window().download_files_list.topLevelItem(i)
            file_info = item.data(0, Qt.UserRole)
            is_selected = item in self.window().download_files_list.selectedItems()
            item_infos.append((item, file_info["included"], is_selected))

            if is_selected:
                selected_files_info.append(file_info)

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

        include_action.triggered.connect(lambda: self.on_files_included(selected_files_info))
        include_action.setEnabled(True)
        exclude_action.triggered.connect(lambda: self.on_files_excluded(selected_files_info))
        exclude_action.setEnabled(not (num_excludes + num_includes_selected == len(item_infos)))

        menu.addAction(include_action)
        menu.addAction(exclude_action)

        menu.exec_(self.window().download_files_list.mapToGlobal(pos))

    def get_included_file_list(self):
        return [unicode(file_info["name"]) for file_info in self.current_download["files"] if file_info["included"]]

    def on_files_included(self, files_data):
        included_list = self.get_included_file_list()
        for file_data in files_data:
            if not file_data["name"] in included_list:
                included_list.append(file_data["name"])

        self.set_included_files(included_list)

    def on_files_excluded(self, files_data):
        included_list = self.get_included_file_list()
        for file_data in files_data:
            if file_data["name"] in included_list:
                included_list.remove(file_data["name"])

        self.set_included_files(included_list)

    def set_included_files(self, files):
        data_str = ''.join(u"selected_files[]=%s&" % quote_plus(file) for file in files)[:-1].encode('utf-8')
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s" % self.current_download['infohash'], lambda _: None,
                                         method='PATCH', data=data_str)
