from __future__ import absolute_import
from __future__ import division

import time

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import TB
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, get_image_path
from TriblerGUI.widgets.graphs.timeseriesplot import TimeSeriesPlot


class TokenMiningSeriesPlot(TimeSeriesPlot):

    def __init__(self, parent, **kargs):
        series = [
            {'name': 'Download', 'pen': (255, 0, 0), 'symbolBrush': (255, 0, 0), 'symbolPen': 'w'},
            {'name': 'Upload  ', 'pen': (0, 255, 0), 'symbolBrush': (0, 255, 0), 'symbolPen': 'w'},
        ]
        super(TokenMiningSeriesPlot, self).__init__(parent, 'Token Mining', series, **kargs)
        self.setLabel('left', 'Mined Data', units='bytes')
        self.setLimits(yMin=0, yMax=TB)


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

        self.downloads_timer = QTimer()
        self.downloads_timeout_timer = QTimer()
        self.downloads_last_update = 0
        self.downloads_request_mgr = TriblerRequestManager()

        self.plot_data = [[[], []], []]
        self.start_time = time.time()

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
            self.trust_plot = TokenMiningSeriesPlot(self.window().token_mining_plot_widget)
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
        if not downloads or "downloads" not in downloads:
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

        self.window().token_mining_upload_amount_label.setText(format_size(total_up + 1))
        self.window().token_mining_download_amount_label.setText(format_size(total_down + 1))
        self.window().token_mining_disk_usage_label.setText("%s / %s" % (format_size(float(bytes_used)),
                                                                         format_size(float(bytes_max))))

        self.trust_plot.add_data(time.time(), [total_down, total_up])
        self.trust_plot.render_plot()
        self.schedule_downloads_timer()
