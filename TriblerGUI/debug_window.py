import json
import socket
from time import localtime, strftime

import psutil
from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem

from TriblerGUI.utilities import get_ui_file_path, format_size
from TriblerGUI.tribler_request_manager import performed_requests as tribler_performed_requests, TriblerRequestManager
from TriblerGUI.event_request_manager import received_events as tribler_received_events


class DebugWindow(QMainWindow):
    """
    The debug window shows various statistics about Tribler such as performed requests, Dispersy statistics and
    community information.
    """

    def __init__(self, settings):
        QMainWindow.__init__(self)

        self.request_mgr = None

        uic.loadUi(get_ui_file_path('debugwindow.ui'), self)
        self.setWindowTitle("Tribler debug pane")

        self.window().debug_tab_widget.setCurrentIndex(0)
        self.window().dispersy_tab_widget.setCurrentIndex(0)
        self.window().debug_tab_widget.currentChanged.connect(self.tab_changed)
        self.window().dispersy_tab_widget.currentChanged.connect(self.dispersy_tab_changed)
        self.window().events_tree_widget.itemClicked.connect(self.on_event_clicked)
        self.window().system_tab_widget.currentChanged.connect(self.system_tab_changed)
        self.load_general_tab()

        self.window().open_files_tree_widget.header().setSectionResizeMode(0, QHeaderView.Stretch)

        if not settings['trustchain']['enabled']:
            self.window().debug_tab_widget.setTabEnabled(2, False)

    def tab_changed(self, index):
        if index == 0:
            self.load_general_tab()
        elif index == 1:
            self.load_requests_tab()
        elif index == 2:
            self.load_trustchain_tab()
        elif index == 3:
            self.dispersy_tab_changed(self.window().dispersy_tab_widget.currentIndex())
        elif index == 4:
            self.load_events_tab()
        elif index == 5:
            self.system_tab_changed(self.window().system_tab_widget.currentIndex())

    def dispersy_tab_changed(self, index):
        if index == 0:
            self.load_dispersy_general_tab()
        elif index == 1:
            self.load_dispersy_communities_tab()

    def system_tab_changed(self, index):
        if index == 0:
            self.load_open_files_tab()
        elif index == 1:
            self.load_open_sockets_tab()
        elif index == 2:
            self.load_threads_tab()

    def create_and_add_widget_item(self, key, value, widget):
        item = QTreeWidgetItem(widget)
        item.setText(0, key)
        item.setText(1, "%s" % value)
        widget.addTopLevelItem(item)

    def load_general_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("statistics/tribler", self.on_tribler_statistics)

    def on_tribler_statistics(self, data):
        data = data["tribler_statistics"]
        self.window().general_tree_widget.clear()
        self.create_and_add_widget_item("Number of channels", data["num_channels"], self.window().general_tree_widget)
        self.create_and_add_widget_item("Database size", format_size(data["database_size"]),
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Number of collected torrents", data["torrents"]["num_collected"],
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Number of torrent files", data["torrents"]["num_files"],
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Total size of torrent files", format_size(data["torrents"]["total_size"]),
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("", "", self.window().general_tree_widget)

        disk_usage = psutil.disk_usage('/')
        self.create_and_add_widget_item("Total disk space", format_size(disk_usage.total),
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Used disk space", format_size(disk_usage.used),
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Free disk space", format_size(disk_usage.free),
                                        self.window().general_tree_widget)

    def load_requests_tab(self):
        self.window().requests_tree_widget.clear()
        for endpoint, method, data, timestamp, status_code in sorted(tribler_performed_requests.values(),
                                                                     key=lambda x: x[3]):
            item = QTreeWidgetItem(self.window().requests_tree_widget)
            item.setText(0, "%s %s %s" % (method, endpoint, data))
            item.setText(1, ("%d" % status_code) if status_code else "unknown")
            item.setText(2, "%s" % strftime("%H:%M:%S", localtime(timestamp)))
            self.window().requests_tree_widget.addTopLevelItem(item)

    def load_trustchain_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("trustchain/statistics", self.on_trustchain_statistics)

    def on_trustchain_statistics(self, data):
        self.window().trustchain_tree_widget.clear()
        for key, value in data["statistics"].iteritems():
            self.create_and_add_widget_item(key, value, self.window().trustchain_tree_widget)

    def load_dispersy_general_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("statistics/dispersy", self.on_dispersy_general_stats)

    def on_dispersy_general_stats(self, data):
        self.window().dispersy_general_tree_widget.clear()
        for key, value in data["dispersy_statistics"].iteritems():
            self.create_and_add_widget_item(key, value, self.window().dispersy_general_tree_widget)

    def load_dispersy_communities_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("statistics/communities", self.on_dispersy_community_stats)

    def on_dispersy_community_stats(self, data):
        self.window().communities_tree_widget.clear()
        for community in data["community_statistics"]:
            item = QTreeWidgetItem(self.window().communities_tree_widget)
            item.setText(0, community["classification"])
            item.setText(1, community["identifier"][:6])
            item.setText(2, community["member"][:6])
            item.setText(3, "%s" % community["candidates"])
            self.window().communities_tree_widget.addTopLevelItem(item)

    def on_event_clicked(self, item):
        event_dict = item.data(0, Qt.UserRole)
        self.window().event_text_box.setPlainText(json.dumps(event_dict))

    def load_events_tab(self):
        self.window().events_tree_widget.clear()
        for event_dict, timestamp in tribler_received_events:
            item = QTreeWidgetItem(self.window().events_tree_widget)
            item.setData(0, Qt.UserRole, event_dict)
            item.setText(0, "%s" % event_dict['type'])
            item.setText(1, "%s" % strftime("%H:%M:%S", localtime(timestamp)))
            self.window().events_tree_widget.addTopLevelItem(item)

    def load_open_files_tab(self):
        # Fill the open files (GUI) tree widget
        my_process = psutil.Process()
        self.window().open_files_tree_widget.clear()
        gui_item = QTreeWidgetItem(self.window().open_files_tree_widget)

        open_files = my_process.open_files()
        gui_item.setText(0, "GUI (%d)" % len(open_files))
        self.window().open_files_tree_widget.addTopLevelItem(gui_item)

        for open_file in open_files:
            item = QTreeWidgetItem()
            item.setText(0, open_file.path)
            item.setText(1, "%d" % open_file.fd)
            gui_item.addChild(item)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/open_files", self.on_core_open_files)

    def on_core_open_files(self, data):
        core_item = QTreeWidgetItem(self.window().open_files_tree_widget)
        core_item.setText(0, "Core (%d)" % len(data["open_files"]))
        self.window().open_files_tree_widget.addTopLevelItem(core_item)

        for open_file in data["open_files"]:
            item = QTreeWidgetItem()
            item.setText(0, open_file["path"])
            item.setText(1, "%d" % open_file["fd"])
            core_item.addChild(item)

    def load_open_sockets_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/open_sockets", self.on_core_open_sockets)

    def on_core_open_sockets(self, data):
        self.window().open_sockets_tree_widget.clear()
        self.window().open_sockets_label.setText("Sockets opened by core (%d):" % len(data["open_sockets"]))
        for open_socket in data["open_sockets"]:
            if open_socket["family"] == socket.AF_INET:
                family = "AF_INET"
            elif open_socket["family"] == socket.AF_INET6:
                family = "AF_INET6"
            elif open_socket["family"] == socket.AF_UNIX:
                family = "AF_UNIX"
            else:
                family = "-"

            item = QTreeWidgetItem(self.window().open_sockets_tree_widget)
            item.setText(0, open_socket["laddr"])
            item.setText(1, open_socket["raddr"])
            item.setText(2, family)
            item.setText(3, "SOCK_STREAM" if open_socket["type"] == socket.SOCK_STREAM else "SOCK_DGRAM")
            item.setText(4, open_socket["status"])
            self.window().open_sockets_tree_widget.addTopLevelItem(item)

    def load_threads_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/threads", self.on_core_threads)

    def on_core_threads(self, data):
        self.window().threads_tree_widget.clear()
        for thread_info in data["threads"]:
            thread_item = QTreeWidgetItem(self.window().threads_tree_widget)
            thread_item.setText(0, "%d" % thread_info["thread_id"])
            thread_item.setText(1, thread_info["thread_name"])
            self.window().threads_tree_widget.addTopLevelItem(thread_item)

            for frame in thread_info["frames"]:
                frame_item = QTreeWidgetItem()
                frame_item.setText(2, frame)
                thread_item.addChild(frame_item)
