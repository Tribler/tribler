from functools import cached_property

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Float, Integer, List, String

from tribler_core.components.bandwidth_accounting.trust_calculation.trust_graph import TrustGraph
from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import froze_it


@froze_it
class TrustViewEndpoint(RESTEndpoint):
    def __init__(self):
        super().__init__()
        self.bandwidth_db = None
        self.bandwidth_community = None  # added to simlify the initialization code of BandwidthAccountingComponent

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_view)])

    @cached_property
    def trust_graph(self) -> TrustGraph:
        trust_graph = TrustGraph(self.bandwidth_db.my_pub_key, self.bandwidth_db)
        trust_graph.compose_graph_data()
        return trust_graph

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
        refresh_graph = int(request.query.get('refresh', '0'))
        if refresh_graph:
            self.trust_graph.compose_graph_data()

        graph_data = self.trust_graph.compute_node_graph()

        return RESTResponse(
            {
                'root_public_key': hexlify(self.bandwidth_db.my_pub_key),
                'graph': graph_data,
                'bootstrap': 0,
                'num_tx': len(graph_data['edge'])
            }
        )
