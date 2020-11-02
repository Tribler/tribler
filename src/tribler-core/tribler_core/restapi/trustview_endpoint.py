import logging

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Float, Integer, List, String

from tribler_common.simpledefs import DOWNLOAD, UPLOAD

from tribler_core.modules.trust_calculation.trust_graph import TrustGraph
from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify


class TrustViewEndpoint(RESTEndpoint):
    def __init__(self, session):
        super(TrustViewEndpoint, self).__init__(session)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.bandwidth_db = None
        self.trust_graph = None
        self.public_key = None

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_view)])

    def initialize_graph(self):
        if self.session.bandwidth_community:
            self.bandwidth_db = self.session.bandwidth_community.database
            self.public_key = self.session.bandwidth_community.my_pk
            self.trust_graph = TrustGraph(self.public_key, self.bandwidth_db)

            # Start bootstrap download if not already done
            if not self.session.bootstrap:
                self.session.start_bootstrap_download()

    @docs(
        tags=["TrustGraph"],
        summary="Return the trust graph.",
        parameters=[],
        responses={
            200: {
                "schema": schema(GraphResponse={
                    'root_public_key': String,
                    'graph': schema(Graph={
                        'node': schema(Node={
                            'id': Integer,
                            'key': String,
                            'pos': [Float],
                            'sequence_number': Integer,
                            'total_up': Integer,
                            'total_down': Integer
                        }),
                        'edge': List(List(Integer))
                    }),
                    'bootstrap': schema(Bootstrap={
                        'download': Integer,
                        'upload': Integer,
                        'progress': Float
                    }),
                    'num_tx': Integer
                })
            }
        }
    )
    async def get_view(self, request):
        if not self.trust_graph:
            self.initialize_graph()
            self.trust_graph.compose_graph_data()

        graph_data = self.trust_graph.compute_node_graph()

        return RESTResponse(
            {
                'root_public_key': hexlify(self.public_key),
                'graph': graph_data,
                'bootstrap': self.get_bootstrap_info(),
                'num_tx': len(graph_data['edge'])
            }
        )

    def get_bootstrap_info(self):
        if self.session.bootstrap.download and self.session.bootstrap.download.get_state():
            state = self.session.bootstrap.download.get_state()
            return {
                'download': state.get_total_transferred(DOWNLOAD),
                'upload': state.get_total_transferred(UPLOAD),
                'progress': state.get_progress(),
            }
        return {'download': 0, 'upload': 0, 'progress': 0}
