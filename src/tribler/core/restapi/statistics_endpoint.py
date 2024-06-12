from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Integer, String

from tribler.core.restapi.rest_endpoint import MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from ipv8.types import IPv8

    from tribler.core.database.store import MetadataStore


class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    path = "/api/statistics"

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new statistics endpoint.
        """
        super().__init__(middlewares, client_max_size)

        self.mds: MetadataStore | None = None
        self.ipv8: IPv8 | None = None

        self.app.add_routes([web.get("/tribler", self.get_tribler_stats),
                             web.get("/ipv8", self.get_ipv8_stats)])

    @docs(
        tags=["General"],
        summary="Return general statistics of Tribler.",
        responses={
            200: {
                "schema": schema(TriblerStatisticsResponse={
                    "statistics": schema(TriblerStatistics={
                        "database_size": Integer,
                        "torrent_queue_stats": [
                            schema(TorrentQueueStats={
                                "failed": Integer,
                                "total": Integer,
                                "type": String,
                                "pending": Integer,
                                "success": Integer
                            })
                        ],
                    })
                })
            }
        }
    )
    def get_tribler_stats(self, _: web.Request) -> RESTResponse:
        """
        Return general statistics of Tribler.
        """
        stats_dict = {}
        if self.mds:
            stats_dict = {"db_size": self.mds.get_db_file_size(),
                          "num_torrents": self.mds.get_num_torrents()}

        return RESTResponse({"tribler_statistics": stats_dict})

    @docs(
        tags=["General"],
        summary="Return general statistics of IPv8.",
        responses={
            200: {
                "schema": schema(IPv8StatisticsResponse={
                    "statistics": schema(IPv8Statistics={
                        "total_up": Integer,
                        "total_down": Integer
                    })
                })
            }
        }
    )
    def get_ipv8_stats(self, _: web.Request) -> RESTResponse:
        """
        Return general statistics of IPv8.
        """
        stats_dict = {}
        if self.ipv8:
            stats_dict = {
                "total_up": self.ipv8.endpoint.bytes_up,
                "total_down": self.ipv8.endpoint.bytes_down
            }
        return RESTResponse({"ipv8_statistics": stats_dict})
