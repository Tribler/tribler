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

            # Populate the trackers list
            self.window().download_trackers_list.clear()
            for tracker in self.current_download["trackers"]:
                item = QTreeWidgetItem(self.window().download_trackers_list)
                DownloadsDetailsTabWidget.update_tracker_row(item, tracker)
                self.tracker_widgets[tracker["url"]] = item

        else:  # No new download, just update data in the lists
            for dfile in self.current_download["files"]:
                DownloadsDetailsTabWidget.update_file_row(self.files_widgets[dfile["name"]], dfile)

            for tracker in self.current_download["trackers"]:
                DownloadsDetailsTabWidget.update_tracker_row(self.tracker_widgets[tracker["url"]], tracker)

        # Populate the peers list if the peer information is available
        self.window().download_peers_list.clear()
        if "peers" in self.current_download:
            for peer in self.current_download["peers"]:
                item = QTreeWidgetItem(self.window().download_peers_list)
                DownloadsDetailsTabWidget.update_peer_row(item, peer)

    def on_right_click_file_item(self, pos):
        item_clicked = self.window().download_files_list.itemAt(pos)
        if not item_clicked:
            return

        file_data = item_clicked.data(0, Qt.UserRole)

        menu = TriblerActionMenu(self)

        include_action = QAction('Include', self)
        exclude_action = QAction('Exclude', self)

        include_action.triggered.connect(lambda: self.on_file_included(file_data))
        include_action.setEnabled(not file_data["included"])
        exclude_action.triggered.connect(lambda: self.on_file_excluded(file_data))
        exclude_action.setEnabled(file_data["included"])

        menu.addAction(include_action)
        menu.addAction(exclude_action)

        menu.exec_(self.window().download_files_list.mapToGlobal(pos))

    def get_included_file_list(self):
        return [unicode(file_info["name"]) for file_info in self.current_download["files"] if file_info["included"]]

    def on_file_included(self, file_data):
        included_list = self.get_included_file_list()
        if not file_data["name"] in included_list:
            included_list.append(file_data["name"])

        self.set_included_files(included_list)

    def on_file_excluded(self, file_data):
        included_list = self.get_included_file_list()
        if file_data["name"] in included_list:
            included_list.remove(file_data["name"])

        self.set_included_files(included_list)

    def set_included_files(self, files):
        data_str = ''.join(u"selected_files[]=%s&" % file for file in files)[:-1].encode('utf-8')
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("downloads/%s" % self.current_download['infohash'], self.on_files_included,
                                         method='PATCH', data=data_str)

    def on_files_included(self, response):
        pass
