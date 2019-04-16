import logging
from twisted.web import resource
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import fix_unicode_dict
from Tribler.Core.Modules.TrustCalculation.local_view import NodeVision


class TrustViewEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)
        self.local_view = NodeVision(0)

    def write_json(self, request, message):
        try:
            message_str = json.twisted_dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            message_str = json.twisted_dumps(fix_unicode_dict(message))
        request.write(message_str)

    def render_GET(self, request):
        from random import randint, random
        import networkx as nx
        # gr = nx.watts_strogatz_graph(10, 4, 0.5)

        # Add random transactions
        trs = []
        for i in range(0, 20):
            n1 = randint(0, 50)
            n2 = randint(0, 50)
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
        return json.twisted_dumps({'graph_data': grs, 'positions': pos})
