import datetime
import json
import logging
import os
import socket
import sys
from binascii import unhexlify
from time import localtime, strftime, time
from typing import Dict

from PyQt5 import QtGui, uic
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QTextCursor
from PyQt5.QtWidgets import QDesktopWidget, QFileDialog, QHeaderView, QMainWindow, QMessageBox, QTreeWidgetItem

import libtorrent

import psutil

from tribler_core.utilities.utilities import has_bep33_support

from tribler_gui.defs import DEBUG_PANE_REFRESH_TIMEOUT, GB, MB
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.event_request_manager import received_events as tribler_received_events
from tribler_gui.resource_monitor import GuiResourceMonitor
from tribler_gui.tribler_request_manager import TriblerNetworkRequest, performed_requests as tribler_performed_requests
from tribler_gui.utilities import connect, format_size, get_ui_file_path
from tribler_gui.widgets.graphs.timeseriesplot import TimeSeriesPlot
from tribler_gui.widgets.ipv8health import MonitorWidget

COLOR_RGB_BLUE = (0, 153, 255)
COLOR_WHITE_HEX = "#FFFFFF"


class MemoryPlot(TimeSeriesPlot):
    def __init__(self, parent, process='CPU', **kargs):
        series = [
            {'name': f'Memory ({process})', 'pen': COLOR_RGB_BLUE, 'symbolBrush': COLOR_RGB_BLUE, 'symbolPen': 'w'}
        ]
        super().__init__(parent, f'Memory Usage({process})', series, **kargs)
        self.setBackground(COLOR_WHITE_HEX)
        self.setLabel('left', 'Memory', units='MB')
        self.setLimits(yMin=0, yMax=2 * GB)


class CPUPlot(TimeSeriesPlot):
    def __init__(self, parent, process='Core', **kargs):
        series = [{'name': f'CPU ({process})', 'pen': COLOR_RGB_BLUE, 'symbolBrush': COLOR_RGB_BLUE, 'symbolPen': 'w'}]
        super().__init__(parent, f'CPU Usage ({process})', series, **kargs)
        self.setBackground(COLOR_WHITE_HEX)
        self.setLabel('left', 'CPU', units='%')
        self.setLimits(yMin=-10, yMax=200)


