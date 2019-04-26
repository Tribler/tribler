from __future__ import absolute_import, division

import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QSizePolicy, QWidget

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.pyplot import Figure

import networkx as nx

from TriblerGUI.defs import TRUST_GRAPH_HEADER_MESSAGE
from TriblerGUI.tribler_request_manager import TriblerRequestManager

matplotlib.use('Qt5Agg')


class TrustAnimationCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor("#202020")
        self.fig.set_edgecolor("green")

        self.fig.set_tight_layout({"pad": 1})
        self.axes = self.fig.add_subplot(111)
        self.axes.tick_params(axis='both', which='both', bottom=False, top=False, left=False,
                              labelbottom=False, labelleft=False)

        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.node_id = None

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("Realtime view of your Trust Graph", color="#e0e0e0")

    def update_canvas(self, graph, node_id, pos, old_pos, edge_list, framecount=0, max_frames=20):
        if not graph or not framecount:
            return

        self.axes.clear()
        self.axes.set_xlim(0, 1)
        self.axes.set_ylim(0, 1)
        self.axes.set_xticks([], [])
        self.axes.set_yticks([], [])

        xpos = []
        ypos = []
        actual_pos = {}

        if old_pos is None:
            nodes = [n for n in graph.nodes]
            for n in nodes:
                actual_pos[n] = ((pos[n][0]), (pos[n][1]))
        else:
            for n in set(old_pos.keys()).difference(pos.keys()):
                old_pos[n] = (1.0, 0.0)
            for n in set(pos.keys()).difference(old_pos.keys()):
                pos[n] = (0.0, 0.0)

            move_frame_fraction = 1 - (framecount - 1) / (1.0 * max_frames)
            nodes = [n for n in graph.nodes]
            for n in nodes:
                if old_pos is not None:
                    if n not in pos:
                        pos[n] = (0.0, 0.0)
                    if n not in old_pos:
                        old_pos[n] = (0.0, 1.0)
                    actual_pos[n] = ((((pos[n][0] - old_pos[n][0]) * move_frame_fraction) + old_pos[n][0]),
                                     (((pos[n][1] - old_pos[n][1]) * move_frame_fraction) + old_pos[n][1]))
                else:
                    actual_pos[n] = ((pos[n][0]),
                                     (pos[n][1]))

        for v in actual_pos.values():
            xpos.append(v[0])
            ypos.append(v[1])

        # Draw edges
        x1s, x2s, y1s, y2s = [], [], [], []
        for edge in edge_list:
            x1s.append(actual_pos[str(edge[0])][0])
            y1s.append(actual_pos[str(edge[0])][1])
            x2s.append(actual_pos[str(edge[1])][0])
            y2s.append(actual_pos[str(edge[1])][1])

        self.axes.set_facecolor('#202020')
        self.axes.plot([x1s, x2s], [y1s, y2s],
                       marker='o', color='#e0e0e0', alpha=0.5, linestyle='--', lw=0.5,
                       markersize=12, markeredgecolor='#ababab', markeredgewidth=1)
        self.axes.plot(actual_pos[node_id][0], actual_pos[node_id][1],
                       marker='o', color='#e67300', alpha=1.0, linestyle='--', lw=1,
                       markersize=24, markeredgecolor='#e67300', markeredgewidth=1)
        self.axes.text(actual_pos[node_id][0], actual_pos[node_id][1], "You", color='#ffffff',
                       verticalalignment='center', horizontalalignment='center', fontsize=8)

        self.axes.figure.canvas.draw()


class TrustGraphPage(QWidget):
    REFRESH_INTERVAL_MS = 1000
    TIMEOUT_INTERVAL_MS = 5000

    MAX_FRAMES = 5
    ANIMATION_DURATION = 3000

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.fetch_data_timer = QTimer()
        self.fetch_data_timeout_timer = QTimer()
        self.fetch_data_last_update = 0
        self.graph_request_mgr = TriblerRequestManager()
        self.graph = None
        self.edges = None
        self.pos = None
        self.old_pos = None
        self.node_id = None

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
        self.window().trust_graph_explanation_label.setText(TRUST_GRAPH_HEADER_MESSAGE)
        self.window().trust_graph_progress_bar.setHidden(True)

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
        if self.animation_timer:
            self.animation_timer.stop()

    def fetch_graph_data(self):
        if time.time() - self.fetch_data_last_update > self.REFRESH_INTERVAL_MS / 1000:
            self.fetch_data_last_update = time.time()
            self.graph_request_mgr.cancel_request()
            self.graph_request_mgr = TriblerRequestManager()
            self.graph_request_mgr.perform_request("trustview", self.on_received_data, priority="LOW")

    def on_received_data(self, data):
        if data is None:
            return
        self.update_gui_labels(data)
        self.graph = nx.node_link_graph(data['graph_data'])
        self.old_pos = None if self.pos is None else dict(self.pos)
        self.pos = data['positions']
        self.edges = self.graph.edges
        self.node_id = data['node_id']

        if not self.should_update_graph(self.old_pos, self.pos):
            return

        self.animation_frame = self.MAX_FRAMES
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_graph)
        self.animation_timer.setInterval(self.ANIMATION_DURATION/self.MAX_FRAMES)
        self.animation_timer.start(0)

    def should_update_graph(self, old_pos, new_pos):
        if not old_pos:
            return True
        if len(old_pos.keys()) != len(new_pos.keys()):
            return True
        for node_id in new_pos.keys():
            if node_id not in old_pos:
                return True
            if old_pos[node_id] != new_pos[node_id]:
                return True
        return False

    def update_graph(self):
        self.animation_frame -= 1
        if self.animation_frame:
            self.trust_plot.update_canvas(self.graph, self.node_id, self.pos, self.old_pos, self.edges,
                                          self.animation_frame, self.MAX_FRAMES)
        else:
            self.animation_timer.stop()
            self.schedule_fetch_data_timer()

    def update_gui_labels(self, data):
        bootstrap_progress = int(data['bootstrap']['progress'] * 100)
        if bootstrap_progress == 100:
            self.window().trust_graph_progress_bar.setHidden(True)
        else:
            self.window().trust_graph_progress_bar.setHidden(False)
            self.window().trust_graph_progress_bar.setValue(bootstrap_progress)
        status_message = "Transactions: %s | Peers: %s" % (data['num_tx'], len(data['positions']))
        self.window().trust_graph_status_bar.setText(status_message)
