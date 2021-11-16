from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from tribler_core.components.bandwidth_accounting.community.bandwidth_accounting_community import (
    BandwidthAccountingCommunity,
)
from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.utilities import froze_it


@froze_it
class BandwidthEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests for bandwidth accounting data.
    """

    def __init__(self, bandwidth_community: BandwidthAccountingCommunity):
        super().__init__()
        self.bandwidth_community = bandwidth_community

    def setup_routes(self) -> None:
        self.app.add_routes([web.get('/statistics', self.get_statistics)])
        self.app.add_routes([web.get('/history', self.get_history)])

    @docs(
        tags=["Bandwidth"],
        summary="Return statistics about the bandwidth community.",
        responses={
            200: {
                "schema": schema(BandwidthStatisticsResponse={
                    'statistics': schema(BandwidthStatistics={
                        'id': String,
                        'num_peers_helped': Integer,
                        'num_peers_helped_by': Integer,
                        'total_taken': Integer,
                        'total_given': Integer
                    })
                })
            }
        }
    )
    async def get_statistics(self, request) -> RESTResponse:
        return RESTResponse({'statistics': self.bandwidth_community.get_statistics()})

    @docs(
        tags=["Bandwidth"],
        summary="Return a list of the balance history.",
        responses={
            200: {
                "schema": schema(BandwidthHistoryResponse={
                    "history": [schema(BandwidthHistoryItem={
                        "timestamp": Integer,
                        "balance": Integer
                    })
                    ]
                })
            }
        }
    )
    async def get_history(self, request) -> RESTResponse:
        return RESTResponse({'history': self.bandwidth_community.database.get_history()})
