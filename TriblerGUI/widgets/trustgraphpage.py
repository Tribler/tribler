from __future__ import absolute_import, division

import math

from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

import numpy as np
import pyqtgraph as pg
from TriblerGUI.defs import (
    COLOR_DEFAULT,
    COLOR_GREEN,
    COLOR_NEUTRAL,
    COLOR_RED,
    COLOR_ROOT,
    COLOR_SELECTED,
    HTML_SPACE,
    TRUST_GRAPH_PEER_LEGENDS,
)
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, html_label


class TrustGraph(pg.GraphItem):
    def __init__(self):
        pg.GraphItem.__init__(self)
        self.data = None

        # Support dragging the nodes
        self.dragPoint = None
        self.dragOffset = None

    def set_node_selection_listener(self, listener):
        self.scatter.sigClicked.connect(listener)

    def setData(self, **data):
        self.data = data
        if 'pos' in self.data:
            num_nodes = self.data['pos'].shape[0]
            self.data['data'] = np.empty(num_nodes, dtype=[('index', int)])
            self.data['data']['index'] = np.arange(num_nodes)
            pg.GraphItem.setData(self, **self.data)

    def mouseDragEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return

        if event.isStart():
            clicked_position = event.buttonDownPos()
            clicked_nodes = self.scatter.pointsAt(clicked_position)
            if not clicked_nodes:
                event.ignore()
                return

            self.dragPoint = clicked_nodes[0]
            clicked_index = clicked_nodes[0].data()[0]
            self.dragOffset = self.data['pos'][clicked_index] - clicked_position

        elif event.isFinish():
            self.dragPoint = None
            return

        elif self.dragPoint is None:
            event.ignore()
            return

        # Update position of the node and re-render the graph
        clicked_index = self.dragPoint.data()[0]
        if clicked_index == 0:
            event.ignore()
            return
        self.data['pos'][clicked_index] = event.pos() + self.dragOffset

        pg.GraphItem.setData(self, **self.data)
        event.accept()


