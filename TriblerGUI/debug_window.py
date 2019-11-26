import datetime
import logging
import os
import socket
import sys
from time import localtime, strftime, time

from PyQt5 import QtGui, uic
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QTextCursor
from PyQt5.QtWidgets import QDesktopWidget, QFileDialog, QHeaderView, QMainWindow, QMessageBox, QTreeWidgetItem

import libtorrent

import psutil

import Tribler.Core.Utilities.json_util as json

from TriblerGUI.defs import DEBUG_PANE_REFRESH_TIMEOUT, GB, MB
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.event_request_manager import received_events as tribler_received_events
from TriblerGUI.tribler_request_manager import TriblerRequestManager, performed_requests as tribler_performed_requests
from TriblerGUI.utilities import format_size, get_ui_file_path
from TriblerGUI.widgets.tokenminingpage import TimeSeriesPlot

try:
    from meliae import scanner
except ImportError:
    scanner = None






class MemoryPlot(TimeSeriesPlot):

    def __init__(self, parent, **kargs):
        series = [{'name': 'Memory', 'pen': (0, 153, 255), 'symbolBrush': (0, 153, 255), 'symbolPen': 'w'}]
        super(MemoryPlot, self).__init__(parent, 'Memory Usage', series, **kargs)
        self.setBackground('#FCF9F6')
        self.setLabel('left', 'Memory', units='bytes')
        self.setLimits(yMin=-MB, yMax=10 * GB)


class CPUPlot(TimeSeriesPlot):

    def __init__(self, parent, **kargs):
        series = [{'name': 'CPU', 'pen': (0, 153, 255), 'symbolBrush': (0, 153, 255), 'symbolPen': 'w'}]
        super(CPUPlot, self).__init__(parent, 'CPU Usage', series, **kargs)
        self.setBackground('#FCF9F6')
        self.setLabel('left', 'CPU', units='%')
        self.setLimits(yMin=-10, yMax=200)


