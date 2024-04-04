from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from ipv8.types import IPv8
from marshmallow.fields import Integer, String

from tribler.core.database.store import MetadataStore
from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """
    path = '/statistics'

    def __init__(self, ipv8: IPv8 = None, metadata_store: MetadataStore = None):
        super().__init__()
        self.mds = metadata_store
        self.ipv8 = ipv8
        self.app.add_routes([web.get('/tribler', self.get_tribler_stats),
                             web.get('/ipv8', self.get_ipv8_stats)])

    @docs(
        tags=["General"],
        summary="Return general statistics of Tribler.",
        responses={
            200: {
                "schema": schema(TriblerStatisticsResponse={
                    'statistics': schema(TriblerStatistics={
                        'database_size': Integer,
                        'torrent_queue_stats': [
                            schema(TorrentQueueStats={
                                'failed': Integer,
                                'total': Integer,
                                'type': String,
                                'pending': Integer,
                                'success': Integer
                            })
                        ],
                    })
                })
            }
        }
    )
    def get_tribler_stats(self, _: web.Request) -> RESTResponse:
        stats_dict = {}
        if self.mds:
            stats_dict = {"db_size": self.mds.get_db_file_size(),
                          "num_torrents": self.mds.get_num_torrents()}

        return RESTResponse({'tribler_statistics': stats_dict})

    @docs(
        tags=["General"],
        summary="Return general statistics of IPv8.",
        responses={
            200: {
                "schema": schema(IPv8StatisticsResponse={
                    'statistics': schema(IPv8Statistics={
                        'total_up': Integer,
                        'total_down': Integer
                    })
                })
            }
        }
    )
    def get_ipv8_stats(self, _: web.Request) -> RESTResponse:
        stats_dict = {}
        if self.ipv8:
            stats_dict = {
                "total_up": self.ipv8.endpoint.bytes_up,
                "total_down": self.ipv8.endpoint.bytes_down
            }
        return RESTResponse({'ipv8_statistics': stats_dict})