class DebugWindow(QMainWindow):
    """
    The debug window shows various statistics about Tribler such as performed requests, IPv8 statistics and
    community information.
    """

    resize_event = pyqtSignal()

    def __init__(self, settings, gui_settings, tribler_version):
        self._logger = logging.getLogger(self.__class__.__name__)
        QMainWindow.__init__(self)

        self.core_cpu_plot = None
        self.gui_cpu_plot = None
        self.initialized_cpu_plot = False
        self.cpu_plot_timer = None

        self.core_memory_plot = None
        self.gui_memory_plot = None
        self.initialized_memory_plot = False
        self.memory_plot_timer = None

        self.tribler_version = tribler_version
        self.profiler_enabled = False
        self.toggling_profiler = False

        uic.loadUi(get_ui_file_path('debugwindow.ui'), self)
        self.setWindowTitle("Tribler debug pane")

        connect(self.window().toggle_profiler_button.clicked, self.on_toggle_profiler_button_clicked)

        self.window().debug_tab_widget.setCurrentIndex(0)
        self.window().ipv8_tab_widget.setCurrentIndex(0)
        self.window().tunnel_tab_widget.setCurrentIndex(0)
        self.window().dht_tab_widget.setCurrentIndex(0)
        self.window().system_tab_widget.setCurrentIndex(0)
        connect(self.window().debug_tab_widget.currentChanged, self.tab_changed)
        connect(self.window().ipv8_tab_widget.currentChanged, self.ipv8_tab_changed)
        connect(self.window().communities_tree_widget.itemClicked, self.on_community_clicked)
        connect(self.window().tunnel_tab_widget.currentChanged, self.tunnel_tab_changed)
        connect(self.window().dht_tab_widget.currentChanged, self.dht_tab_changed)
        connect(self.window().events_tree_widget.itemClicked, self.on_event_clicked)
        connect(self.window().system_tab_widget.currentChanged, self.system_tab_changed)
        self.load_general_tab()

        self.window().open_files_tree_widget.header().setSectionResizeMode(0, QHeaderView.Stretch)

        self.window().community_peers_tree_widget.hide()

        # Enable/disable tabs, based on settings
        self.window().debug_tab_widget.setTabEnabled(2, settings is not None)
        self.window().debug_tab_widget.setTabEnabled(3, settings and settings['ipv8']['enabled'])
        self.window().system_tab_widget.setTabEnabled(3, settings and settings['resource_monitor']['enabled'])
        self.window().system_tab_widget.setTabEnabled(4, settings and settings['resource_monitor']['enabled'])

        # Refresh logs
        connect(self.window().log_refresh_button.clicked, lambda _: self.load_logs_tab())
        connect(self.window().log_tab_widget.currentChanged, lambda index: self.load_logs_tab())

        # IPv8 statistics enabled?
        self.ipv8_statistics_enabled = settings['ipv8']['statistics']

        # Libtorrent tab
        self.init_libtorrent_tab()

        # Channels tab
        connect(self.window().channels_tab_widget.currentChanged, self.channels_tab_changed)
        self.window().channels_tab_widget.setCurrentIndex(0)

        # Position to center
        frame_geometry = self.frameGeometry()
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center_point = QDesktopWidget().screenGeometry(screen).center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

        # Refresh timer
        self.refresh_timer = None
        self.rest_request = None
        self.ipv8_health_widget = None

        # GUI resource monitor
        self.resource_monitor = GuiResourceMonitor()
        self.resource_monitor.start()

        # QT settings
        self.gui_settings = gui_settings

    def hideEvent(self, hide_event):
        self.stop_timer()
        self.hide_ipv8_health_widget()

    def showEvent(self, show_event):
        if self.ipv8_health_widget and self.ipv8_health_widget.isVisible():
            self.ipv8_health_widget.resume()
            TriblerNetworkRequest(
                "ipv8/asyncio/drift", self.on_ipv8_health_enabled, data={"enable": True}, method='PUT'
            )

    def run_with_timer(self, call_fn, timeout=DEBUG_PANE_REFRESH_TIMEOUT):
        call_fn()
        self.stop_timer()
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        connect(
            self.refresh_timer.timeout,
            lambda _call_fn=call_fn, _timeout=timeout: self.run_with_timer(_call_fn, timeout=_timeout),
        )
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
        connect(self.window().libtorrent_tab_widget.currentChanged, lambda _: self.load_libtorrent_data(export=False))

        connect(self.window().lt_zero_hop_btn.clicked, lambda _: self.load_libtorrent_data(export=False))
        connect(self.window().lt_one_hop_btn.clicked, lambda _: self.load_libtorrent_data(export=False))
        connect(self.window().lt_two_hop_btn.clicked, lambda _: self.load_libtorrent_data(export=False))
        connect(self.window().lt_three_hop_btn.clicked, lambda _: self.load_libtorrent_data(export=False))
        connect(self.window().lt_export_btn.clicked, lambda _: self.load_libtorrent_data(export=True))

        self.window().lt_zero_hop_btn.setChecked(True)

    def tab_changed(self, index):
        if index == 0:
            self.load_general_tab()
        elif index == 1:
            self.load_requests_tab()
        elif index == 2:
            self.run_with_timer(self.load_bandwidth_accounting_tab)
        elif index == 3:
            self.ipv8_tab_changed(self.window().ipv8_tab_widget.currentIndex())
        elif index == 4:
            self.tunnel_tab_changed(self.window().tunnel_tab_widget.currentIndex())
        elif index == 5:
            self.dht_tab_changed(self.window().dht_tab_widget.currentIndex())
        elif index == 6:
            self.run_with_timer(self.load_events_tab)
        elif index == 7:
            self.system_tab_changed(self.window().system_tab_widget.currentIndex())
        elif index == 8:
            self.load_libtorrent_data()
        elif index == 9:
            self.load_logs_tab()
        elif index == 10:
            self.channels_tab_changed(self.window().channels_tab_widget.currentIndex())

    def ipv8_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_ipv8_general_tab)
        elif index == 1:
            self.run_with_timer(self.load_ipv8_communities_tab)
        elif index == 2:
            self.run_with_timer(self.load_ipv8_community_details_tab)
        elif index == 3:
            self.run_with_timer(self.load_ipv8_health_monitor)

    def tunnel_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_tunnel_circuits_tab)
        elif index == 1:
            self.run_with_timer(self.load_tunnel_relays_tab)
        elif index == 2:
            self.run_with_timer(self.load_tunnel_exits_tab)
        elif index == 3:
            self.run_with_timer(self.load_tunnel_swarms_tab)
        elif index == 4:
            self.run_with_timer(self.load_tunnel_peers_tab)

    def dht_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_dht_statistics_tab)
        elif index == 1:
            self.run_with_timer(self.load_dht_buckets_tab)

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
        item.setText(1, f"{value}")
        widget.addTopLevelItem(item)

    def load_general_tab(self):
        TriblerNetworkRequest("statistics/tribler", self.on_tribler_statistics)

    def on_tribler_statistics(self, data):
        if not data:
            return
        data = data["tribler_statistics"]
        self.window().general_tree_widget.clear()
        self.create_and_add_widget_item("Tribler version", self.tribler_version, self.window().general_tree_widget)
        self.create_and_add_widget_item(
            "Python version", sys.version.replace('\n', ''), self.window().general_tree_widget  # to fit in one line
        )
        self.create_and_add_widget_item("Libtorrent version", libtorrent.version, self.window().general_tree_widget)
        self.create_and_add_widget_item("BEP33 support", has_bep33_support(), self.window().general_tree_widget)
        self.create_and_add_widget_item("", "", self.window().general_tree_widget)

        self.create_and_add_widget_item("Number of channels", data["num_channels"], self.window().general_tree_widget)
        self.create_and_add_widget_item(
            "Database size", format_size(data["db_size"]), self.window().general_tree_widget
        )
        self.create_and_add_widget_item(
            "Number of known torrents", data["num_torrents"], self.window().general_tree_widget
        )
        self.create_and_add_widget_item("", "", self.window().general_tree_widget)

        disk_usage = psutil.disk_usage('/')
        self.create_and_add_widget_item(
            "Total disk space", format_size(disk_usage.total), self.window().general_tree_widget
        )
        self.create_and_add_widget_item(
            "Used disk space", format_size(disk_usage.used), self.window().general_tree_widget
        )
        self.create_and_add_widget_item(
            "Free disk space", format_size(disk_usage.free), self.window().general_tree_widget
        )

        # Show GUI settings
        self.show_gui_settings()

    def show_gui_settings(self):
        # Empty line at the beginning
        self.create_and_add_widget_item("", "", self.window().general_tree_widget)
        # Heading: GUI Settings
        self.create_and_add_widget_item("GUI Settings:", "", self.window().general_tree_widget)
        # Location of the settings file
        self.create_and_add_widget_item("Qt file", self.gui_settings.fileName(), self.window().general_tree_widget)

        selected_settings = {
            "api_key": lambda val: val.decode('utf-8'),
            "api_port": lambda val: val,
            "pos": lambda val: f"(x : {val.x()} px,  y : {val.y()} px)",
            "size": lambda val: f"(width : {val.width()} px,  height : {val.height()} px)",
            "ask_download_settings": lambda val: val,
            "autocommit_enabled": lambda val: val,
            "debug": lambda val: val,
            "family_filter": lambda val: val,
            "first_discover": lambda val: val,
            "use_monochrome_icon": lambda val: val,
            "recent_download_locations": lambda val: [unhexlify(url).decode('utf-8') for url in val.split(",")],
        }

        # List only selected gui settings
        for key in self.gui_settings.allKeys():
            if key in selected_settings:
                value = selected_settings[key](self.gui_settings.value(key, 'N/A'))
                self.create_and_add_widget_item(key, value, self.window().general_tree_widget)

    def load_requests_tab(self):
        self.window().requests_tree_widget.clear()
        for request, status_code in sorted(tribler_performed_requests, key=lambda rq: rq[0].time):
            endpoint = request.url
            method = request.method
            data = request.raw_data
            timestamp = request.time

            item = QTreeWidgetItem(self.window().requests_tree_widget)
            item.setText(0, f"{method} {repr(endpoint)} {repr(data)}")
            item.setText(1, ("%d" % status_code) if status_code else "unknown")
            item.setText(2, f"{strftime('%H:%M:%S', localtime(timestamp))}")
            self.window().requests_tree_widget.addTopLevelItem(item)

    def load_bandwidth_accounting_tab(self) -> None:
        """
        Initiate a request to the Tribler core to fetch statistics on bandwidth accounting.
        """
        TriblerNetworkRequest("bandwidth/statistics", self.on_bandwidth_statistics)

    def on_bandwidth_statistics(self, data: Dict) -> None:
        """
        We received bandwidth statistics from the core.
        :param data: The bandwidth statistics, in JSON format.
        """
        if not data:
            return
        self.window().bandwidth_tree_widget.clear()
        for key, value in data["statistics"].items():
            self.create_and_add_widget_item(key, value, self.window().bandwidth_tree_widget)

    def load_ipv8_general_tab(self):
        TriblerNetworkRequest("statistics/ipv8", self.on_ipv8_general_stats)

    def on_ipv8_general_stats(self, data):
        if not data:
            return
        self.window().ipv8_general_tree_widget.clear()
        for key, value in data["ipv8_statistics"].items():
            if key in ('total_up', 'total_down'):
                value = f"{value / (1024.0 * 1024.0):.2f} MB"
            elif key == 'session_uptime':
                value = f"{str(datetime.timedelta(seconds=int(value)))}"
            self.create_and_add_widget_item(key, value, self.window().ipv8_general_tree_widget)

    def load_ipv8_communities_tab(self):
        TriblerNetworkRequest("ipv8/overlays", self.on_ipv8_community_stats)

    def _colored_peer_count(self, peer_count, max_peers):
        limits = [20, max_peers + 1]
        color = 0xF4D03F if peer_count < limits[0] else (0x56F129 if peer_count < limits[1] else 0xF12929)
        return QBrush(QColor(color))

    def on_ipv8_community_stats(self, data):
        if not data:
            return

        for overlay in data["overlays"]:
            item = None
            item_exists = False

            # Check if this item is already rendered
            for ind in range(self.window().communities_tree_widget.topLevelItemCount()):
                existing_item = self.window().communities_tree_widget.topLevelItem(ind)
                if existing_item.data(0, Qt.UserRole)["id"] == overlay["id"]:
                    item = existing_item
                    item_exists = True
                    break

            if not item:
                # Create a new one
                item = QTreeWidgetItem(self.window().communities_tree_widget)

            item.setData(0, Qt.UserRole, overlay)
            item.setText(0, overlay["overlay_name"])
            item.setText(1, overlay["id"][:10])
            item.setText(2, overlay["my_peer"][-12:])
            peer_count = len(overlay["peers"])
            item.setText(3, f"{peer_count}")
            item.setForeground(3, self._colored_peer_count(peer_count, overlay["max_peers"]))

            if "statistics" in overlay and overlay["statistics"]:
                statistics = overlay["statistics"]
                item.setText(4, f"{statistics['bytes_up'] / (1024.0 * 1024.0):.3f}")
                item.setText(5, f"{statistics['bytes_down'] / (1024.0 * 1024.0):.3f}")
                item.setText(6, f"{statistics['num_up']}")
                item.setText(7, f"{statistics['num_down']}")
                item.setText(8, f"{statistics['diff_time']:.3f}")
            else:
                item.setText(4, "N/A")
                item.setText(5, "N/A")
                item.setText(6, "N/A")
                item.setText(7, "N/A")
                item.setText(8, "N/A")

            if not item_exists:
                self.window().communities_tree_widget.addTopLevelItem(item)
            map(self.window().communities_tree_widget.resizeColumnToContents, range(10))

        # Reload the window with peers
        selected_items = self.window().communities_tree_widget.selectedItems()
        if len(selected_items) > 0:
            self.update_community_peers(selected_items[0])

    def on_community_clicked(self, item, _):
        self.window().community_peers_tree_widget.show()
        self.update_community_peers(item)

    def update_community_peers(self, item):
        self.window().community_peers_tree_widget.clear()
        peers_info = item.data(0, Qt.UserRole)["peers"]

        for peer_info in peers_info:
            item = QTreeWidgetItem(self.window().community_peers_tree_widget)
            item.setText(0, peer_info["ip"])
            item.setText(1, f"{peer_info['port']}")
            item.setText(2, peer_info["public_key"])
            self.window().community_peers_tree_widget.addTopLevelItem(item)

    def load_ipv8_community_details_tab(self):
        if self.ipv8_statistics_enabled:
            self.window().ipv8_statistics_error_label.setHidden(True)
            TriblerNetworkRequest("ipv8/overlays/statistics", self.on_ipv8_community_detail_stats)
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
                    stat_item.setText(1, f"{stat['bytes_up'] / (1024.0 * 1024.0):.3f}")
                    stat_item.setText(2, f"{stat['bytes_down'] / (1024.0 * 1024.0):.3f}")
                    stat_item.setText(3, f"{stat['num_up']}")
                    stat_item.setText(4, f"{stat['num_down']}")
                    self.window().ipv8_communities_details_widget.addTopLevelItem(stat_item)

    def load_ipv8_health_monitor(self):
        """
        Lazy load and enable the IPv8 core health monitor.
        """
        if self.ipv8_health_widget is None:
            # Add the core monitor widget to the tab widget.
            from PyQt5.QtWidgets import QVBoxLayout

            widget = MonitorWidget()
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            self.window().ipv8_health_monitor_widget.setLayout(layout)
            self.window().ipv8_health_monitor_widget.show()
            self.ipv8_health_widget = widget
        else:
            # We already loaded the widget, just resume it.
            self.ipv8_health_widget.resume()
        # Whether the widget is newly loaded or not, start the measurements.
        TriblerNetworkRequest("ipv8/asyncio/drift", self.on_ipv8_health_enabled, data={"enable": True}, method='PUT')

    def hide_ipv8_health_widget(self):
        """
        We need to hide the IPv8 health widget, involving two things:

         1. Stop the smooth graphical updates in the widget.
         2. Remove the observer from the IPv8 core.
        """
        if self.ipv8_health_widget is not None and not self.ipv8_health_widget.is_paused:
            self.ipv8_health_widget.pause()
            TriblerNetworkRequest("ipv8/asyncio/drift", lambda _: None, data={"enable": False}, method='PUT')

    def on_ipv8_health(self, data):
        """
        Measurements came in, send them to the widget for "plotting".
        """
        if not data or 'measurements' not in data or self.ipv8_health_widget is None:
            return
        self.ipv8_health_widget.set_history(data['measurements'])

    def on_ipv8_health_enabled(self, data):
        """
        The request to enable IPv8 completed.

        Start requesting measurements.
        """
        if not data:
            return
        self.run_with_timer(lambda: TriblerNetworkRequest("ipv8/asyncio/drift", self.on_ipv8_health), 100)

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
        self.window().circuits_tree_widget.setColumnWidth(3, 200)
        TriblerNetworkRequest("ipv8/tunnel/circuits", self.on_tunnel_circuits)

    def on_tunnel_circuits(self, circuits):
        if not circuits:
            return

        for c in circuits["circuits"]:
            c["hops"] = f"{c['goal_hops']} / {c['goal_hops']}"
            c["exit_flags"] = c["exit_flags"] if c["state"] == "READY" else ""

        self.add_items_to_tree(
            self.window().circuits_tree_widget,
            circuits.get("circuits"),
            ["circuit_id", "hops", "type", "state", "bytes_up", "bytes_down", "creation_time", "exit_flags"],
        )

    def load_tunnel_relays_tab(self):
        TriblerNetworkRequest("ipv8/tunnel/relays", self.on_tunnel_relays)

    def on_tunnel_relays(self, data):
        if data:
            self.add_items_to_tree(
                self.window().relays_tree_widget,
                data["relays"],
                ["circuit_from", "circuit_to", "is_rendezvous", "bytes_up", "bytes_down", "creation_time"],
            )

    def load_tunnel_exits_tab(self):
        TriblerNetworkRequest("ipv8/tunnel/exits", self.on_tunnel_exits)

    def on_tunnel_exits(self, data):
        if data:
            self.add_items_to_tree(
                self.window().exits_tree_widget,
                data["exits"],
                ["circuit_from", "enabled", "bytes_up", "bytes_down", "creation_time"],
            )

    def load_tunnel_swarms_tab(self):
        TriblerNetworkRequest("ipv8/tunnel/swarms", self.on_tunnel_swarms)

    def on_tunnel_swarms(self, data):
        if data:
            self.add_items_to_tree(
                self.window().swarms_tree_widget,
                data.get("swarms"),
                [
                    "info_hash",
                    "num_seeders",
                    "num_connections",
                    "num_connections_incomplete",
                    "seeding",
                    "last_lookup",
                    "bytes_up",
                    "bytes_down",
                ],
            )

    def load_tunnel_peers_tab(self):
        self.window().peers_tree_widget.setColumnWidth(2, 300)
        TriblerNetworkRequest("ipv8/tunnel/peers", self.on_tunnel_peers)

    def on_tunnel_peers(self, data):
        if data:
            self.add_items_to_tree(
                self.window().peers_tree_widget, data.get("peers"), ["ip", "port", "mid", "is_key_compatible", "flags"]
            )

    def load_dht_statistics_tab(self):
        TriblerNetworkRequest("ipv8/dht/statistics", self.on_dht_statistics)

    def on_dht_statistics(self, data):
        if not data:
            return
        self.window().dhtstats_tree_widget.clear()
        for key, value in data["statistics"].items():
            self.create_and_add_widget_item(key, value, self.window().dhtstats_tree_widget)

    def load_dht_buckets_tab(self):
        TriblerNetworkRequest("ipv8/dht/buckets", self.on_dht_buckets)

    def on_dht_buckets(self, data):
        if data:
            for bucket in data["buckets"]:
                bucket["num_peers"] = len(bucket["peers"])
                ts = bucket["last_changed"]
                bucket["last_changed"] = str(datetime.timedelta(seconds=int(time() - ts))) if ts > 0 else '-'
            self.add_items_to_tree(
                self.window().buckets_tree_widget,
                data.get("buckets"),
                ["prefix", "last_changed", "num_peers"],
            )

    def on_event_clicked(self, item, _):
        event_dict = item.data(0, Qt.UserRole)
        self.window().event_text_box.setPlainText(json.dumps(event_dict))

    def load_events_tab(self):
        self.window().events_tree_widget.clear()
        for event_dict, timestamp in tribler_received_events:
            item = QTreeWidgetItem(self.window().events_tree_widget)
            item.setData(0, Qt.UserRole, event_dict)
            item.setText(0, f"{event_dict['type']}")
            item.setText(1, f"{strftime('%H:%M:%S', localtime(timestamp))}")
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
            gui_item.setText(0, f"Unable to get open files for GUI ({exc})")

        TriblerNetworkRequest("debug/open_files", self.on_core_open_files)

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
        TriblerNetworkRequest("debug/open_sockets", self.on_core_open_sockets)

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
        TriblerNetworkRequest("debug/threads", self.on_core_threads)

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
            self.core_cpu_plot = CPUPlot(self.window().tab_system_cpu, process='Core')
            self.gui_cpu_plot = CPUPlot(self.window().tab_system_cpu, process='GUI')

            vlayout = self.window().system_cpu_layout.layout()
            vlayout.addWidget(self.core_cpu_plot)
            vlayout.addWidget(self.gui_cpu_plot)

            self.initialized_cpu_plot = True

        self.refresh_cpu_plot()

        # Start timer
        self.cpu_plot_timer = QTimer()
        connect(self.cpu_plot_timer.timeout, self.load_cpu_tab)
        self.cpu_plot_timer.start(5000)

    def refresh_cpu_plot(self):
        # To update the core CPU graph, call Debug REST API to get the history
        # and update the CPU graph after receiving the response.
        TriblerNetworkRequest("debug/cpu/history", self.on_core_cpu_history)

        # GUI CPU graph can be simply updated using the data from GuiResourceMonitor object.
        self._update_cpu_graph(self.gui_cpu_plot, self.resource_monitor.get_cpu_history_dict())

    def on_core_cpu_history(self, data):
        if not data or "cpu_history" not in data:
            return

        self._update_cpu_graph(self.core_cpu_plot, data['cpu_history'])

    def _update_cpu_graph(self, cpu_graph, history_data):
        cpu_graph.reset_plot()
        for cpu_info in history_data:
            process_cpu = [round(cpu_info["cpu"], 2)]
            cpu_graph.add_data(cpu_info["time"], process_cpu)
        cpu_graph.render_plot()

    def load_memory_tab(self):
        if not self.initialized_memory_plot:
            self.core_memory_plot = MemoryPlot(self.window().tab_system_memory, process='Core')
            self.gui_memory_plot = MemoryPlot(self.window().tab_system_memory, process='GUI')

            vlayout = self.window().system_memory_layout.layout()
            vlayout.addWidget(self.core_memory_plot)
            vlayout.addWidget(self.gui_memory_plot)

            self.initialized_memory_plot = True

        self.refresh_memory_plot()

        # Start timer
        self.memory_plot_timer = QTimer()
        connect(self.memory_plot_timer.timeout, self.load_memory_tab)
        self.memory_plot_timer.start(5000)

    def load_profiler_tab(self):
        self.window().toggle_profiler_button.setEnabled(False)
        TriblerNetworkRequest("debug/profiler", self.on_profiler_info)

    def on_profiler_info(self, data):
        if not data:
            return
        self.window().toggle_profiler_button.setEnabled(True)
        self.profiler_enabled = data["state"] == "STARTED"
        self.window().toggle_profiler_button.setText(f"{'Stop' if self.profiler_enabled else 'Start'} profiler")

    def on_toggle_profiler_button_clicked(self, checked=False):
        if self.toggling_profiler:
            return

        self.toggling_profiler = True
        self.window().toggle_profiler_button.setEnabled(False)
        method = "DELETE" if self.profiler_enabled else "PUT"
        TriblerNetworkRequest("debug/profiler", self.on_profiler_state_changed, method=method)

    def on_profiler_state_changed(self, data):
        if not data:
            return
        self.toggling_profiler = False
        self.window().toggle_profiler_button.setEnabled(True)
        self.load_profiler_tab()

        if 'profiler_file' in data:
            QMessageBox.about(
                self, "Profiler statistics saved", f"The profiler data has been saved to {data['profiler_file']}."
            )

    def refresh_memory_plot(self):
        # To update the core memory graph, call Debug REST API to get the history
        # and update the memory graph after receiving the response.
        TriblerNetworkRequest("debug/memory/history", self.on_core_memory_history)

        # GUI memory graph can be simply updated using the data from GuiResourceMonitor object.
        self._update_memory_graph(self.gui_memory_plot, self.resource_monitor.get_memory_history_dict())

    def on_core_memory_history(self, data):
        if not data or data.get("memory_history") is None:
            return
        self._update_memory_graph(self.core_memory_plot, data["memory_history"])

    def _update_memory_graph(self, memory_graph, history_data):
        memory_graph.reset_plot()
        for mem_info in history_data:
            process_memory = round(mem_info["mem"] / MB, 2)
            memory_graph.add_data(mem_info["time"], [process_memory])
        memory_graph.render_plot()

    def on_memory_dump_data_available(self, filename, data):
        if not data:
            return
        dest_path = os.path.join(self.export_dir, filename)
        try:
            with open(dest_path, "wb") as memory_dump_file:
                memory_dump_file.write(data)
        except OSError as exc:
            ConfirmationDialog.show_error(
                self.window(),
                "Error when exporting file",
                f"An error occurred when exporting the torrent file: {str(exc)}",
            )

    def closeEvent(self, close_event):
        if self.rest_request:
            self.rest_request.cancel_request()
        if self.cpu_plot_timer:
            self.cpu_plot_timer.stop()

        if self.memory_plot_timer:
            self.memory_plot_timer.stop()

    def load_logs_tab(self):
        # Max lines from GUI
        max_log_lines = self.window().max_lines_value.text()

        tab_index = self.window().log_tab_widget.currentIndex()
        tab_name = "core" if tab_index == 0 else "gui"

        request_query = f"process={tab_name}&max_lines={max_log_lines}"
        TriblerNetworkRequest(f"debug/log?{request_query}", self.display_logs)

    def display_logs(self, data):
        if not data:
            return
        tab_index = self.window().log_tab_widget.currentIndex()
        log_display_widget = (
            self.window().core_log_display_area if tab_index == 0 else self.window().gui_log_display_area
        )

        log_display_widget.moveCursor(QTextCursor.End)

        key_content = 'content'
        key_max_lines = 'max_lines'

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
        super().show()

        # this will remove minimized status
        # and restore window with keeping maximized/normal state
        self.window().setWindowState(self.window().windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.window().activateWindow()

    def load_libtorrent_data(self, export=False):
        tab = self.window().libtorrent_tab_widget.currentIndex()
        hop = (
            0
            if self.window().lt_zero_hop_btn.isChecked()
            else 1
            if self.window().lt_one_hop_btn.isChecked()
            else 2
            if self.window().lt_two_hop_btn.isChecked()
            else 3
        )
        if tab == 0:
            self.load_libtorrent_settings_tab(hop, export=export)
        elif tab == 1:
            self.load_libtorrent_sessions_tab(hop, export=export)

    def load_libtorrent_settings_tab(self, hop, export=False):
        TriblerNetworkRequest(
            "libtorrent/settings?hop=%d" % hop, lambda data: self.on_libtorrent_settings_received(data, export=export)
        )
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
        TriblerNetworkRequest(
            "libtorrent/session?hop=%d" % hop, lambda data: self.on_libtorrent_session_received(data, export=export)
        )
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
                with open(dest_path, "w") as torrent_file:
                    torrent_file.write(json.dumps(data))
            except OSError as exc:
                ConfirmationDialog.show_error(self.window(), "Error exporting file", str(exc))

    def on_channels_peers(self, data):
        widget = self.window().channels_peers_tree_widget
        widget.clear()
        if not data:
            return

        for c in data["channels_list"]:
            channel_item = QTreeWidgetItem()
            channel_item.setText(0, str(c["channel_name"]))
            channel_item.setText(1, str(c["channel_pk"]))
            channel_item.setText(2, str(c["channel_id"]))
            channel_item.setData(3, Qt.DisplayRole, len(c["peers"]))  #  Peers count
            for p in c["peers"]:
                peer_item = QTreeWidgetItem()
                peer_item.setText(1, str(p[0]))  # Peer mid
                peer_item.setData(4, Qt.DisplayRole, p[1])  # Peer age
                channel_item.addChild(peer_item)
            widget.addTopLevelItem(channel_item)

    def load_channels_peers_tab(self):
        TriblerNetworkRequest("remote_query/channels_peers", self.on_channels_peers)

    def channels_tab_changed(self, index):
        if index == 0:
            self.run_with_timer(self.load_channels_peers_tab)
        elif index == 1:
            pass
