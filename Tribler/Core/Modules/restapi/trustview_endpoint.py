from __future__ import absolute_import

import logging
from binascii import hexlify, unhexlify

from networkx.readwrite import json_graph

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.TrustCalculation.local_view import NodeVision
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD


class TrustViewEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

        self.node_id = None
        self.local_view = None

        self.bootstrap = None
        self.peers = []
        self.transactions = {}
        self.token_balance = {}
        self.initialized = False
        self.trustchain_db = None

    def initialize_graph(self):
        if not self.initialized and self.session.lm.trustchain_community and not self.local_view:
            pub_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
            self.node_id = hexlify(pub_key)
            self.local_view = NodeVision(self.node_id)
            self.trustchain_db = self.session.lm.trustchain_community.persistence
            self.initialized = True

            # Start bootstrap download if not already done
            if not self.session.lm.bootstrap:
                self.session.lm.start_bootstrap_download()

    @staticmethod
    def block_to_edge(block):
        if not block:
            return None

        diff = block.transaction['up'] - block.transaction['down']
        if diff < 0:
            return {'downloader': hexlify(block.public_key),
                    'uploader': hexlify(block.link_public_key),
                    'amount': diff * -1
                   }
        return {'downloader': hexlify(block.link_public_key),
                'uploader': hexlify(block.public_key),
                'amount': diff
               }

    def load_single_block(self, block):
        if block.hash not in self.transactions and block.type == 'tribler_bandwidth':
            self.transactions[block.hash] = self.block_to_edge(block)
            # Update token balance
            hex_public_key = hexlify(block.public_key)
            node_balance = self.token_balance.get(hex_public_key, dict())
            if block.sequence_number > node_balance.get('sequence_number', 0):
                node_balance['sequence_number'] = block.sequence_number
                node_balance['total_up'] = block.transaction["total_up"]
                node_balance['total_down'] = block.transaction["total_down"]
                self.token_balance[hex_public_key] = node_balance

    def load_blocks(self, blocks):
        for block in blocks:
            self.load_single_block(block)

    def render_GET(self, _):
        self.initialize_graph()

        # Load your 25 latest trustchain blocks
        pub_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        blocks = self.trustchain_db.get_latest_blocks(pub_key)
        self.load_blocks(blocks)

        # Load 5 latest blocks of all the connected users in the database
        userblocks = self.trustchain_db.get_connected_users(pub_key)
        for userblock in userblocks:
            blocks = self.trustchain_db.get_latest_blocks(unhexlify(userblock['public_key']), limit=5)
            self.load_blocks(blocks)

        # Add blocks to graph and update your local view
        self.local_view.add_transactions(self.transactions.values())
        self.local_view.lay_down_nodes()
        self.local_view.reposition_nodes()
        self.local_view.update_component()

        positions = self.local_view.normalize_positions_dict()
        graph_data = json_graph.node_link_data(self.local_view.component)

        return json.twisted_dumps({'node_id': self.node_id,
                                   'graph_data': graph_data,
                                   'positions': positions,
                                   'bootstrap': self.get_bootstrap_info(),
                                   'num_tx': len(self.transactions),
                                   'token_balance': self.token_balance
                                  })

    def get_bootstrap_info(self):
        if self.session.lm.bootstrap.download and self.session.lm.bootstrap.download.get_state():
            state = self.session.lm.bootstrap.download.get_state()
            return {'download': state.get_total_transferred(DOWNLOAD),
                    'upload': state.get_total_transferred(UPLOAD),
                    'progress': state.get_progress()
                   }
        return {'download': 0, 'upload': 0, 'progress': 0}
