import logging
from binascii import unhexlify, hexlify
import networkx as nx

from twisted.web import resource
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import fix_unicode_dict
from Tribler.Core.Modules.TrustCalculation.local_view import NodeVision
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD


class TrustViewEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

        self.pub_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        self.node_id = hexlify(self.pub_key)
        self.local_view = NodeVision(self.node_id)

        self.bootstrap = None
        self.peers = []
        self.transactions = {}
        self.initialized = False
        self.trustchain_db = self.session.lm.trustchain_community.persistence

    def write_json(self, request, message):
        try:
            message_str = json.twisted_dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            message_str = json.twisted_dumps(fix_unicode_dict(message))
        request.write(message_str)

    def block_to_edge(self, block):
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
        if block.hash not in self.transactions:
            self.transactions[block.hash] = self.block_to_edge(block)

    def load_blocks(self, blocks):
        for block in blocks:
            self.load_single_block(block)

    def render_GET(self, request):
        if not self.initialized:
            self.load_bootstrap()

        # Load your 25 latest trustchain blocks
        blocks = self.trustchain_db.get_latest_blocks(self.pub_key)
        self.load_blocks(blocks)

        # Load 25 latest blocks of all the users in the database
        userblocks = self.trustchain_db.get_users()
        for userblock in userblocks:
            blocks = self.trustchain_db.get_latest_blocks(unhexlify(userblock['public_key']), limit=25)
            self.load_blocks(blocks)

        # Add blocks to graph and update your local view
        self.local_view.add_transactions(self.transactions.values())
        self.local_view.lay_down_nodes()
        self.local_view.reposition_nodes()
        self.local_view.update_component()

        positions = self.local_view.normalize_positions_dict()
        graph_data = nx.node_link_data(self.local_view.component)

        return json.twisted_dumps({'node_id': self.node_id,
                                   'graph_data': graph_data,
                                   'positions': positions,
                                   'bootstrap': self.get_bootstrap_info(),
                                   'num_tx': len(self.transactions)
                                   })

    def load_bootstrap(self):
        if not self.session.lm.bootstrap:
            self.session.lm.start_bootstrap_download()

    def get_bootstrap_info(self):
        if self.session.lm.bootstrap.download and self.session.lm.bootstrap.download.get_state():
            state = self.session.lm.bootstrap.download.get_state()
            return {'download': state.get_total_transferred(DOWNLOAD),
                    'upload': state.get_total_transferred(UPLOAD),
                    'progress': state.get_progress()
                    }
        return {'download': 0, 'upload': 0, 'progress': 0}
