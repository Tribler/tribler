import logging
from twisted.web import resource
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import fix_unicode_dict


class TrustViewEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

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
        gr = nx.watts_strogatz_graph(10, 4, 0.5)
        pos = {}
        for n in gr.nodes():
            pos[n] = (random(), random())
        grs = nx.node_link_data(gr)
        return json.twisted_dumps({'graph_data': grs, 'positions': pos})
