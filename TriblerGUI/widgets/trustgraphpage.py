from __future__ import absolute_import, division

import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QSizePolicy, QWidget

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.pyplot import Figure

from networkx.readwrite import json_graph

from TriblerGUI.defs import TRUST_GRAPH_HEADER_MESSAGE
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, html_label

matplotlib.use('Qt5Agg')

RED = "#ff0000"
GREEN = "#2ca01c"
NEUTRAL = "#cdcdcd"
DEFAULT = "#150507"
SELECTED = "#5c58ee"
BACKGROUND = "#202020"
SPACE = '&nbsp;'


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

        # User interaction
        self.fig.canvas.setFocusPolicy(Qt.ClickFocus)
        self.fig.canvas.setFocus()
        # self.fig.canvas.mpl_connect('pick_event', self.on_pick)
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press_event)
        self.fig.canvas.mpl_connect('button_release_event', self.on_mouse_release_event)
        self.figure.canvas.mpl_connect("motion_notify_event", self.on_drag)

        self.line_nodes = []
        self.central_nodes = []
        self.drag_root_node = False

        self.animation_frame = 0

        self.graph = None
        self.edges = None
        self.pos = None
        self.old_pos = None
        self.root_node = None
        self.token_balance = {}
        self.redraw = False
        self.translation = {'x': 0, 'y': 0}
        self.root_position = {'x': 0, 'y': 0}
        self.move_frame_fraction = 0

        self.animation_frame = 0
        self.max_frames = 20

        self.selected_node = {'public_key': '', 'up': 0, 'down': 0}
        self.node_selection_callback = None

    def showEvent(self, QShowEvent):
        super(TrustAnimationCanvas, self).showEvent(QShowEvent)
        self.translation = {'x': 0, 'y': 0}
        self.redraw = True
        self.animation_frame = 1
        self.update_canvas()

    def compute_initial_figure(self):
        self.axes.cla()
        self.axes.set_title("Realtime view of your Trust Graph", color="#e0e0e0")

    def update_canvas(self):
        if not self.graph or not self.animation_frame or not self.should_redraw_graph():
            return

        self.axes.clear()
        self.axes.set_xlim(0, 1)
        self.axes.set_ylim(0, 1)
        self.axes.set_xticks([], [])
        self.axes.set_yticks([], [])

        # To support animation, new positions of the nodes are calculated based on the frame rate.
        move_frame_fraction = 1 - (self.animation_frame - 1) / (1.0 * self.max_frames)
        current_positions = self.compute_node_positions_and_color(self.pos, self.old_pos, move_frame_fraction)

        # Draw the graph based on the current positions of the nodes
        self.draw_graph(self.root_node, current_positions)

    def compute_node_positions_and_color(self, target_pos, old_pos, move_fraction):
        """
        Computes the new position of the nodes to animate the graph based on frame rate (represented by move fraction).
        :param target_pos: Final position of the nodes
        :param old_pos: Previous position of the nodes
        :param move_fraction: Represents how close the current position should be from the target position.
        :return: Positions of the nodes to render in the graph
        """
        actual_pos = {}

        if old_pos is None:
            for n in self.graph.node:
                actual_pos[n] = ((target_pos[n][0]), (target_pos[n][1]), self.get_node_color(n), self.get_node_size(n))
        else:
            for n in set(old_pos.keys()).difference(target_pos.keys()):
                old_pos[n] = (1.0, 0.0)
            for n in set(target_pos.keys()).difference(old_pos.keys()):
                target_pos[n] = (0.0, 0.0)

            for n in self.graph.node:
                if n not in target_pos:
                    target_pos[n] = (0.0, 0.0)
                if n not in old_pos:
                    old_pos[n] = (0.0, 1.0)
                actual_pos[n] = ((((target_pos[n][0] - old_pos[n][0]) * move_fraction)
                                  + old_pos[n][0] + self.translation['x']
                                 ),
                                 (((target_pos[n][1] - old_pos[n][1]) * move_fraction)
                                  + old_pos[n][1] + self.translation['y']
                                 ),
                                 self.get_node_color(n), self.get_node_size(n))
        return actual_pos

    def draw_graph(self, root_node, node_positions):
        """
        Draws graph using the nodes and edges provided from root_node perspective.
        :param root_node: Central node
        :param node_positions: List of positions (x,y) of all the graph nodes.
        :return: None
        """
        x1s, x2s, y1s, y2s = [], [], [], []
        for edge in self.graph.edges():
            x1s.append(node_positions[str(edge[0])][0])
            y1s.append(node_positions[str(edge[0])][1])
            x2s.append(node_positions[str(edge[1])][0])
            y2s.append(node_positions[str(edge[1])][1])

        self.axes.set_facecolor(BACKGROUND)
        self.central_nodes = self.axes.plot(node_positions[root_node][0], node_positions[root_node][1],
                                            marker='o', color='#e67300', alpha=1.0, linestyle='--', lw=1,
                                            markersize=24, markeredgecolor='#e67300', markeredgewidth=1)
        self.line_nodes = self.axes.plot([x1s, x2s], [y1s, y2s],
                                         marker='o', color='#e0e0e0', alpha=0.5, linestyle='--', lw=0.5,
                                         markersize=0, markeredgecolor='#ababab', markeredgewidth=1)
        self.axes.text(node_positions[root_node][0], node_positions[root_node][1], "You", color='#ffffff',
                       verticalalignment='center', horizontalalignment='center', fontsize=8)

        nodes_x, nodes_y, colors, sizes = zip(*node_positions.values())
        self.axes.scatter(nodes_x, nodes_y, c=colors, s=sizes, alpha=0.6, edgecolors=colors)

        self.axes.figure.canvas.draw()
        self.show_selected_node_info()
        self.redraw = False

    def show_selected_node_info(self):
        if not self.selected_node or not self.selected_node.get('public_key', None):
            self.selected_node = dict()
            self.selected_node['public_key'] = self.root_node

        node_balance = self.token_balance.get(self.selected_node['public_key'], dict())
        self.selected_node['total_up'] = node_balance.get('total_up', 0)
        self.selected_node['total_down'] = node_balance.get('total_down', 0)

        if self.node_selection_callback:
            self.node_selection_callback(self.selected_node)

    def get_node_color(self, node_public_key):
        if self.selected_node.get('public_key', None) == node_public_key:
            return SELECTED
        node_balance = self.token_balance.get(node_public_key, {'total_up': 0, 'total_down': 0})
        if node_balance['total_up'] > node_balance['total_down']:
            return GREEN
        elif node_balance['total_up'] < node_balance['total_down']:
            return RED
        return NEUTRAL

    def get_node_size(self, node_public_key):
        if self.selected_node.get('public_key', None) == node_public_key:
            return 200
        return 100

    def should_redraw_graph(self):
        if not self.old_pos or self.redraw:
            return True
        if len(self.old_pos.keys()) != len(self.pos.keys()):
            return True
        for node_id in self.pos.keys():
            if node_id not in self.old_pos:
                return True
            if self.old_pos[node_id] != self.pos[node_id]:
                return True
        return False

    def on_mouse_press_event(self, event):
        self.selected_node = dict()
        self.drag_root_node = self.central_nodes[0].contains(event)[0]
        if self.drag_root_node:
            self.selected_node['public_key'] = self.root_node
        else:
            for index in range(len(self.line_nodes)):
                clicked_line = self.line_nodes[index].contains(event)
                if clicked_line[0]:
                    node_index_in_line = clicked_line[1]['ind'][0]
                    self.selected_node['public_key'] = self.graph.edges.keys()[index][node_index_in_line]
                    self.redraw = True

    def on_mouse_release_event(self, _):
        self.update_canvas()

    def on_drag(self, event):
        if event.button == 1 and self.drag_root_node:
            self.translation['x'] += event.xdata - self.central_nodes[0].get_xdata()[0]
            self.translation['y'] += event.ydata - self.central_nodes[0].get_ydata()[0]
            self.animation_frame = 1
            self.redraw = True
            self.update_canvas()


