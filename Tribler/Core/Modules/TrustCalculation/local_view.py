import networkx as nx
import matplotlib.pyplot as plt
import math
from Tribler.Core.Modules.TrustCalculation.graph_positioning import GraphPositioning as gpos
from random import choice, random


class NodeVision(object):
    """
    This object is used for laying out the nodes of a graph according to \
    the local vision of a specific node (root node)
    """

    def __init__(self, root_node):
        """
        :param graph: Peer network
        :param root_node: Transaction keypair of the node
        """

        self.graph = nx.DiGraph()
        self.graph.add_node(root_node)

        self.root_node = root_node
        self.bfs_tree = {} # Bfs tree rooted at the peer
        self.component = None  # The connected component which includes the peer


        self.pos = self.lay_down_nodes()
        self.component_pos = dict(self.pos)

        self.update_component()

    def set_root_node(self, rootnode):
        self.root_node = rootnode
        self.pos = self.lay_down_nodes()

    @property
    def n_nodes(self):
        return self.graph.number_of_nodes()

    @property
    def node_positions(self):
        return dict(self.graph.nodes(data='pos'))

    def reposition_nodes(self):
        self.pos = self.lay_down_nodes()
        self.component_pos = self.normalize_positions_dict()

    def lay_down_nodes(self):
        """
        Given a directed graph, finds the connected component which includes
        the root node and then determines positions in the circular view.

        :return: Positions of the nodes from the perspective of the root node
        !!! returned dict does not contain positions of unconnected nodes!
        """
        # Find undirected graph (needed for connected component discovery)
        gr_undirected = self.graph.to_undirected()

        # Remove disconnected nodes from the graph
        component_nodes = nx.node_connected_component(gr_undirected, self.root_node)
        for node in list(gr_undirected.nodes()):
            if node not in component_nodes:
                gr_undirected.remove_node(node)

        # Find bfs tree of the connected components
        bfs_tree = nx.bfs_tree(gr_undirected, self.root_node)
        self.bfs_tree[self.root_node] = bfs_tree

        # Position the nodes in a circular fashion according to the bfs tree
        pos = gpos.hierarchy_pos(bfs_tree, self.root_node,
                                 width=2 * math.pi, xcenter=0.5)
        new_pos = {u: (r * math.cos(theta), r * math.sin(theta))
                   for u, (theta, r) in pos.items()}

        # Set positions to the networkx object
        nx.set_node_attributes(self.graph, new_pos, 'pos')

        # Also, return the positions
        return new_pos

    def normalize_positions_dict(self, width=0.80, margin=0.05):
        poslist = [v for v in self.pos.values() if v is not None]
        minx = min(poslist, key=lambda t: t[0])[0]
        miny = min(poslist, key=lambda t: t[1])[1]
        maxx = max(poslist, key=lambda t: t[0])[0]
        maxy = max(poslist, key=lambda t: t[1])[1]
        xinterval = (maxx - minx)
        yinterval = (maxy - miny)

        # To escape from division by zero:
        if xinterval == 0:
            xinterval = 1.0
        if yinterval == 0:
            yinterval = 1.0

        newposlist = {}

        for node, pos in self.pos.items():
            if pos is not None:
                nposx = ((pos[0] - minx) / xinterval) * width + margin
                nposy = ((pos[1] - miny) / yinterval) * width + margin
                newposlist[node] = (nposx, nposy)

        return newposlist

    def add_transactions(self, transactions):
        for tr in transactions:
            self.add_edge_to_graph(tr['downloader'],
                                   tr['uploader'],
                                   tr['amount'])

    def add_edge_to_graph(self, n1, n2, w):
        if n1 in self.graph and n2 in self.graph.successors(n1):
            self.graph[n1][n2]['weight'] *= 0.8
            self.graph[n1][n2]['weight'] += (0.2 * w)
            # print('Existing edge !!!')
        else:
            # print('Non-Existing edge !!!')
            self.graph.add_edge(n1, n2, weight=w)

    def update_component(self):
        H = self.graph.to_undirected()
        self.component = nx.DiGraph(self.graph)

        component_nodes = nx.node_connected_component(H, self.root_node)
        for node in self.graph:
            if node not in component_nodes:
                self.component.remove_node(node)

    # def make_random_transactions(self, tr_count):
    #     trs = []
    #     for i in range(tr_count):
    #         neigh = choice(list(self.graph.nodes().keys()))
    #         if neigh == self.root_node:
    #             continue
    #         if random() > 0.3:
    #             trs.append({'downloader': self.root_node,
    #                         'uploader': neigh,
    #                         'amount': random() * 100})
    #         else:
    #             trs.append({'downloader': neigh,
    #                         'uploader': self.root_node,
    #                         'amount': random() * 100})
    #     self.add_transactions(trs)
    #
    #
    #
    # def diminish_weights(self, remove=True):
    #     to_be_removed = []
    #     n_rem, n_not_rem = 0, 0
    #     for n1, n2 in self.graph.edges():
    #         self.graph[n1][n2]['weight'] *= 0.9
    #         if self.graph[n1][n2]['weight'] < 0.5:
    #             n_rem += 1
    #             to_be_removed.append((n1, n2))
    #         else:
    #             n_not_rem += 1
    #     if remove:
    #         print('Removed: {}, Not removed: {}'.format(n_rem, n_not_rem))
    #         self.graph.remove_edges_from(to_be_removed)
    #
    # def normalize_edge_weights(self, minwidth=0.5, maxwidth=2):
    #     weights = [w for (n1, n2, w) in self.graph.edges(data='weight')]
    #     maxw = max(weights)
    #     minw = min(weights)
    #
    #     width_diff = (maxwidth - minwidth)
    #     weight_diff = (maxw - minw)
    #
    #     for n1, n2 in self.graph.edges():
    #         w = self.graph[n1][n2]['weight']
    #         self.graph[n1][n2]['weight'] = minwidth + (width_diff
    #                                                    * ((w - minw)
    #                                                       / weight_diff))
    #