class DebugWindow(QMainWindow):
    """
    The debug window shows various statistics about Tribler such as performed requests, IPv8 statistics and
    community information.
    """
    resize_event = pyqtSignal()

    def __init__(self, settings, tribler_version):
        self._logger = logging.getLogger(self.__class__.__name__)
        QMainWindow.__init__(self)

        self.request_mgr = None
        self.cpu_plot = None
        self.memory_plot = None
        self.initialized_cpu_plot = False
        self.initialized_memory_plot = False
        self.cpu_plot_timer = None
        self.memory_plot_timer = None
        self.tribler_version = tribler_version
        self.profiler_enabled = False
        self.toggling_profiler = False

        uic.loadUi(get_ui_file_path('debugwindow.ui'), self)
        self.setWindowTitle("Tribler debug pane")

        self.window().dump_memory_core_button.clicked.connect(lambda: self.on_memory_dump_button_clicked(True))
        self.window().dump_memory_gui_button.clicked.connect(lambda: self.on_memory_dump_button_clicked(False))
        self.window().toggle_profiler_button.clicked.connect(self.on_toggle_profiler_button_clicked)

        self.window().debug_tab_widget.setCurrentIndex(0)
        self.window().ipv8_tab_widget.setCurrentIndex(0)
        self.window().tunnel_tab_widget.setCurrentIndex(0)
        self.window().system_tab_widget.setCurrentIndex(0)
        self.window().debug_tab_widget.currentChanged.connect(self.tab_changed)
        self.window().ipv8_tab_widget.currentChanged.connect(self.ipv8_tab_changed)
        self.window().tunnel_tab_widget.currentChanged.connect(self.tunnel_tab_changed)
        self.window().events_tree_widget.itemClicked.connect(self.on_event_clicked)
        self.window().system_tab_widget.currentChanged.connect(self.system_tab_changed)
        self.load_general_tab()

        self.window().open_files_tree_widget.header().setSectionResizeMode(0, QHeaderView.Stretch)

        # Enable/disable tabs, based on settings
        self.window().debug_tab_widget.setTabEnabled(2, settings and settings['trustchain']['enabled'])
        self.window().debug_tab_widget.setTabEnabled(3, settings and settings['ipv8']['enabled'])
        self.window().system_tab_widget.setTabEnabled(3, settings and settings['resource_monitor']['enabled'])
        self.window().system_tab_widget.setTabEnabled(4, settings and settings['resource_monitor']['enabled'])

        # Refresh logs
        self.window().log_refresh_button.clicked.connect(lambda: self.load_logs_tab())
        self.window().log_tab_widget.currentChanged.connect(lambda index: self.load_logs_tab())

        # IPv8 statistics enabled?
        self.ipv8_statistics_enabled = settings['ipv8']['statistics']

        # Libtorrent tab
        self.init_libtorrent_tab()

        # Position to center
        frame_geometry = self.frameGeometry()
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center_point = QDesktopWidget().screenGeometry(screen).center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

        # Refresh timer
        self.refresh_timer = None

    def hideEvent(self, hide_event):
        self.stop_timer()

    def run_with_timer(self, call_fn, timeout=DEBUG_PANE_REFRESH_TIMEOUT):
        call_fn()
        self.stop_timer()
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(lambda _call_fn=call_fn, _timeout=timeout:
                                           self.run_with_timer(_call_fn, timeout=_timeout))
        self.refresh_timer.start(timeout)

    def stop_timer(self):
        if self.refresh_timer:
            try:
                self.refresh_timer.stop()
                self.refresh_timer.deleteLater()
            except RuntimeError:
                self._logger.error("Failed to stop refresh timer in Debug pane")

    def init_libtorrent_tab(self):
        self.window().libtorrent_tab_widget.setCurrentIndex(0)
        self.window().libtorrent_tab_widget.currentChanged.connect(lambda _: self.load_libtorrent_data(export=False))

        self.window().lt_zero_hop_btn.clicked.connect(lambda _: self.load_libtorrent_data(export=False))
        self.window().lt_one_hop_btn.clicked.connect(lambda _: self.load_libtorrent_data(export=False))
        self.window().lt_two_hop_btn.clicked.connect(lambda _: self.load_libtorrent_data(export=False))
        self.window().lt_three_hop_btn.clicked.connect(lambda _: self.load_libtorrent_data(export=False))
        self.window().lt_export_btn.clicked.connect(lambda _: self.load_libtorrent_data(export=True))

        self.window().lt_zero_hop_btn.setChecked(True)

    def tab_changed(self, index):
        if index == 0:
            self.load_general_tab()
        elif index == 1:
            self.load_requests_tab()
        elif index == 2:
            self.run_with_timer(self.load_trustchain_tab)
        elif index == 3:
            self.ipv8_tab_changed(self.window().ipv8_tab_widget.currentIndex())
        elif index == 4:
            self.tunnel_tab_changed(self.window().tunnel_tab_widget.currentIndex())
        elif index == 5:
            self.run_with_timer(self.load_dht_tab)
        elif index == 6:
            self.run_with_timer(self.load_events_tab)
        elif index == 7:
            self.system_tab_changed(self.window().system_tab_widget.currentIndex())
        elif index == 8:
            self.load_libtorrent_data()
        elif index == 9:
            self.load_logs_tab()

    def ipv8_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_ipv8_general_tab)
        elif index == 1:
            self.run_with_timer(self.load_ipv8_communities_tab)
        elif index == 2:
            self.run_with_timer(self.load_ipv8_community_details_tab)

    def tunnel_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_tunnel_circuits_tab)
        elif index == 1:
            self.run_with_timer(self.load_tunnel_relays_tab)
        elif index == 2:
            self.run_with_timer(self.load_tunnel_exits_tab)
        elif index == 3:
            self.run_with_timer(self.load_tunnel_swarms_tab)

    def system_tab_changed(self, index):
        if index == 0:
            self.load_open_files_tab()
        elif index == 1:
            self.load_open_sockets_tab()
        elif index == 2:
            self.load_threads_tab()
        elif index == 3:
            self.load_cpu_tab()
        elif index == 4:
            self.load_memory_tab()
        elif index == 5:
            self.load_profiler_tab()

    def create_and_add_widget_item(self, key, value, widget):
        item = QTreeWidgetItem(widget)
        item.setText(0, key)
        item.setText(1, "%s" % value)
        widget.addTopLevelItem(item)

    def load_general_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("statistics/tribler", self.on_tribler_statistics)

    def on_tribler_statistics(self, data):
        if not data:
            return
        data = data["tribler_statistics"]
        self.window().general_tree_widget.clear()
        self.create_and_add_widget_item("Tribler version", self.tribler_version, self.window().general_tree_widget)
        self.create_and_add_widget_item("Python version", sys.version.replace('\n', ''),  # to fit in one line
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Libtorrent version", libtorrent.version, self.window().general_tree_widget)
        self.create_and_add_widget_item("", "", self.window().general_tree_widget)

        self.create_and_add_widget_item("Number of channels", data["num_channels"], self.window().general_tree_widget)
        self.create_and_add_widget_item("Database size", format_size(data["db_size"]),
                                        self.window().general_tree_widget)
        self.create_and_add_widget_item("Number of known torrents", data["num_torrents"],
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
        for endpoint, method, data, timestamp, status_code in sorted(tribler_performed_requests,
                                                                     key=lambda x: x[3]):
            item = QTreeWidgetItem(self.window().requests_tree_widget)
            item.setText(0, "%s %s %s" % (method, repr(endpoint), repr(data)))
            item.setText(1, ("%d" % status_code) if status_code else "unknown")
            item.setText(2, "%s" % strftime("%H:%M:%S", localtime(timestamp)))
            self.window().requests_tree_widget.addTopLevelItem(item)

    def load_trustchain_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("trustchain/statistics", self.on_trustchain_statistics)

    def on_trustchain_statistics(self, data):
        if not data:
            return
        self.window().trustchain_tree_widget.clear()
        for key, value in data["statistics"].items():
            self.create_and_add_widget_item(key, value, self.window().trustchain_tree_widget)

    def load_ipv8_general_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("statistics/ipv8", self.on_ipv8_general_stats)

    def on_ipv8_general_stats(self, data):
        if not data:
            return
        self.window().ipv8_general_tree_widget.clear()
        for key, value in data["ipv8_statistics"].items():
            if key in ('total_up', 'total_down'):
                value = "%.2f MB" % (value / (1024.0 * 1024.0))
            elif key == 'session_uptime':
                value = "%s" % str(datetime.timedelta(seconds=int(value)))
            self.create_and_add_widget_item(key, value, self.window().ipv8_general_tree_widget)

    def load_ipv8_communities_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/overlays", self.on_ipv8_community_stats)

    def _colored_peer_count(self, peer_count, overlay_count, master_peer):
        is_discovery = (master_peer == "3081a7301006072a8648ce3d020106052b81040027038192000403b3ab059ced9b20646ab5e01"
                                       "762b3595c5e8855227ae1e424cff38a1e4edee73734ff2e2e829eb4f39bab20d7578284fcba72"
                                       "51acd74e7daf96f21d01ea17077faf4d27a655837d072baeb671287a88554e1191d8904b0dc57"
                                       "2d09ff95f10ff092c8a5e2a01cd500624376aec875a6e3028aab784cfaf0bac6527245db8d939"
                                       "00d904ac2a922a02716ccef5a22f7968")
        limits = [20, overlay_count * 30 + 1] if is_discovery else [20, 31]
        color = 0xF4D03F if peer_count < limits[0] else (0x56F129 if peer_count < limits[1] else 0xF12929)
        return QBrush(QColor(color))

    def on_ipv8_community_stats(self, data):
        if not data:
            return
        self.window().communities_tree_widget.clear()
        for overlay in data["overlays"]:
            item = QTreeWidgetItem(self.window().communities_tree_widget)
            item.setText(0, overlay["overlay_name"])
            item.setText(1, overlay["master_peer"][-12:])
            item.setText(2, overlay["my_peer"][-12:])
            peer_count = len(overlay["peers"])
            item.setText(3, "%s" % peer_count)
            item.setForeground(3, self._colored_peer_count(peer_count, len(data["overlays"]),
                                                           overlay["master_peer"]))

            if "statistics" in overlay and overlay["statistics"]:
                statistics = overlay["statistics"]
                item.setText(4, "%.3f" % (statistics["bytes_up"]/(1024.0 * 1024.0)))
                item.setText(5, "%.3f" % (statistics["bytes_down"]/(1024.0 * 1024.0)))
                item.setText(6, "%s" % statistics["num_up"])
                item.setText(7, "%s" % statistics["num_down"])
                item.setText(8, "%.3f" % statistics["diff_time"])
            else:
                item.setText(4, "N/A")
                item.setText(5, "N/A")
                item.setText(6, "N/A")
                item.setText(7, "N/A")
                item.setText(8, "N/A")

            self.window().communities_tree_widget.addTopLevelItem(item)
            map(self.window().communities_tree_widget.resizeColumnToContents, range(10))

    def load_ipv8_community_details_tab(self):
        if self.ipv8_statistics_enabled:
            self.window().ipv8_statistics_error_label.setHidden(True)
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("ipv8/overlays/statistics", self.on_ipv8_community_detail_stats)
        else:
            self.window().ipv8_statistics_error_label.setHidden(False)
            self.window().ipv8_communities_details_widget.setHidden(True)

    def on_ipv8_community_detail_stats(self, data):
        if not data:
            return

        self.window().ipv8_communities_details_widget.setHidden(False)
        self.window().ipv8_communities_details_widget.clear()
        for overlay in data["statistics"]:
            self.window().ipv8_communities_details_widget.setColumnWidth(0, 250)

            for key, stats in overlay.items():
                header_item = QTreeWidgetItem(self.window().ipv8_communities_details_widget)
                header_item.setFirstColumnSpanned(True)
                header_item.setBackground(0, QtGui.QColor('#CCCCCC'))
                header_item.setText(0, key)
                self.window().ipv8_communities_details_widget.addTopLevelItem(header_item)

                for request_id, stat in stats.items():
                    stat_item = QTreeWidgetItem(self.window().ipv8_communities_details_widget)
                    stat_item.setText(0, request_id)
                    stat_item.setText(1, "%.3f" % (stat["bytes_up"] / (1024.0 * 1024.0)))
                    stat_item.setText(2, "%.3f" % (stat["bytes_down"] / (1024.0 * 1024.0)))
                    stat_item.setText(3, "%s" % stat["num_up"])
                    stat_item.setText(4, "%s" % stat["num_down"])
                    self.window().ipv8_communities_details_widget.addTopLevelItem(stat_item)

    def add_items_to_tree(self, tree, items, keys):
        tree.clear()
        for item in items:
            widget_item = QTreeWidgetItem(tree)
            for index, key in enumerate(keys):
                if key in ["bytes_up", "bytes_down"]:
                    value = format_size(item[key])
                elif key in ["creation_time", "last_lookup"]:
                    value = str(datetime.timedelta(seconds=int(time() - item[key]))) if item[key] > 0 else '-'
                else:
                    value = str(item[key])
                widget_item.setText(index, value)
            tree.addTopLevelItem(widget_item)

    def load_tunnel_circuits_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/tunnel/circuits", self.on_tunnel_circuits)

    def on_tunnel_circuits(self, data):
        if data:
            self.add_items_to_tree(self.window().circuits_tree_widget, data.get("circuits"),
                                   ["circuit_id", "goal_hops", "actual_hops", "unverified_hop",
                                    "type", "state", "bytes_up", "bytes_down", "creation_time"])

    def load_tunnel_relays_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/tunnel/relays", self.on_tunnel_relays)

    def on_tunnel_relays(self, data):
        if data:
            self.add_items_to_tree(self.window().relays_tree_widget, data["relays"],
                                   ["circuit_from", "circuit_to", "is_rendezvous",
                                    "bytes_up", "bytes_down", "creation_time"])

    def load_tunnel_exits_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/tunnel/exits", self.on_tunnel_exits)

    def on_tunnel_exits(self, data):
        if data:
            self.add_items_to_tree(self.window().exits_tree_widget, data["exits"],
                                   ["circuit_from", "enabled", "bytes_up", "bytes_down", "creation_time"])

    def load_tunnel_swarms_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/tunnel/swarms", self.on_tunnel_swarms)

    def on_tunnel_swarms(self, data):
        if data:
            self.add_items_to_tree(self.window().swarms_tree_widget, data.get("swarms"),
                                   ["info_hash", "num_seeders", "num_connections", "num_connections_incomplete",
                                    "seeding", "last_lookup", "bytes_up", "bytes_down"])

    def load_dht_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/dht/statistics", self.on_dht_statistics)

    def on_dht_statistics(self, data):
        if not data:
            return
        self.window().dht_tree_widget.clear()
        for key, value in data["statistics"].items():
            self.create_and_add_widget_item(key, value, self.window().dht_tree_widget)

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

        try:
            open_files = my_process.open_files()
            gui_item.setText(0, "GUI (%d)" % len(open_files))
            self.window().open_files_tree_widget.addTopLevelItem(gui_item)

            for open_file in open_files:
                item = QTreeWidgetItem()
                item.setText(0, open_file.path)
                item.setText(1, "%d" % open_file.fd)
                gui_item.addChild(item)
        except psutil.AccessDenied as exc:
            gui_item.setText(0, "Unable to get open files for GUI (%s)" % exc)

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/open_files", self.on_core_open_files)

    def on_core_open_files(self, data):
        if not data:
            return
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
        if not data:
            return
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
        if not data:
            return
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

    def load_cpu_tab(self):
        if not self.initialized_cpu_plot:
            vlayout = self.window().cpu_plot_widget.layout()
            self.cpu_plot = CPUPlot(self.window().cpu_plot_widget)
            vlayout.addWidget(self.cpu_plot)
            self.initialized_cpu_plot = True

        self.refresh_cpu_plot()

        # Start timer
        self.cpu_plot_timer = QTimer()
        self.cpu_plot_timer.timeout.connect(self.load_cpu_tab)
        self.cpu_plot_timer.start(5000)

    def refresh_cpu_plot(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/cpu/history", self.on_core_cpu_history)

    def on_core_cpu_history(self, data):
        if not data:
            return

        self.cpu_plot.reset_plot()
        for cpu_info in data["cpu_history"]:
            self.cpu_plot.add_data(cpu_info["time"], [round(cpu_info["cpu"], 2)])
        self.cpu_plot.render_plot()

    def load_memory_tab(self):
        if not self.initialized_memory_plot:
            vlayout = self.window().memory_plot_widget.layout()
            self.memory_plot = MemoryPlot(self.window().memory_plot_widget)
            vlayout.addWidget(self.memory_plot)
            self.initialized_memory_plot = True

        self.refresh_memory_plot()

        # Start timer
        self.memory_plot_timer = QTimer()
        self.memory_plot_timer.timeout.connect(self.load_memory_tab)
        self.memory_plot_timer.start(5000)

    def load_profiler_tab(self):
        self.window().toggle_profiler_button.setEnabled(False)
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/profiler", self.on_profiler_info)

    def on_profiler_info(self, data):
        if not data:
            return
        self.profiler_enabled = (data["state"] == "STARTED")
        self.window().toggle_profiler_button.setEnabled(True)
        self.window().toggle_profiler_button.setText("%s profiler" %
                                                     ("Stop" if self.profiler_enabled else "Start"))

    def on_toggle_profiler_button_clicked(self):
        if self.toggling_profiler:
            return

        self.toggling_profiler = True
        self.window().toggle_profiler_button.setEnabled(False)
        self.request_mgr = TriblerRequestManager()
        method = "DELETE" if self.profiler_enabled else "PUT"
        self.request_mgr.perform_request("debug/profiler", self.on_profiler_state_changed, method=method)

    def on_profiler_state_changed(self, data):
        if not data:
            return
        self.toggling_profiler = False
        self.window().toggle_profiler_button.setEnabled(True)
        self.load_profiler_tab()

        if 'profiler_file' in data:
            QMessageBox.about(self,
                              "Profiler statistics saved",
                              "The profiler data has been saved to %s." % data['profiler_file'])

    def refresh_memory_plot(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/memory/history", self.on_core_memory_history)

    def on_core_memory_history(self, data):
        if not data:
            return
        self.memory_plot.reset_plot()
        for mem_info in data["memory_history"]:
            self.memory_plot.add_data(mem_info["time"], [round(mem_info["mem"], 2)])
        self.memory_plot.render_plot()

    def on_memory_dump_button_clicked(self, dump_core):
        self.export_dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory", "",
                                                           QFileDialog.ShowDirsOnly)

        if len(self.export_dir) > 0:
            filename = "tribler_mem_dump_%s_%s.json" % \
                       ('core' if dump_core else 'gui', datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
            if dump_core:
                self.request_mgr = TriblerRequestManager()
                self.request_mgr.download_file("debug/memory/dump",
                                               lambda data: self.on_memory_dump_data_available(filename, data))
            elif scanner:
                scanner.dump_all_objects(os.path.join(self.export_dir, filename))
            else:
                ConfirmationDialog.show_error(self.window(),
                                              "Error when performing a memory dump",
                                              "meliae memory dumper is not compatible with Python 3")

    def on_memory_dump_data_available(self, filename, data):
        if not data:
            return
        dest_path = os.path.join(self.export_dir, filename)
        try:
            memory_dump_file = open(dest_path, "wb")
            memory_dump_file.write(data)
            memory_dump_file.close()
        except IOError as exc:
            ConfirmationDialog.show_error(self.window(),
                                          "Error when exporting file",
                                          "An error occurred when exporting the torrent file: %s" % str(exc))

    def closeEvent(self, close_event):
        self.request_mgr.cancel_request()
        if self.cpu_plot_timer:
            self.cpu_plot_timer.stop()

        if self.memory_plot_timer:
            self.memory_plot_timer.stop()

    def load_logs_tab(self):
        # Max lines from GUI
        max_log_lines = self.window().max_lines_value.text()

        tab_index = self.window().log_tab_widget.currentIndex()
        tab_name = "core" if tab_index == 0 else "gui"

        self.request_mgr = TriblerRequestManager()
        request_query = "process=%s&max_lines=%s" % (tab_name, max_log_lines)
        self.request_mgr.perform_request("debug/log?%s" % request_query, self.display_logs)

    def display_logs(self, data):
        if not data:
            return
        tab_index = self.window().log_tab_widget.currentIndex()
        log_display_widget = self.window().core_log_display_area if tab_index == 0 \
            else self.window().gui_log_display_area

        log_display_widget.moveCursor(QTextCursor.End)

        key_content = u'content'
        key_max_lines = u'max_lines'

        if not key_content in data or not data[key_content]:
            log_display_widget.setPlainText('No logs found')
        else:
            log_display_widget.setPlainText(data[key_content])

        if not key_max_lines in data or not data[key_max_lines]:
            self.window().max_lines_value.setText('')
        else:
            self.window().max_lines_value.setText(str(data[key_max_lines]))

        sb = log_display_widget.verticalScrollBar()
        sb.setValue(sb.maximum())

    def show(self):
        super(DebugWindow, self).show()

        # this will remove minimized status
        # and restore window with keeping maximized/normal state
        self.window().setWindowState(self.window().windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.window().activateWindow()

    def load_libtorrent_data(self, export=False):
        tab = self.window().libtorrent_tab_widget.currentIndex()
        hop = 0 if self.window().lt_zero_hop_btn.isChecked() \
            else 1 if self.window().lt_one_hop_btn.isChecked() \
            else 2 if self.window().lt_two_hop_btn.isChecked() \
            else 3
        if tab == 0:
            self.load_libtorrent_settings_tab(hop, export=export)
        elif tab == 1:
            self.load_libtorrent_sessions_tab(hop, export=export)

    def load_libtorrent_settings_tab(self, hop, export=False):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("libtorrent/settings?hop=%d" % hop,
                                         lambda data: self.on_libtorrent_settings_received(data, export=export))
        self.window().libtorrent_settings_tree_widget.clear()

    def on_libtorrent_settings_received(self, data, export=False):
        if not data:
            return
        for key, value in data["settings"].items():
            item = QTreeWidgetItem(self.window().libtorrent_settings_tree_widget)
            item.setText(0, key)
            item.setText(1, str(value))
            self.window().libtorrent_settings_tree_widget.addTopLevelItem(item)
        if export:
            self.save_to_file("libtorrent_settings.json", data)

    def load_libtorrent_sessions_tab(self, hop, export=False):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("libtorrent/session?hop=%d" % hop,
                                         lambda data: self.on_libtorrent_session_received(data, export=export))
        self.window().libtorrent_session_tree_widget.clear()

    def on_libtorrent_session_received(self, data, export=False):
        if not data:
            return
        for key, value in data["session"].items():
            item = QTreeWidgetItem(self.window().libtorrent_session_tree_widget)
            item.setText(0, key)
            item.setText(1, str(value))
            self.window().libtorrent_session_tree_widget.addTopLevelItem(item)
        if export:
            self.save_to_file("libtorrent_session.json", data)

    def save_to_file(self, filename, data):
        base_dir = QFileDialog.getExistingDirectory(self, "Select an export directory", "", QFileDialog.ShowDirsOnly)
        if len(base_dir) > 0:
            dest_path = os.path.join(base_dir, filename)
            try:
                torrent_file = open(dest_path, "wb")
                torrent_file.write(json.dumps(data))
                torrent_file.close()
            except IOError as exc:
                ConfirmationDialog.show_error(self.window(), "Error exporting file", str(exc))
