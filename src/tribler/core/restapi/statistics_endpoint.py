from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Integer, String

from tribler.core.restapi.rest_endpoint import MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from tribler.core.session import Session


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
        self.session: Session | None = None
        self.content_discovery_community = None

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

        if self.session and self.content_discovery_community:
            stats_dict["peers"] = len(self.content_discovery_community.get_peers())

        if self.session and self.session.mds:
            stats_dict.update({"db_size": self.session.mds.get_db_file_size(),
                               "num_torrents": self.session.mds.get_num_torrents()})

        if self.session and self.session.download_manager:
            lt_stats: dict[str, list[dict]] = {"sessions": []}
            for hops, stats in self.session.download_manager.session_stats.items():
                lt_stats["sessions"].append({
                    "recv_bytes": stats.get("net.recv_bytes", 0),
                    "sent_bytes": stats.get("net.sent_bytes", 0),
                    "dht_recv_bytes": stats.get("dht.dht_bytes_in", 0),
                    "dht_sent_bytes": stats.get("dht.dht_bytes_out", 0),
                    "tracker_recv_bytes": stats.get("net.recv_tracker_bytes", 0),
                    "tracker_sent_bytes": stats.get("net.sent_tracker_bytes", 0),
                    "payload_recv_bytes": stats.get("net.recv_payload_bytes", 0),
                    "payload_sent_bytes": stats.get("net.sent_payload_bytes", 0),
                    "hops": hops
                })
            lt_stats["total_recv_bytes"] = sum([s["recv_bytes"] for s in lt_stats["sessions"]])
            lt_stats["total_sent_bytes"] = sum([s["sent_bytes"] for s in lt_stats["sessions"]])
            stats_dict["libtorrent"] = lt_stats

        if self.session and self.session.socks_servers:
            socks5_stats = []
            for index, server in enumerate(self.session.socks_servers):
                socks5_stats.append({"hops": index,
                                     "sessions": len(server.sessions),
                                     "associates": sum([1 for session in server.sessions if session.udp_connection])})
            stats_dict["socks5_sessions"] = socks5_stats

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
        if self.session and self.session.ipv8:
            stats_dict = {
                "total_up": self.session.ipv8.endpoint.bytes_up,
                "total_down": self.session.ipv8.endpoint.bytes_down
            }
        return RESTResponse({"ipv8_statistics": stats_dict})
