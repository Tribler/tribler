from __future__ import absolute_import

import logging
import math
from binascii import unhexlify

import networkx as nx

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.TrustCalculation.graph_positioning import GraphPositioning as gpos
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.exceptions import TrustGraphException
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD


MAX_PEERS = 500
MAX_TRANSACTIONS = 2500


class TrustGraph(nx.DiGraph):

    def __init__(self, root_key, max_peers=MAX_PEERS, max_transactions=MAX_TRANSACTIONS):
        nx.DiGraph.__init__(self)
        self.max_peers = max_peers
        self.max_transactions = max_transactions

        self.root_node = 0

        self.peers = []
        self.get_node(root_key)

        self.transactions = {}
        self.token_balance = {}

    def reset(self, root_key):
        self.peers = []
        self.get_node(root_key)

        self.transactions = {}
        self.token_balance = {}

    def set_limits(self, max_peers, max_transactions):
        self.max_peers = max_peers
        self.max_transactions = max_transactions

    def get_node(self, peer_key, add_if_not_exist=True):
        if peer_key in self.peers:
            return self.node[self.peers.index(peer_key)]
        if add_if_not_exist:
            next_node_id = len(self.peers)
            if next_node_id >= self.max_peers:
                raise TrustGraphException("Max node peers reached in graph")
            super(TrustGraph, self).add_node(next_node_id, id=next_node_id, key=peer_key)
            self.peers.append(peer_key)
            return self.node[self.peers.index(peer_key)]
        return None

    def add_block(self, block):
        if len(self.transactions) >= self.max_transactions:
            raise TrustGraphException("Max transactions reached in the graph")

        if block.hash not in self.transactions and block.type == b'tribler_bandwidth':
            peer1_key = hexlify(block.public_key)
            peer2_key = hexlify(block.link_public_key)

            peer1 = self.get_node(peer1_key, add_if_not_exist=True)
            peer2 = self.get_node(peer2_key, add_if_not_exist=True)

            if block.sequence_number > peer1.get('sequence_number', 0):
                peer1['sequence_number'] = block.sequence_number
                peer1['total_up'] = block.transaction[b"total_up"]
                peer1['total_down'] = block.transaction[b"total_down"]

            diff = block.transaction[b'up'] - block.transaction[b'down']
            if peer2['id'] not in self.successors(peer1['id']):
                self.add_edge(peer1['id'], peer2['id'], weight=diff)
            self.transactions[block.hash] = block

    def add_blocks(self, blocks):
        for block in blocks:
            self.add_block(block)

    def compute_node_graph(self):
        gr_undirected = self.to_undirected()
        num_nodes = len(gr_undirected.node)

        # Remove disconnected nodes from the graph
        component_nodes = nx.node_connected_component(gr_undirected, self.root_node)
        for node in list(gr_undirected.nodes()):
            if node not in component_nodes:
                gr_undirected.remove_node(node)

        # Find bfs tree of the connected components
        bfs_tree = nx.bfs_tree(gr_undirected, self.root_node)

        # Position the nodes in a circular fashion according to the bfs tree
        pos = gpos.hierarchy_pos(bfs_tree, root=self.root_node, width=2 * math.pi, xcenter=0.5)

        graph_nodes = []
        graph_edges = []
        index_mapper = {}

        node_id = 0
        max_x = max_y = 0.0001
        for _id, (theta, r) in pos.items():
            index_mapper[_id] = node_id
            node = gr_undirected.node[_id]
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

        for edge in gr_undirected.edges():
            graph_edges.append((index_mapper[edge[0]], index_mapper[edge[1]]))

        return {'node': graph_nodes, 'edge': graph_edges}


class TrustViewEndpoint(resource.Resource):
    def __init__(self, session):
        resource.Resource.__init__(self)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        self.trustchain_db = None
        self.trust_graph = None
        self.public_key = None

    def initialize_graph(self):
        if self.session.lm.trustchain_community:
            self.trustchain_db = self.session.lm.trustchain_community.persistence
            self.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
            self.trust_graph = TrustGraph(hexlify(self.public_key))

            # Start bootstrap download if not already done
            if not self.session.lm.bootstrap:
                self.session.lm.start_bootstrap_download()

    def render_GET(self, request):
        if not self.trust_graph:
            self.initialize_graph()

        def get_bandwidth_blocks(public_key, limit=5):
            return self.trustchain_db.get_latest_blocks(public_key, limit=limit, block_types=[b'tribler_bandwidth'])

        def get_friends(public_key, limit=5):
            return self.trustchain_db.get_connected_users(public_key, limit=limit)

        depth = 0
        if b'depth' in request.args:
            depth = int(request.args[b'depth'][0])

        # If depth is zero or not provided then fetch all depth levels
        fetch_all = depth == 0

        try:
            if fetch_all:
                self.trust_graph.reset(hexlify(self.public_key))
            if fetch_all or depth == 1:
                self.trust_graph.add_blocks(get_bandwidth_blocks(self.public_key, limit=100))
            if fetch_all or depth == 2:
                for friend in get_friends(self.public_key):
                    self.trust_graph.add_blocks(get_bandwidth_blocks(unhexlify(friend['public_key']), limit=10))
            if fetch_all or depth == 3:
                for friend in get_friends(self.public_key):
                    self.trust_graph.add_blocks(get_bandwidth_blocks(unhexlify(friend['public_key'])))
                    for fof in get_friends(unhexlify(friend['public_key'])):
                        self.trust_graph.add_blocks(get_bandwidth_blocks(unhexlify(fof['public_key'])))
            if fetch_all or depth == 4:
                for user_block in self.trustchain_db.get_users():
                    self.trust_graph.add_blocks(get_bandwidth_blocks(unhexlify(user_block['public_key'])))
        except TrustGraphException as tgex:
            self.logger.warn(tgex)

        graph_data = self.trust_graph.compute_node_graph()

        return json.twisted_dumps(
            {
                'root_public_key': hexlify(self.public_key),
                'graph': graph_data,
                'bootstrap': self.get_bootstrap_info(),
                'num_tx': len(graph_data['edge']),
                'depth': depth,
            }
        )

    def get_bootstrap_info(self):
        if self.session.lm.bootstrap.download and self.session.lm.bootstrap.download.get_state():
            state = self.session.lm.bootstrap.download.get_state()
            return {
                'download': state.get_total_transferred(DOWNLOAD),
                'upload': state.get_total_transferred(UPLOAD),
                'progress': state.get_progress(),
            }
        return {'download': 0, 'upload': 0, 'progress': 0}