class TrustGraphPage(QWidget):
    REFRESH_INTERVAL_MS = 2000
    TIMEOUT_INTERVAL_MS = 30000

    def __init__(self):
        QWidget.__init__(self)

        self.graph_request_mgr = TriblerRequestManager()
        self.fetch_data_timer = QTimer()
        self.fetch_data_timeout_timer = QTimer()

        self.trust_graph = None
        self.graph_view = None
        self.selected_node = dict()

        self.root_public_key = None
        self.graph_data = None
        self.graph_depth_to_fetch = 1
        self.refresh_graph_data = False

    def showEvent(self, QShowEvent):
        super(TrustGraphPage, self).showEvent(QShowEvent)
        self.schedule_fetch_data_timer(True)

    def hideEvent(self, QHideEvent):
        super(TrustGraphPage, self).hideEvent(QHideEvent)
        self.stop_fetch_data_request()

    def initialize_trust_graph(self):
        pg.setConfigOption('background', '222222')
        pg.setConfigOption('foreground', '555')
        pg.setConfigOption('antialias', True)

        graph_layout = pg.GraphicsLayoutWidget()
        self.graph_view = graph_layout.addViewBox()
        self.graph_view.setAspectLocked()
        self.graph_view.setMenuEnabled(False)
        self.reset_graph()

        # To disable zoom in the graph, wheel event is overridden. To enable it again, remove the statement below.
        self.graph_view.wheelEvent = lambda evt: None

        self.trust_graph = TrustGraph()
        self.trust_graph.set_node_selection_listener(self.on_node_clicked)
        self.graph_view.addItem(self.trust_graph)
        self.graph_view.addItem(pg.TextItem(text='YOU'))
        self.window().trust_graph_plot_widget.layout().addWidget(graph_layout)

        self.window().tr_control_refresh_btn.clicked.connect(self.refresh_graph)

        self.window().tr_selected_node_pub_key.setHidden(True)
        self.window().tr_selected_node_stats.setHidden(True)
        self.window().trust_graph_progress_bar.setHidden(True)

    def on_node_clicked(self, points):
        clicked_node_data = points.ptsClicked[0].data()
        clicked_node = self.graph_data['node'][clicked_node_data[0]]

        if not self.selected_node:
            self.selected_node = dict()
        elif 'spot' in self.selected_node and self.selected_node['spot']:
            self.selected_node['spot'].setBrush(self.selected_node['color'])

        self.selected_node['public_key'] = clicked_node['key']
        self.selected_node['total_up'] = clicked_node.get('total_up', 0)
        self.selected_node['total_down'] = clicked_node.get('total_down', 0)
        self.selected_node['color'] = self.get_node_color(clicked_node)
        self.selected_node['spot'] = points.ptsClicked[0]

        spot = points.ptsClicked[0]
        spot.setBrush(COLOR_SELECTED)

        self.update_status_bar(self.selected_node)

    def update_status_bar(self, selected_node):
        if not selected_node:
            return

        peer_message = "<b>User</b> %s%s..." % (HTML_SPACE * 16, selected_node.get('public_key', '')[:74])
        self.window().tr_selected_node_pub_key.setHidden(False)
        self.window().tr_selected_node_pub_key.setText(peer_message)

        diff = selected_node.get('total_up', 0) - selected_node.get('total_down', 0)
        color = COLOR_GREEN if diff > 0 else COLOR_RED if diff < 0 else COLOR_DEFAULT
        bandwidth_message = (
            "<b>Bandwidth</b> "
            + HTML_SPACE * 2
            + " Given "
            + HTML_SPACE
            + html_label(format_size(selected_node.get('total_up', 0)))
            + " Taken "
            + HTML_SPACE
            + html_label(format_size(selected_node.get('total_down', 0)))
            + " Balance "
            + HTML_SPACE
            + html_label(format_size(diff), color=color)
        )
        self.window().tr_selected_node_stats.setHidden(False)
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

    def reset_graph(self):
        self.graph_view.setXRange(-1, 1)
        self.graph_view.setYRange(-1, 1)

    def refresh_graph(self):
        self.graph_depth_to_fetch = 0
        self.schedule_fetch_data_timer(now=True)

    def fetch_graph_data(self):
        self.graph_request_mgr.cancel_request()
        self.graph_request_mgr.perform_request("trustview?depth=%d" % self.graph_depth_to_fetch,
                                               self.on_received_data, priority="LOW")

    def on_received_data(self, data):
        if data is None:
            return
        self.update_gui_labels(data)

        self.root_public_key = data['root_public_key']
        self.graph_data = data['graph']

        plot_data = dict()
        plot_data['pxMode'] = False
        plot_data['pen'] = (100, 100, 100, 150)
        plot_data['brush'] = (255, 0, 0, 255)
        plot_data['pos'] = np.array([node[u'pos'] for node in data['graph']['node']])
        plot_data['size'] = np.array([self.get_node_size(node) for node in data['graph']['node']])
        plot_data['symbolBrush'] = np.array([self.get_node_color(node) for node in data['graph']['node']])

        # If there are edges, only then set 'adj' keyword
        if data['graph']['edge']:
            plot_data['adj'] = np.array(data['graph']['edge'])

        self.trust_graph.setData(**plot_data)

        # if depth is less than 4, fetch the next batch
        if 0 < data['depth'] < 4:
            self.graph_depth_to_fetch = data['depth'] + 1
            self.schedule_fetch_data_timer()
        else:
            self.stop_fetch_data_request()

    def get_node_color(self, node, selected=False):
        if not selected and self.root_public_key == node['key']:
            return COLOR_ROOT
        if selected and self.selected_node and self.selected_node.get('public_key', None) == node['key']:
            return COLOR_SELECTED
        diff = node.get('total_up', 0) - node.get('total_down', 0)
        return COLOR_GREEN if diff > 0 else COLOR_NEUTRAL if diff == 0 else COLOR_RED

    def get_node_size(self, node):
        # User root node is bigger than normal nodes
        min_size = 0.01 if node[u'key'] != self.root_public_key else 0.05

        diff = abs(node.get('total_up', 0) - node.get('total_down', 0))
        if diff == 0:
            return min_size

        # magic function to set the node size based on their balance
        return math.log(diff / (1024 * 1024), 2) / 512 + min_size

    def update_gui_labels(self, data):
        header_message = (
            "The graph below is based on your historical interactions with other users in the "
            "network. It shows <strong>%s</strong> interactions made by <strong>%s</strong> users."
            "<br/>" % (data['num_tx'], len(data['graph']['node']))
        )
        self.window().trust_graph_explanation_label.setText(header_message)
        self.window().trust_graph_status_bar.setText(TRUST_GRAPH_PEER_LEGENDS)
