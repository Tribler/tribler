import urllib

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
        self.blocks = None

    def initialize_trust_page(self):
        vlayout = self.window().plot_widget.layout()
        self.trust_plot = TrustPlotMplCanvas(self.window().plot_widget, dpi=100)
        vlayout.addWidget(self.trust_plot)

    def load_trust_statistics(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("multichain/statistics", self.received_multichain_statistics)

    def received_multichain_statistics(self, statistics):
        statistics = statistics["statistics"]
        self.window().trust_contribution_amount_label.setText("%s MBytes" % statistics["self_total_up_mb"])
        self.window().trust_consumption_amount_label.setText("%s MBytes" % statistics["self_total_down_mb"])

        self.window().trust_people_helped_label.setText("%d" % statistics["self_peers_helped"])
        self.window().trust_people_helped_you_label.setText("%d" % statistics["self_peers_helped_you"])

        # Fetch the latest blocks of this user
        encoded_pub_key = urllib.quote_plus(statistics["self_id"])
        self.public_key = statistics["self_id"]
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("multichain/blocks/%s" % encoded_pub_key, self.received_multichain_blocks)

    def received_multichain_blocks(self, blocks):
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

            if block["public_key_requester"] == self.public_key:
                plot_data[0][0].append(block["total_up_requester"])
                plot_data[0][1].append(block["total_down_requester"])
            else:
                plot_data[0][0].append(block["total_up_responder"])
                plot_data[0][1].append(block["total_down_responder"])

        if len(self.blocks) == 0:
            # Create on single data point with 0mb up and 0mb down
            plot_data = [[[0], [0]], [datetime.datetime.now()]]

        self.trust_plot.plot_data = plot_data
        self.trust_plot.compute_initial_figure()
