from __future__ import absolute_import
from __future__ import division

import datetime
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSizePolicy, QWidget

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, get_image_path

matplotlib.use('Qt5Agg')


class TokenMiningPlotMplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.set_facecolor("#00000000")

        fig.set_tight_layout({"pad": 1})
        self.axes = fig.add_subplot(111)
        self.plot_data = [[[0], [0]], [datetime.datetime.now()]]

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.compute_initial_figure()

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("Token Mining stats of the current session", color="#e0e0e0")
        self.axes.set_xlabel("Date")
        self.axes.set_ylabel("Mined Data (MB)")

        self.axes.xaxis.set_major_formatter(DateFormatter('%y-%m-%d'))

        self.axes.plot(self.plot_data[1], self.plot_data[0][0], label="Upload(MB)", marker='o')
        self.axes.plot(self.plot_data[1], self.plot_data[0][1], label="Download(MB)", marker='o')
        self.axes.grid(True)

        for line in self.axes.get_xgridlines() + self.axes.get_ygridlines():
            line.set_linestyle('--')

        # Color the axes
        if hasattr(self.axes, 'set_facecolor'):  # Not available on Linux
            self.axes.set_facecolor('#464646')
        self.axes.xaxis.label.set_color('#e0e0e0')
        self.axes.yaxis.label.set_color('#e0e0e0')
        self.axes.tick_params(axis='x', colors='#e0e0e0')
        self.axes.tick_params(axis='y', colors='#e0e0e0')

        # Create the legend
        handles, labels = self.axes.get_legend_handles_labels()
        self.axes.legend(handles, labels)

        if len(self.plot_data[0][0]) == 1:  # If we only have one data point, don't show negative axis
            self.axes.set_ylim(-0.3, 10)
            self.axes.set_xlim(datetime.datetime.now() - datetime.timedelta(hours=1),
                               datetime.datetime.now() + datetime.timedelta(days=4))
        self.draw()


class TokenMiningPage(QWidget):
    """
    This page shows various trust statistics.
    """
    REFRESH_INTERVAL_MS = 10000
    TIMEOUT_INTERVAL_MS = 30000

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.public_key = None
        self.request_mgr = None
        self.blocks = None
        self.byte_scale = 1024 * 1024
        self.dialog = None

        # Timer for garbage collection
        self.gc_timer = 0

        self.downloads_timer = QTimer()
        self.downloads_timeout_timer = QTimer()
        self.downloads_last_update = 0
        self.downloads_request_mgr = TriblerRequestManager()

        self.plot_data = [[[], []], []]

    def showEvent(self, QShowEvent):
        """
        When the downloads tab is clicked, we want to update the downloads list immediately.
        """
        super(TokenMiningPage, self).showEvent(QShowEvent)
        self.stop_loading_downloads()
        self.schedule_downloads_timer(True)

    def initialize_token_mining_page(self):
        self.window().token_mining_back_button.setIcon(QIcon(get_image_path('page_back.png')))
        vlayout = self.window().token_mining_plot_widget.layout()
        if vlayout.isEmpty():
            self.trust_plot = TokenMiningPlotMplCanvas(self.window().token_mining_plot_widget, dpi=100)
            vlayout.addWidget(self.trust_plot)

    def on_received_stats(self, stats):
        total_download = stats.get('total_download', 0)
        total_upload = stats.get('total_upload', 0)
        self.window().token_mining_upload_amount_label.setText(str(total_upload))
        self.window().token_mining_download_amount_label.setText(str(total_download))

    def schedule_downloads_timer(self, now=False):
        self.downloads_timer = QTimer()
        self.downloads_timer.setSingleShot(True)
        self.downloads_timer.timeout.connect(self.load_downloads)
        self.downloads_timer.start(0 if now else self.REFRESH_INTERVAL_MS)

        self.downloads_timeout_timer = QTimer()
        self.downloads_timeout_timer.setSingleShot(True)
        self.downloads_timeout_timer.timeout.connect(self.on_downloads_request_timeout)
        self.downloads_timeout_timer.start(self.TIMEOUT_INTERVAL_MS)

    def on_downloads_request_timeout(self):
        self.downloads_request_mgr.cancel_request()
        self.schedule_downloads_timer()

    def stop_loading_downloads(self):
        self.downloads_timer.stop()
        self.downloads_timeout_timer.stop()

    def load_downloads(self):
        url = "downloads?get_pieces=1"
        if time.time() - self.downloads_last_update > self.REFRESH_INTERVAL_MS/1000:
            self.downloads_last_update = time.time()
            self.downloads_request_mgr.cancel_request()
            self.downloads_request_mgr = TriblerRequestManager()
            self.downloads_request_mgr.perform_request(url, self.on_received_downloads, priority="LOW")

    def on_received_downloads(self, downloads):
        if not downloads:
            return  # This might happen when closing Tribler

        bytes_max = self.window().tribler_settings["credit_mining"]["max_disk_space"]
        bytes_used = 0
        total_up = total_down = 0
        for download in downloads["downloads"]:
            if download["credit_mining"] and \
                    download["status"] in ("DLSTATUS_DOWNLOADING", "DLSTATUS_SEEDING",
                                           "DLSTATUS_STOPPED", "DLSTATUS_STOPPED_ON_ERROR"):
                bytes_used += download["progress"] * download["size"]
                total_up += download["total_up"]
                total_down += download["total_down"]

        self.window().token_mining_upload_amount_label.setText(format_size(total_up))
        self.window().token_mining_download_amount_label.setText(format_size(total_down))
        self.window().token_mining_disk_usage_label.setText("%s / %s" % (format_size(float(bytes_used)),
                                                                         format_size(float(bytes_max))))

        self.push_data_to_plot(total_up, total_down)
        self.trust_plot.plot_data = self.plot_data
        self.trust_plot.compute_initial_figure()

        self.schedule_downloads_timer()

    def push_data_to_plot(self, upload, download):
        # Keep only last 100 records to show in graph
        if len(self.plot_data[1]) > 100:
            self.plot_data[1] = self.plot_data[1][-100:]
            self.plot_data[0][0] = self.plot_data[0][0][-100:]
            self.plot_data[0][1] = self.plot_data[0][1][-100:]

        self.plot_data[1].append(datetime.datetime.now())
        self.plot_data[0][0].append(upload / self.byte_scale)
        self.plot_data[0][1].append(download / self.byte_scale)
