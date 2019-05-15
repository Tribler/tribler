from __future__ import absolute_import, division

import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QSizePolicy, QWidget

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.pyplot import Figure

from networkx.readwrite import json_graph

from TriblerGUI.defs import COLOR_BACKGROUND, COLOR_DEFAULT, COLOR_GREEN, COLOR_NEUTRAL, COLOR_RED, COLOR_SELECTED, \
    HTML_SPACE, TRUST_GRAPH_HEADER_MESSAGE, TRUST_GRAPH_PEER_LEGENDS
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, html_label

matplotlib.use('Qt5Agg')


class TrustAnimationCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, frameon=False)
        self.fig.set_tight_layout(True)

        self.axes = self.fig.add_subplot(111)
        self.axes.tick_params(which='both', bottom=False, top=False, left=False, labelbottom=False, labelleft=False)
        self.axes.set_xlim(0, 1)
        self.axes.set_ylim(0, 1)
        self.axes.set_xticks([], [])
        self.axes.set_yticks([], [])
        self.axes.set_facecolor(COLOR_BACKGROUND)

        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        # User interaction
        self.fig.canvas.setFocusPolicy(Qt.ClickFocus)
        self.fig.canvas.setFocus()
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press_event)
        self.fig.canvas.mpl_connect('button_release_event', self.on_mouse_release_event)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_drag_event)

        self.root_public_key = None
        self.token_balance = {}

        # Reference to nodes in the plotted graph
        self.root_node = None
        self.scatter_nodes = []

        self.graph = None
        self.pos = None
        self.old_pos = None
        self.node_positions = None
        self.redraw = False

        self.animation_frame = 0
        self.max_frames = 20
        self.translation = {'x': 0, 'y': 0}

        self.selected_node = {'public_key': '', 'up': 0, 'down': 0}
        self.node_selection_callback = None

    def showEvent(self, QShowEvent):
        super(TrustAnimationCanvas, self).showEvent(QShowEvent)
        self.translation = {'x': 0, 'y': 0}
        self.redraw = True
        self.animation_frame = 1
        self.update_canvas()

    def update_canvas(self):
        if not self.graph or not self.animation_frame or not self.should_redraw_graph():
            return

        self.axes.clear()
        self.axes.set_xlim(0, 1)
        self.axes.set_ylim(0, 1)
        self.axes.set_xticks([], [])
        self.axes.set_yticks([], [])
        self.axes.set_facecolor(COLOR_BACKGROUND)

        # To support animation, new positions of the nodes are calculated based on the frame rate.
        move_frame_fraction = 1 - (self.animation_frame - 1) / (1.0 * self.max_frames)
        self.node_positions = self.compute_node_positions_and_color(self.pos, self.old_pos, move_frame_fraction)

        # Draw the graph based on the current positions of the nodes
        self.draw_graph(self.root_public_key, self.node_positions)

    def compute_node_positions_and_color(self, target_position, old_position, move_fraction):
        """
        Computes the new position of the nodes to animate the graph based on frame rate (represented by move fraction).
        :param target_position: Final position of the nodes
        :param old_position: Previous position of the nodes
        :param move_fraction: Represents how close the current position should be from the target position.
        :return: Position, color and size of the nodes to render in the graph
        """
        current_position = {}

        if old_position is None:
            for n in self.graph.node:
                current_position[n] = ((target_position[n][0]), (target_position[n][1]),
                                       self.get_node_color(n), self.get_node_size(n))
        else:
            for n in set(old_position.keys()).difference(target_position.keys()):
                old_position[n] = (1.0, 0.0)
            for n in set(target_position.keys()).difference(old_position.keys()):
                target_position[n] = (0.0, 0.0)

            for n in self.graph.node:
                if n not in target_position:
                    target_position[n] = (0.0, 0.0)
                if n not in old_position:
                    old_position[n] = (0.0, 1.0)
                current_position[n] = ((((target_position[n][0] - old_position[n][0]) * move_fraction)
                                        + old_position[n][0] + self.translation['x']),
                                       (((target_position[n][1] - old_position[n][1]) * move_fraction)
                                        + old_position[n][1] + self.translation['y']),
                                       self.get_node_color(n), self.get_node_size(n))
        return current_position

    def draw_graph(self, root_node, node_positions):
        """
        Draws graph using the nodes and edges provided from root_node perspective.
        :param root_node: Central node
        :param node_positions: List of positions (x,y) of all the graph nodes.
        :return: None
        """
        # Compute the co-ordinates for the nodes and (array) index as edges: (x1, y1) ---> (x2, y2)
        x1s, x2s, y1s, y2s = [], [], [], []
        for edge in self.graph.edges():
            x1s.append(node_positions[str(edge[0])][0])
            y1s.append(node_positions[str(edge[0])][1])
            x2s.append(node_positions[str(edge[1])][0])
            y2s.append(node_positions[str(edge[1])][1])

        # Plot the graph edges but nodes are set to have zero marker size. Nodes are plotted separately later.
        self.axes.plot([x1s, x2s], [y1s, y2s], color='#e0e0e0', alpha=0.5, linestyle='--', lw=0.1, markersize=0)
        self.axes.text(node_positions[root_node][0], node_positions[root_node][1], "You", color='#ffffff',
                       verticalalignment='center', horizontalalignment='center', fontsize=8)

        # Plot the root (center) node
        root_color = COLOR_SELECTED if self.selected_node.get('public_key', None) == self.root_public_key else '#e67300'
        self.root_node = self.axes.plot(node_positions[root_node][0], node_positions[root_node][1], marker='o',
                                        color=root_color, alpha=1.0, linestyle='--', lw=1, markersize=24,
                                        markeredgecolor='#e67300', markeredgewidth=1)[0]

        # Plot all the nodes as scatter plot to support clicking on the nodes
        nodes_x, nodes_y, colors, sizes = zip(*node_positions.values())
        self.scatter_nodes = self.axes.scatter(nodes_x, nodes_y, c=colors, s=sizes, alpha=0.6, edgecolors=colors)

        # Draw the canvas and invoke the callback for showing the info about the selected node
        self.figure.canvas.draw()
        self.show_selected_node_info()

        # At the end reset the redraw flag
        self.redraw = False

    def show_selected_node_info(self):
        """
        Invokes the registered callback to show the information about the selected node.
        """
        if not self.selected_node or not self.selected_node.get('public_key', None):
            self.selected_node = dict()
            self.selected_node['public_key'] = self.root_public_key

        node_balance = self.token_balance.get(self.selected_node['public_key'], dict())
        self.selected_node['total_up'] = node_balance.get('total_up', 0)
        self.selected_node['total_down'] = node_balance.get('total_down', 0)

        if self.node_selection_callback:
            self.node_selection_callback(self.selected_node)

    def get_node_color(self, node_public_key):
        if self.selected_node.get('public_key', None) == node_public_key:
            return COLOR_SELECTED
        node_balance = self.token_balance.get(node_public_key, {'total_up': 0, 'total_down': 0})
        if node_balance['total_up'] > node_balance['total_down']:
            return COLOR_GREEN
        elif node_balance['total_up'] < node_balance['total_down']:
            return COLOR_RED
        return COLOR_NEUTRAL

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
        enclosing_nodes = self.scatter_nodes.contains(event)
        # Example value for enclosing nodes: (True, {'ind': array([ 71, 340], dtype=int32)})
        if enclosing_nodes[0]:
            index = enclosing_nodes[1]['ind'][-1]
            self.selected_node['public_key'] = self.node_positions.keys()[index]
            self.redraw = True

    def on_mouse_release_event(self, _):
        self.update_canvas()

    def on_drag_event(self, event):
        if event.button == 1 and self.selected_node.get('public_key', '') == self.root_public_key:
            self.translation['x'] += event.xdata - self.root_node.get_xdata()[0]
            self.translation['y'] += event.ydata - self.root_node.get_ydata()[0]
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

        peer_message = "<b>Peer</b> %s%s..." % (HTML_SPACE * 16, selected_node.get('public_key', '')[:74])
        self.window().tr_selected_node_pub_key.setText(peer_message)

        diff = selected_node.get('total_up', 0) - selected_node.get('total_down', 0)
        color = COLOR_GREEN if diff > 0 else COLOR_RED if diff < 0 else COLOR_DEFAULT
        bandwidth_message = "<b>Bandwidth</b> " + HTML_SPACE * 2 \
                            + " Given " + HTML_SPACE + html_label(format_size(selected_node.get('total_up', 0))) \
                            + " Taken " + HTML_SPACE + html_label(format_size(selected_node.get('total_down', 0))) \
                            + " Balance " + HTML_SPACE + html_label(format_size(diff), color=color)
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
        self.trust_plot.root_public_key = data['root_public_key']
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

        status_message = u"<strong style='font-size:14px'>Transactions : %s | Peers : %s</strong> %s" \
                         % (data['num_tx'], len(data['positions']), TRUST_GRAPH_PEER_LEGENDS)

        self.window().trust_graph_status_bar.setText(status_message)
