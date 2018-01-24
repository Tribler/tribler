import os
import socket
from time import localtime, strftime

import datetime
import matplotlib
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QFileDialog, QTextEdit, QDesktopWidget
from PyQt5.QtWidgets import QSizePolicy
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from meliae import scanner
from twisted.internet.task import LoopingCall

matplotlib.use('Qt5Agg')

import psutil
from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure

import Tribler.Core.Utilities.json_util as json
from TriblerGUI.utilities import get_ui_file_path, format_size
from TriblerGUI.tribler_request_manager import performed_requests as tribler_performed_requests, TriblerRequestManager
from TriblerGUI.event_request_manager import received_events as tribler_received_events


class MplCanvas(FigureCanvas):
    """Ultimately, this is a QWidget."""

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)

        fig.set_tight_layout({"pad": 1})
        self.axes = fig.add_subplot(111)
        self.plot_data = None

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def compute_initial_figure(self):
        pass


class CPUPlotMplCanvas(MplCanvas):

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("CPU Usage (refreshes every 5 sec)", color="#e0e0e0")
        self.axes.set_xlabel("Time")
        self.axes.set_ylabel("CPU utilization (%)")

        self.axes.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

        self.axes.plot(self.plot_data[0], self.plot_data[1], label="CPU usage (core)", marker='o')
        self.axes.grid(True)

        for line in self.axes.get_xgridlines() + self.axes.get_ygridlines():
            line.set_linestyle('--')

        # Create the legend
        handles, labels = self.axes.get_legend_handles_labels()
        self.axes.legend(handles, labels)

        self.axes.set_ylim(0, 100)
        self.axes.set_xlim(self.plot_data[0][0] - datetime.timedelta(seconds=10),
                           self.plot_data[0][0] + datetime.timedelta(seconds=100))

        self.draw()


class MemoryPlotMplCanvas(MplCanvas):

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("Memory Usage (refreshes every 5 sec)", color="#e0e0e0")
        self.axes.set_xlabel("Time")
        self.axes.set_ylabel("Memory usage (MB)")

        self.axes.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

        self.axes.plot(self.plot_data[0], self.plot_data[1], label="Memory usage (core)", marker='o')
        self.axes.grid(True)

        for line in self.axes.get_xgridlines() + self.axes.get_ygridlines():
            line.set_linestyle('--')

        # Create the legend
        handles, labels = self.axes.get_legend_handles_labels()
        self.axes.legend(handles, labels)

        self.axes.set_xlim(self.plot_data[0][0] - datetime.timedelta(seconds=10),
                           self.plot_data[0][0] + datetime.timedelta(seconds=100))

        self.draw()


class DebugWindow(QMainWindow):
    """
    The debug window shows various statistics about Tribler such as performed requests, Dispersy statistics and
    community information.
    """

    def __init__(self, settings):
        QMainWindow.__init__(self)

        self.request_mgr = None
        self.cpu_plot = None
        self.memory_plot = None
        self.initialized_cpu_plot = False
        self.initialized_memory_plot = False
        self.cpu_plot_timer = None
        self.memory_plot_timer = None

        uic.loadUi(get_ui_file_path('debugwindow.ui'), self)
        self.setWindowTitle("Tribler debug pane")

        self.window().dump_memory_core_button.clicked.connect(lambda: self.on_memory_dump_button_clicked(True))
        self.window().dump_memory_gui_button.clicked.connect(lambda: self.on_memory_dump_button_clicked(False))

        self.window().debug_tab_widget.setCurrentIndex(0)
        self.window().dispersy_tab_widget.setCurrentIndex(0)
        self.window().system_tab_widget.setCurrentIndex(0)
        self.window().debug_tab_widget.currentChanged.connect(self.tab_changed)
        self.window().dispersy_tab_widget.currentChanged.connect(self.dispersy_tab_changed)
        self.window().events_tree_widget.itemClicked.connect(self.on_event_clicked)
        self.window().system_tab_widget.currentChanged.connect(self.system_tab_changed)
        self.load_general_tab()

        self.window().open_files_tree_widget.header().setSectionResizeMode(0, QHeaderView.Stretch)

        if settings and settings['trustchain']['enabled']:
            self.window().debug_tab_widget.setTabEnabled(2, False)

        # Refresh logs
        self.window().log_refresh_button.clicked.connect(lambda: self.load_logs_tab())
        self.window().log_tab_widget.currentChanged.connect(lambda index: self.load_logs_tab())

        # Position to center
        frame_geometry = self.frameGeometry()
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center_point = QDesktopWidget().screenGeometry(screen).center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

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
        elif index == 6:
            self.load_logs_tab()

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
        elif index == 3:
            self.load_cpu_tab()
        elif index == 4:
            self.load_memory_tab()

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
        for endpoint, method, data, timestamp, status_code in sorted(tribler_performed_requests,
                                                                     key=lambda x: x[3]):
            item = QTreeWidgetItem(self.window().requests_tree_widget)
            item.setText(0, "%s %s %s" % (method, endpoint, data))
            item.setText(1, ("%d" % status_code()) if status_code() else "unknown")
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

    def load_cpu_tab(self):
        if not self.initialized_cpu_plot:
            vlayout = self.window().cpu_plot_widget.layout()
            self.cpu_plot = CPUPlotMplCanvas(self.window().cpu_plot_widget, dpi=100)
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
        plot_data = [[], []]
        for cpu_info in data["cpu_history"]:
            if cpu_info["cpu"] == 0.0:
                continue  # Ignore the initial measurement, is always zero
            plot_data[0].append(datetime.datetime.fromtimestamp(cpu_info["time"]))
            plot_data[1].append(cpu_info["cpu"])

        if len(plot_data[0]) == 0:
            plot_data = [[datetime.datetime.now()], [0]]

        self.cpu_plot.plot_data = plot_data
        self.cpu_plot.compute_initial_figure()

    def load_memory_tab(self):
        if not self.initialized_memory_plot:
            vlayout = self.window().memory_plot_widget.layout()
            self.memory_plot = MemoryPlotMplCanvas(self.window().memory_plot_widget, dpi=100)
            vlayout.addWidget(self.memory_plot)
            self.initialized_memory_plot = True

        self.refresh_memory_plot()

        # Start timer
        self.memory_plot_timer = QTimer()
        self.memory_plot_timer.timeout.connect(self.load_memory_tab)
        self.memory_plot_timer.start(5000)

    def refresh_memory_plot(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("debug/memory/history", self.on_core_memory_history)

    def on_core_memory_history(self, data):
        plot_data = [[], []]
        for mem_info in data["memory_history"]:
            plot_data[0].append(datetime.datetime.fromtimestamp(mem_info["time"]))
            plot_data[1].append(mem_info["mem"] / 1024 / 1024)

        if len(plot_data[0]) == 0:
            plot_data = [[datetime.datetime.now()], [0]]

        self.memory_plot.plot_data = plot_data
        self.memory_plot.compute_initial_figure()

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
            else:
                scanner.dump_all_objects(os.path.join(self.export_dir, filename))

    def on_memory_dump_data_available(self, filename, data):
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
