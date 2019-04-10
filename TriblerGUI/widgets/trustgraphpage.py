import datetime
import time

import networkx as nx
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from PyQt5.QtWidgets import QSizePolicy, QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.trustpage import MplCanvas


class TrustAnimationCanvas(MplCanvas):

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
        self.axes.set_title("Realtime view of your Trust Graph", color="#e0e0e0")
        self.ax = self.figure.add_axes([0.025, 0.1, 1, 1], frameon=False)
        self.ax.set_xlim(0, 1), self.ax.set_xticks([])
        self.ax.set_ylim(0, 1), self.ax.set_yticks([])
        self._dynamic_ax = self.figure.subplots()

    def update_canvas(self, graph, pos, old_pos, framecount=0, max_frames=20):
        if not framecount:
            return

        self._dynamic_ax.clear()
        self._dynamic_ax.set_xlim(0, 1), self._dynamic_ax.set_xticks([])
        self._dynamic_ax.set_ylim(0, 1), self._dynamic_ax.set_yticks([])

        xpos = []
        ypos = []

        if graph is not None:
            move_frame_fraction = 1 - framecount / (1.0 * max_frames)
            for n in graph.nodes():
                if old_pos is not None:
                    xpos.append(((pos[str(n)][0] - old_pos[str(n)][0]) * move_frame_fraction) + old_pos[str(n)][0])
                    ypos.append(((pos[str(n)][1] - old_pos[str(n)][1]) * move_frame_fraction) + old_pos[str(n)][1])
                else:
                    xpos.append(pos[str(n)][0])
                    ypos.append(pos[str(n)][1])

            self._dynamic_ax.scatter(xpos, ypos)
            self._dynamic_ax.figure.canvas.draw()


class TrustGraphPage(QWidget):
    REFRESH_INTERVAL_MS = 2000
    TIMEOUT_INTERVAL_MS = 5000

    MAX_FRAMES = 100
    ANIMATION_DURATION = 4000

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.fetch_data_timer = QTimer()
        self.fetch_data_timeout_timer = QTimer()
        self.fetch_data_last_update = 0
        self.graph_request_mgr = TriblerRequestManager()
        self.pos = None
        self.old_pos = None

        self.animation_timer = None
        self.animation_frame = 0
        self.animation_refresh_interval = self.ANIMATION_DURATION/self.MAX_FRAMES

    def showEvent(self, QShowEvent):
        super(TrustGraphPage, self).showEvent(QShowEvent)
        self.schedule_fetch_data_timer(True)

    def hideEvent(self, QHideEvent):
        super(TrustGraphPage, self).hideEvent(QHideEvent)
        self.stop_fetch_data_request()

    def initialize_trust_graph(self):
        vlayout = self.window().trust_graph_plot_widget.layout()
        self.trust_plot = TrustAnimationCanvas(self.window().trust_graph_plot_widget, dpi=100)
        vlayout.addWidget(self.trust_plot)

    def schedule_fetch_data_timer(self, now=False):
        self.fetch_data_timer = QTimer()
        self.fetch_data_timer.setSingleShot(True)
        self.fetch_data_timer.timeout.connect(self.fetch_graph_data)
        self.fetch_data_timer.start(0 if now else self.REFRESH_INTERVAL_MS)

        self.fetch_data_timeout_timer = QTimer()
        self.fetch_data_timeout_timer.setSingleShot(True)
        self.fetch_data_timeout_timer.timeout.connect(self.on_fetch_data_request_timeout)
        self.fetch_data_timeout_timer.start(self.TIMEOUT_INTERVAL_MS)

    def on_fetch_data_request_timeout(self):
        self.graph_request_mgr.cancel_request()
        self.schedule_fetch_data_timer()

    def stop_fetch_data_request(self):
        self.fetch_data_timer.stop()
        self.fetch_data_timeout_timer.stop()

    def fetch_graph_data(self):
        if time.time() - self.fetch_data_last_update > self.REFRESH_INTERVAL_MS / 1000:
            self.fetch_data_last_update = time.time()
            self.graph_request_mgr.cancel_request()
            self.graph_request_mgr = TriblerRequestManager()
            self.graph_request_mgr.perform_request("trustview", self.on_received_data, priority="LOW")

    def on_received_data(self, data):
        self.graph = nx.node_link_graph(data['graph_data'])
        self.old_pos = None if self.pos is None else dict(self.pos)
        self.pos = data['positions']

        self.animation_frame = self.MAX_FRAMES
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_graph)
        self.animation_timer.setInterval(self.ANIMATION_DURATION/self.MAX_FRAMES)
        self.animation_timer.start(0)

    def update_graph(self):
        self.animation_frame -= 1
        if self.animation_frame:
            self.trust_plot.update_canvas(self.graph, self.pos, self.old_pos, self.animation_frame, self.MAX_FRAMES)
        else:
            self.animation_timer.stop()
            self.schedule_fetch_data_timer()

