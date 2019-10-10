from __future__ import absolute_import, division

import datetime
import time

from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import GB, PAGE_MARKET, PAGE_TOKEN_MINING_PAGE, TB
from TriblerGUI.dialogs.trustexplanationdialog import TrustExplanationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.tokenminingpage import TimeSeriesPlot


class TrustSeriesPlot(TimeSeriesPlot):

    def __init__(self, parent, **kargs):
        series = [
            {'name': 'Bytes taken', 'pen': (255, 0, 0), 'symbolBrush': (255, 0, 0), 'symbolPen': 'w'},
            {'name': 'Bytes given', 'pen': (0, 255, 0), 'symbolBrush': (0, 255, 0), 'symbolPen': 'w'},
        ]
        super(TrustSeriesPlot, self).__init__(parent, 'Mbytes given/taken over time', series, **kargs)
        self.setLabel('left', 'Given/taken data', units='bytes')
        self.setLimits(yMin=-GB, yMax=TB)


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
        self.byte_scale = 1024 * 1024
        self.dialog = None

    def showEvent(self, QShowEvent):
        super(TrustPage, self).showEvent(QShowEvent)
        if self.window().tribler_settings:  # It could be that the settings are not loaded yet
            self.window().mine_button.setHidden(not self.window().tribler_settings["credit_mining"]["enabled"])
            self.window().trade_button.setHidden(not self.window().tribler_settings["market_community"]["enabled"])
        else:
            self.window().mine_button.hide()
            self.window().trade_button.hide()

    def initialize_trust_page(self):
        vlayout = self.window().plot_widget.layout()
        if vlayout.isEmpty():
            self.trust_plot = TrustSeriesPlot(self.window().plot_widget)
            vlayout.addWidget(self.trust_plot)

        self.window().trade_button.clicked.connect(self.on_trade_button_clicked)
        self.window().mine_button.clicked.connect(self.on_mine_button_clicked)
        self.window().trust_explain_button.clicked.connect(self.on_info_button_clicked)

    def on_trade_button_clicked(self):
        self.window().market_page.initialize_market_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET)

    def on_info_button_clicked(self):
        self.dialog = TrustExplanationDialog(self.window())
        self.dialog.show()

    def on_mine_button_clicked(self):
        self.window().token_mining_page.initialize_token_mining_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_TOKEN_MINING_PAGE)

    def load_blocks(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("ipv8/trustchain/users/%s/blocks" % self.public_key,
                                         self.received_trustchain_blocks)

    def received_trustchain_statistics(self, statistics):
        if not statistics or "statistics" not in statistics:
            return
        statistics = statistics["statistics"]
        self.public_key = statistics["id"]

        total_up = statistics.get("total_up", 0)
        total_down = statistics.get("total_down", 0)

        self.window().trust_contribution_amount_label.setText("%s MBytes" % (total_up // self.byte_scale))
        self.window().trust_consumption_amount_label.setText("%s MBytes" % (total_down // self.byte_scale))

        self.window().trust_people_helped_label.setText("%d" % statistics["peers_that_pk_helped"])
        self.window().trust_people_helped_you_label.setText("%d" % statistics["peers_that_helped_pk"])

    def received_trustchain_blocks(self, blocks):
        if blocks:
            self.blocks = blocks["blocks"]
            self.plot_absolute_values()

    def plot_absolute_values(self):
        """
        Plot two lines of the absolute amounts of contributed and consumed bytes.
        """
        # Convert all dates to a datetime object
        num_bandwidth_blocks = 0
        for block in self.blocks:
            if block["type"] != "tribler_bandwidth":
                continue

            num_bandwidth_blocks += 1
            timestamp = time.mktime(datetime.datetime.strptime(block["insert_time"], "%Y-%m-%d %H:%M:%S").timetuple())
            self.trust_plot.add_data(timestamp, [block["transaction"]["total_down"], block["transaction"]["total_up"]])

        self.trust_plot.render_plot()
