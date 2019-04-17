import logging
from random import choice, randint, random
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
        self.local_view = NodeVision(0)

        self.bootstrap = None
        self.peers = []

    def write_json(self, request, message):
        try:
            message_str = json.twisted_dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            message_str = json.twisted_dumps(fix_unicode_dict(message))
        request.write(message_str)

    def render_GET(self, request):
        bootstrap = self.load_bootstrap()
        peers = bootstrap.get_bootstrap_peers(dht=self.session.lm.dht_community)

        from random import randint, random
        import networkx as nx
        # gr = nx.watts_strogatz_graph(10, 4, 0.5)

        # Add random transactions
        trs = []
        for i in range(0, 2):
            n1 = randint(0, 5)
            n2 = randint(0, 5)
            if n1 == n2:
                continue
            trs.append({'downloader': n1,
                        'uploader': n2,
                        'amount': random() * 20})

        self.local_view.add_transactions(trs)
        self.local_view.lay_down_nodes()
        self.local_view.reposition_nodes()
        self.local_view.update_component()

        gr = self.local_view.component
        pos = self.local_view.pos
        pos = self.local_view.normalize_positions_dict()
        # pos = {}
        # for n in gr.nodes():
        #     pos[n] = (random(), random())
        grs = nx.node_link_data(gr)
        return json.twisted_dumps({'graph_data': grs, 'positions': pos, 'bootstrap': self.get_bootstrap_info()})

    def load_bootstrap(self):
        if self.bootstrap:
            return self.bootstrap
        if not self.session.lm.bootstrap:
            self.bootstrap = self.session.lm.start_bootstrap_download()
        return self.session.lm.bootstrap

    def get_bootstrap_info(self):
        if self.session.lm.bootstrap.download and self.session.lm.bootstrap.download.get_state():
            state = self.session.lm.bootstrap.download.get_state()
            return {'download': state.get_total_transferred(DOWNLOAD),
                    'upload': state.get_total_transferred(UPLOAD),
                    'progress': state.get_progress()
                    }
        return dict()
