import datetime
import time
from random import random
import numpy

import networkx as nx
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.pyplot import Figure
# import matplotlib.pyplot as plt
# from matplotlib.animation import FuncAnimation

from PyQt5.QtWidgets import QSizePolicy, QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.trustpage import MplCanvas


class TrustAnimationCanvas(MplCanvas):

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.set_facecolor("#00000000")
        fig.set_edgecolor("green")

        fig.set_tight_layout({"pad": 1})
        self.axes = fig.add_subplot(111)
        self.axes.tick_params(axis='both', which='both', bottom=False, top=False, left=False,
                              labelbottom=False, labelleft=False)
        # self.plot_data = [[[0], [0]], [datetime.datetime.now()]]

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.compute_initial_figure()

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("Realtime view of your Trust Graph", color="#e0e0e0")
        # self.ax = self.figure.add_axes([0.025, 0.1, 1, 1], frameon=False)
        # self.ax.set_xlim(0, 1), self.ax.set_xticks([])
        # self.ax.set_ylim(0, 1), self.ax.set_yticks([])
        self._dynamic_ax = self.figure.subplots()

    def update_canvas(self, graph, pos, old_pos, edge_list, framecount=0, max_frames=20):
        if not framecount:
            return

        self._dynamic_ax.clear()
        self._dynamic_ax.set_xlim(0, 1), self._dynamic_ax.set_xticks([], [])
        self._dynamic_ax.set_ylim(0, 1), self._dynamic_ax.set_yticks([], [])
        # self.axes.tick_params(axis='both', which='both', bottom=False, top=False, labelbottom=False, labelleft=False)

        xpos = []
        ypos = []

        actual_pos = {}

        if graph is None:
            return

        if old_pos is None:
            nodes = [str(n) for n in graph.nodes]
            for n in nodes:
                actual_pos[n] = ((pos[n][0]), (pos[n][1]))
        else:
            for n in set(old_pos.keys()).difference(pos.keys()):
                old_pos[n] = (1.0, 0.0)
            for n in set(pos.keys()).difference(old_pos.keys()):
                pos[n] = (0.0, 0.0)

            move_frame_fraction = 1 - (framecount - 1) / (1.0 * max_frames)
            nodes = [str(n) for n in graph.nodes]
            for n in nodes:
                if old_pos is not None:
                    if n not in pos:
                        pos[n] = (0.0, 0.0)
                    if n not in old_pos:
                        old_pos[n] = (0.0, 1.0)
                    # actual_pos[n] = ((((pos[n][0] - old_pos[n][0]) * move_frame_fraction) + old_pos[n][0])
                    #                  + (random() * 0.001 - 0.0005),
                    #                  (((pos[n][1] - old_pos[n][1]) * move_frame_fraction) + old_pos[n][1])
                    #                  + (random() * 0.001 - 0.0005))
                    actual_pos[n] = ((((pos[n][0] - old_pos[n][0]) * move_frame_fraction) + old_pos[n][0]),
                                     (((pos[n][1] - old_pos[n][1]) * move_frame_fraction) + old_pos[n][1]))
                else:
                    actual_pos[n] = ((pos[n][0]),
                                     (pos[n][1]))

        for v in actual_pos.values():
            xpos.append(v[0])
            ypos.append(v[1])

        self._dynamic_ax.scatter(xpos, ypos)

        # Draw edges
        x1s, x2s, y1s, y2s, lws = [], [], [], [], []

        # print('Setting edge positions')
        for edge in edge_list:
            x1s.append(actual_pos[str(edge[0])][0])
            y1s.append(actual_pos[str(edge[0])][1])
            x2s.append(actual_pos[str(edge[1])][0])
            y2s.append(actual_pos[str(edge[1])][1])
            # lws.append(self.gr[edge[0]][edge[1]]['weight'])

        self._dynamic_ax.set_facecolor('#202020')
        self._dynamic_ax.plot([x1s, x2s], [y1s, y2s],
                              marker='o', color='#DADADA', alpha=0.3, linestyle='--', lw=1,
                              markersize=12, markeredgecolor='black', markeredgewidth=2)
        self._dynamic_ax.plot(actual_pos['0'][0], actual_pos['0'][1],
                              marker='o', color='#e67300', alpha=0.9, linestyle='--', lw=1,
                              markersize=12, markeredgecolor='black', markeredgewidth=2)
        self._dynamic_ax.figure.canvas.draw()


        # for e in edge_list:
        #     self._dynamic_ax.plot(actual_pos[e[0]], actual_pos[e[1]])


class TrustGraphPage(QWidget):
    REFRESH_INTERVAL_MS = 1000
    TIMEOUT_INTERVAL_MS = 5000

    MAX_FRAMES = 20
    ANIMATION_DURATION = 3000

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
        if data is None:
            return
        self.graph = nx.node_link_graph(data['graph_data'])
        self.old_pos = None if self.pos is None else dict(self.pos)
        self.pos = data['positions']
        self.edges = self.graph.edges

        self.animation_frame = self.MAX_FRAMES
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_graph)
        self.animation_timer.setInterval(self.ANIMATION_DURATION/self.MAX_FRAMES)
        self.animation_timer.start(0)

    def update_graph(self):
        self.animation_frame -= 1
        if self.animation_frame:
            self.trust_plot.update_canvas(self.graph, self.pos, self.old_pos, self.edges, self.animation_frame, self.MAX_FRAMES)
        else:
            self.animation_timer.stop()
            self.schedule_fetch_data_timer()

