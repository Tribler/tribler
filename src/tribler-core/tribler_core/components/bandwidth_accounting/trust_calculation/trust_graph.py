import hashlib
import logging
import math

import networkx as nx

from tribler_core.exceptions import TrustGraphException
from tribler_core.components.bandwidth_accounting.trust_calculation.graph_positioning import GraphPositioning
from tribler_core.utilities.unicode import hexlify

MAX_NODES = 500
MAX_TRANSACTIONS = 2500
ROOT_NODE_ID = 0


class TrustGraph(nx.DiGraph):

    def __init__(self, root_key, bandwidth_db, max_nodes=MAX_NODES, max_transactions=MAX_TRANSACTIONS):
        nx.DiGraph.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.root_key = root_key
        self.bandwidth_db = bandwidth_db

        self.max_nodes = max_nodes
        self.max_transactions = max_transactions

        self.node_public_keys = []
        self.edge_set = set()

        # The root node is added first so it gets the node id zero.
        self.get_or_create_node(root_key)

    def reset(self, root_key):
        self.clear()
        self.node_public_keys = []
        self.edge_set = set()

        self.get_or_create_node(root_key)

    def set_limits(self, max_nodes=None, max_transactions=None):
        if max_nodes:
            self.max_nodes = max_nodes
        if max_transactions:
            self.max_transactions = max_transactions

    def get_or_create_node(self, peer_key, add_if_not_exist=True):
        if peer_key in self.node_public_keys:
            peer_graph_node_id = self.node_public_keys.index(peer_key)
            return self.nodes()[peer_graph_node_id]

        if not add_if_not_exist:
            return None

        if self.number_of_nodes() >= self.max_nodes:
            raise TrustGraphException(f"Max node peers ({self.max_nodes}) reached in the graph")

        # Node does not exist in the graph so a new node at this point.
        # The numeric node id is used here so the id for the new node becomes
        # equal to the number of nodes in the graph.
        node_id = self.number_of_nodes()
        node_attrs = {
            'id': node_id,
            'key': hexlify(peer_key),
            'total_up': self.bandwidth_db.get_total_given(peer_key),
            'total_down': self.bandwidth_db.get_total_taken(peer_key)
        }
        self.add_node(node_id, **node_attrs)
        self.node_public_keys.append(peer_key)

        return self.nodes()[node_id]

    def compose_graph_data(self):
        # Reset the graph first
        self.reset(self.root_key)

        layer_1 = self.bandwidth_db.get_latest_transactions(self.root_key)
        try:
            for tx in layer_1:
                self.add_bandwidth_transaction(tx)

                # Stop at layer 2
                counter_party = tx.public_key_a if self.root_key != tx.public_key_a else tx.public_key_b
                layer_2 = self.bandwidth_db.get_latest_transactions(counter_party)
                for tx2 in layer_2:
                    self.add_bandwidth_transaction(tx2)

        except TrustGraphException as tge:
            self._logger.warning("Error composing Trust graph: %s", tge)

    def compute_edge_id(self, transaction):
        sha2 = hashlib.sha3_224()  # any safe hashing should do
        sha2.update(transaction.public_key_a)
        sha2.update(transaction.public_key_b)
        return sha2.hexdigest()[:64]

    def add_bandwidth_transaction(self, tx):
        # First, compose a unique edge id for the transaction and check if it is already added.
        edge_id = self.compute_edge_id(tx)

        if len(self.edge_set) >= self.max_transactions:
            raise TrustGraphException(f"Max transactions ({self.max_transactions}) reached in the graph")

        if edge_id not in self.edge_set:
            peer1 = self.get_or_create_node(tx.public_key_a, add_if_not_exist=True)
            peer2 = self.get_or_create_node(tx.public_key_b, add_if_not_exist=True)

            if peer1 and peer2 and peer2['id'] not in self.successors(peer1['id']):
                self.add_edge(peer1['id'], peer2['id'])
                self.edge_set.add(edge_id)

    def compute_node_graph(self):
        undirected_graph = self.to_undirected()
        num_nodes = undirected_graph.number_of_nodes()

        # Find bfs tree of the connected components
        bfs_tree = nx.bfs_tree(undirected_graph, ROOT_NODE_ID)

        # Position the nodes in a circular fashion according to the bfs tree
        pos = GraphPositioning.hierarchy_pos(bfs_tree, root=ROOT_NODE_ID, width=2 * math.pi, xcenter=0.5)

        graph_nodes = []
        graph_edges = []
        index_mapper = {}

        node_id = ROOT_NODE_ID
        max_x = max_y = 0.0001  # as close to zero
        for _id, (theta, r) in pos.items():
            index_mapper[_id] = node_id
            node = undirected_graph.nodes()[_id]
            node['id'] = node_id
            node_id += 1

            # convert from polar coordinates to cartesian coordinates
            x = r * math.sin(theta) * num_nodes
            y = r * math.cos(theta) * num_nodes
            node['pos'] = [x, y]
            graph_nodes.append(node)

            # max values to be used for normalization
            max_x = max(abs(x), max_x)
            max_y = max(abs(y), max_y)

        # Normalize the positions
        for node in graph_nodes:
            node['pos'][0] /= max_x
            node['pos'][1] /= max_y

        for edge in undirected_graph.edges():
            graph_edges.append((index_mapper[edge[0]], index_mapper[edge[1]]))

        return {'node': graph_nodes, 'edge': graph_edges}
