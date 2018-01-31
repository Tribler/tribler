import matplotlib

from TriblerGUI.defs import PAGE_MARKET

matplotlib.use('Qt5Agg')

import datetime
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure

from TriblerGUI.tribler_request_manager import TriblerRequestManager


class MplCanvas(FigureCanvas):
    """Ultimately, this is a QWidget."""

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.set_facecolor("#282828")

        fig.set_tight_layout({"pad": 1})
        self.axes = fig.add_subplot(111)
        self.plot_data = None

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def compute_initial_figure(self):
        pass


class TrustPlotMplCanvas(MplCanvas):

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("MBytes given/taken over time", color="#e0e0e0")
        self.axes.set_xlabel("Date")
        self.axes.set_ylabel("Given/taken data (MBytes)")

        self.axes.xaxis.set_major_formatter(DateFormatter('%d-%m-%y'))

        self.axes.plot(self.plot_data[1], self.plot_data[0][0], label="MBytes given", marker='o')
        self.axes.plot(self.plot_data[1], self.plot_data[0][1], label="MBytes taken", marker='o')
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


class TrustPage(QWidget):
    """
    This page shows various trust statistics.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.public_key = None
        self.request_mgr = None
        self.statistics = None
        self.blocks = None
        self.byte_scale = 1024 * 1024
        self.timer = None

    def initialize_trust_page(self):
        vlayout = self.window().plot_widget.layout()
        self.trust_plot = TrustPlotMplCanvas(self.window().plot_widget, dpi=100)
        vlayout.addWidget(self.trust_plot)
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.load_trust_statistics)
        self.timer.start(60000)

        self.window().trade_button.clicked.connect(self.on_trade_button_clicked)

    def on_trade_button_clicked(self):
        self.window().market_page.initialize_market_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET)

    def load_trust_statistics(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("trustchain/statistics", self.received_trustchain_statistics)

    def received_trustchain_statistics(self, statistics):
        statistics = statistics["statistics"]
        total_up = 0
        total_down = 0
        if 'latest_block' in statistics:
            total_up = statistics["latest_block"]["transaction"]["total_up"]
            total_down = statistics["latest_block"]["transaction"]["total_down"]

        self.window().trust_contribution_amount_label.setText("%s MBytes" % (total_up / self.byte_scale))
        self.window().trust_consumption_amount_label.setText("%s MBytes" % (total_down / self.byte_scale))

        self.window().trust_people_helped_label.setText("%d" % statistics["peers_that_pk_helped"])
        self.window().trust_people_helped_you_label.setText("%d" % statistics["peers_that_helped_pk"])

        # Fetch the latest blocks of this user
        self.public_key = statistics["id"]
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("trustchain/blocks/%s" % self.public_key, self.received_trustchain_blocks)

    def received_trustchain_blocks(self, blocks):
        self.blocks = blocks["blocks"]
        self.plot_absolute_values()

    def plot_absolute_values(self):
        """
        Plot two lines of the absolute amounts of contributed and consumed bytes.
        """
        plot_data = [[[], []], []]

        # Convert all dates to a datetime object
        for block in self.blocks:
            plot_data[1].append(datetime.datetime.strptime(block["insert_time"], "%Y-%m-%d %H:%M:%S"))

            plot_data[0][0].append(block["transaction"]["total_up"] / self.byte_scale)
            plot_data[0][1].append(block["transaction"]["total_down"] / self.byte_scale)

        if len(self.blocks) == 0:
            # Create on single data point with 0mb up and 0mb down
            plot_data = [[[0], [0]], [datetime.datetime.now()]]

        self.trust_plot.plot_data = plot_data
        self.trust_plot.compute_initial_figure()