class TrustGraphPage(QWidget):
    REFRESH_INTERVAL_MS = 1000
    TIMEOUT_INTERVAL_MS = 5000

    MAX_FRAMES = 3
    ANIMATION_DURATION = 3000

    def __init__(self):
        QWidget.__init__(self)
        self.trust_plot = None
        self.fetch_data_timer = QTimer()
        self.fetch_data_timeout_timer = QTimer()
        self.fetch_data_last_update = 0
        self.graph_request_mgr = TriblerRequestManager()

        self.animation_timer = None
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
        self.trust_plot.node_selection_callback = self.on_node_selection_callback
        vlayout.addWidget(self.trust_plot)
        self.window().trust_graph_explanation_label.setText(TRUST_GRAPH_HEADER_MESSAGE)
        self.window().trust_graph_progress_bar.setHidden(True)
        self.trust_plot.max_frames = self.MAX_FRAMES

    def on_node_selection_callback(self, selected_node):
        if not selected_node:
            return

        peer_message = "<b>Peer</b> %s%s..." % (SPACE * 16, selected_node.get('public_key', '')[:74])
        self.window().tr_selected_node_pub_key.setText(peer_message)

        diff = selected_node.get('total_up', 0) - selected_node.get('total_down', 0)
        color = GREEN if diff > 0 else RED if diff < 0 else DEFAULT
        bandwidth_message = "<b>Bandwidth</b> " + SPACE * 2 \
                            + " Given " + SPACE + html_label(format_size(selected_node.get('total_up', 0))) \
                            + " Taken " + SPACE + html_label(format_size(selected_node.get('total_down', 0))) \
                            + " Balance " + SPACE + html_label(format_size(diff), color=color)
        self.window().tr_selected_node_stats.setText(bandwidth_message)

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
        self.trust_plot.graph = json_graph.node_link_graph(data['graph_data'])
        self.trust_plot.old_pos = None if self.trust_plot.pos is None else dict(self.trust_plot.pos)
        self.trust_plot.pos = data['positions']
        self.trust_plot.edges = self.trust_plot.graph.edges()
        self.trust_plot.root_node = data['node_id']
        self.trust_plot.token_balance = data['token_balance']

        if not self.trust_plot.should_redraw_graph():
            return

        self.trust_plot.animation_frame = self.MAX_FRAMES
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.redraw_graph)
        self.animation_timer.setInterval(self.ANIMATION_DURATION/self.MAX_FRAMES)
        self.animation_timer.start(0)

    def redraw_graph(self):
        self.trust_plot.animation_frame -= 1
        if self.trust_plot.animation_frame:
            self.trust_plot.update_canvas()
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

        status_message = u"<strong style='font-size:14px'>Transactions : %s &nbsp;&nbsp; " \
                         u"| &nbsp;&nbsp; Peers : %s</strong> &nbsp;" \
                         u"( <span style='color:%s'>\u2B24 Good</span> &nbsp; " \
                         u"<span style='color:%s'>\u2B24 Bad</span> &nbsp; " \
                         u"<span style='color:%s'>\u2B24 Unknown</span> &nbsp; " \
                         u"<span style='color:%s'>\u2B24 Selected</span> )" \
                         % (data['num_tx'], len(data['positions']), GREEN, RED, NEUTRAL, SELECTED)
        self.window().trust_graph_status_bar.setText(status_message)
