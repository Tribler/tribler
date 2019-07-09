from __future__ import absolute_import

import logging
import math
from binascii import hexlify, unhexlify

import networkx as nx

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.TrustCalculation.graph_positioning import GraphPositioning as gpos
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD


class TrustGraph(nx.DiGraph):

    def __init__(self, root_node):
        nx.DiGraph.__init__(self)
        self.root_node = 0

        self.peers = []
        self.get_node(root_node)

        self.transactions = {}
        self.token_balance = {}

    def get_node(self, peer_key):
        if peer_key not in self.peers:
            node_id = len(self.peers)
            self.peers.append(peer_key)
            super(TrustGraph, self).add_node(node_id, id=node_id, key=peer_key)
        return self.node[self.peers.index(peer_key)]

    def add_block(self, block):
        if block.hash not in self.transactions and block.type == 'tribler_bandwidth':
            peer1_key = hexlify(block.public_key)
            peer2_key = hexlify(block.link_public_key)

            peer1 = self.get_node(peer1_key)
            peer2 = self.get_node(peer2_key)

            if block.sequence_number > peer1.get('sequence_number', 0):
                peer1['sequence_number'] = block.sequence_number
                peer1['total_up'] = block.transaction["total_up"]
                peer1['total_down'] = block.transaction["total_down"]

            diff = block.transaction['up'] - block.transaction['down']
            if peer2['id'] not in self.successors(peer1['id']):
                self.add_edge(peer1['id'], peer2['id'], weight=diff)

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
        pos = gpos.hierarchy_pos(bfs_tree, root=self.root_node, width=num_nodes, xcenter=0.5)

        graph_nodes = []
        graph_edges = []
        index_mapper = {}

        node_id = 0
        for _id, (theta, r) in pos.items():
            index_mapper[_id] = node_id
            node = gr_undirected.node[_id]
            node['pos'] = [r * math.sin(theta) * num_nodes, r * math.cos(theta) * num_nodes]
            node['id'] = node_id
            graph_nodes.append(node)
            node_id += 1

        for edge in gr_undirected.edges():
            graph_edges.append((index_mapper[edge[0]], index_mapper[edge[1]]))

        return {'node': graph_nodes, 'edge': graph_edges}


class TrustViewEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

        self.root_public_key = None
        self.bootstrap = None
        self.initialized = False
        self.trustchain_db = None
        self.trust_graph = None

    def initialize_graph(self):
        if not self.initialized and self.session.lm.trustchain_community:
            pub_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
            self.root_public_key = hexlify(pub_key)
            self.trust_graph = TrustGraph(self.root_public_key)

            self.trustchain_db = self.session.lm.trustchain_community.persistence
            self.initialized = True

            # Start bootstrap download if not already done
            if not self.session.lm.bootstrap:
                self.session.lm.start_bootstrap_download()

    def render_GET(self, _):
        self.initialize_graph()

        # Load your 25 latest trustchain blocks
        pub_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        blocks = self.trustchain_db.get_latest_blocks(pub_key)
        self.trust_graph.add_blocks(blocks)

        # Load 25 latest blocks of all the connected users in the database
        connected_blocks = self.trustchain_db.get_connected_users(pub_key)
        for connected_block in connected_blocks:
            blocks = self.trustchain_db.get_latest_blocks(unhexlify(connected_block['public_key']), limit=25)
            self.trust_graph.add_blocks(blocks)

        # Load 5 latest blocks of all the users in the database
        user_blocks = self.trustchain_db.get_users(limit=-1)
        for user_block in user_blocks:
            blocks = self.trustchain_db.get_latest_blocks(unhexlify(user_block['public_key']), limit=5)
            self.trust_graph.add_blocks(blocks)

        graph_data = self.trust_graph.compute_node_graph()

        return json.twisted_dumps({'root_public_key': self.root_public_key,
                                   'graph': graph_data,
                                   'bootstrap': self.get_bootstrap_info(),
                                   'num_tx': len(graph_data['edge'])
                                  })

    def get_bootstrap_info(self):
        if self.session.lm.bootstrap.download and self.session.lm.bootstrap.download.get_state():
            state = self.session.lm.bootstrap.download.get_state()
            return {'download': state.get_total_transferred(DOWNLOAD),
                    'upload': state.get_total_transferred(UPLOAD),
                    'progress': state.get_progress()
                   }
        return {'download': 0, 'upload': 0, 'progress': 0}
