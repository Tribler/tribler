from typing import Dict

from PyQt5.QtWidgets import QWidget

from tribler.gui.defs import PB, TB
from tribler.gui.dialogs.trustexplanationdialog import TrustExplanationDialog
from tribler.gui.network.request_manager import request_manager
from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.utilities import connect
from tribler.gui.widgets.graphs.dataplot import TimeSeriesDataPlot


class TrustSeriesPlot(TimeSeriesDataPlot):
    def __init__(self, parent, **kargs):
        series = [
            {'name': 'Token balance', 'pen': (224, 94, 0), 'symbolBrush': (224, 94, 0), 'symbolPen': 'w'},
        ]
        super().__init__(parent, 'Token balance over time', series, **kargs)
        self.setLabel('left', 'Data', units='B')
        self.setLimits(yMin=-TB, yMax=PB)


class TrustPage(AddBreadcrumbOnShowMixin, QWidget):
    """
    This page shows various trust statistics.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.history = None
        self.byte_scale = 1024 * 1024
        self.dialog = None

    def initialize_trust_page(self):
        vlayout = self.window().plot_widget.layout()
        if vlayout.isEmpty():
            self.trust_plot = TrustSeriesPlot(self.window().plot_widget)
            vlayout.addWidget(self.trust_plot)

        connect(self.window().trust_explain_button.clicked, self.on_info_button_clicked)

    def on_info_button_clicked(self, checked):
        self.dialog = TrustExplanationDialog(self.window())
        self.dialog.show()

    def received_bandwidth_statistics(self, statistics: Dict) -> None:
        """
        We received bandwidth statistics from the Tribler core. Update the labels on the trust page with the
        received information.
        :param statistics: The received statistics, in JSON format.
        """
        if not statistics or "statistics" not in statistics:
            return

        statistics = statistics["statistics"]
        total_up = statistics.get("total_given", 0)
        total_down = statistics.get("total_taken", 0)

        self.window().trust_contribution_amount_label.setText(f"{total_up // self.byte_scale} MBytes")
        self.window().trust_consumption_amount_label.setText(f"{total_down // self.byte_scale} MBytes")

        self.window().trust_people_helped_label.setText("%d" % statistics["num_peers_helped"])
        self.window().trust_people_helped_you_label.setText("%d" % statistics["num_peers_helped_by"])

    def load_history(self) -> None:
        """
        Load the bandwidth balance history by initiating a request to the Tribler core.
        """
        request_manager.get("bandwidth/history", self.received_history)

    def received_history(self, history: Dict):
        """
        We received the bandwidth history from the Tribler core. Plot it in the trust chart.
        :param history: The received bandwidth history, in JSON format.
        """
        if history:
            self.history = history["history"]
            self.plot_absolute_values()

    def plot_absolute_values(self) -> None:
        """
        Plot the evolution of the token balance.
        """
        if self.history:
            min_balance = min(item['balance'] for item in self.history)
            max_balance = max(item['balance'] for item in self.history)
            half = (max_balance - min_balance) / 2
            min_limit = min(-TB, min_balance - half)
            max_limit = max(PB, max_balance + half)
            self.trust_plot.setLimits(yMin=min_limit, yMax=max_limit)
            self.trust_plot.setYRange(min_balance, max_balance)

        # Convert all dates to a datetime object
        for history_item in self.history:
            timestamp = history_item["timestamp"] // 1000
            self.trust_plot.add_data(timestamp, [history_item["balance"]])

        self.trust_plot.render_plot()
