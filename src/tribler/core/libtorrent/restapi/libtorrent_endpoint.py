from __future__ import annotations

from asyncio import Future
from binascii import hexlify
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Integer

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    import libtorrent
    from aiohttp.abc import Request

    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager


class LibTorrentEndpoint(RESTEndpoint):
    """
    Endpoint for getting information about libtorrent sessions and settings.
    """

    path = "/api/libtorrent"

    def __init__(self, download_manager: DownloadManager) -> None:
        """
        Create a new libtorrent endpoint.
        """
        super().__init__()
        self.download_manager = download_manager
        self.app.add_routes([web.get("/settings", self.get_libtorrent_settings),
                             web.get("/session", self.get_libtorrent_session_info)])

    @docs(
        tags=["Libtorrent"],
        summary="Return Libtorrent session settings.",
        parameters=[{
            "in": "query",
            "name": "hop",
            "description": "The hop count of the session for which to return settings",
            "type": "string",
            "required": False
        }],
        responses={
            200: {
                "description": "Return a dictonary with key-value pairs from the Libtorrent session settings",
                "schema": schema(LibtorrentSessionResponse={"hop": Integer,
                                                            "settings": schema(LibtorrentSettings={})})
            }
        }
    )
    async def get_libtorrent_settings(self, request: Request) -> RESTResponse:
        """
        Return Libtorrent session settings.
        """
        args = request.query
        hop = 0
        if args.get("hop"):
            hop = int(args["hop"])

        if hop not in self.download_manager.ltsessions:
            return RESTResponse({"hop": hop, "settings": {}})

        lt_session = await self.download_manager.ltsessions[hop]
        if hop == 0:
            lt_settings = self.download_manager.get_session_settings(lt_session)
            lt_settings["peer_fingerprint"] = hexlify(lt_settings["peer_fingerprint"].encode()).decode()
        else:
            lt_settings = lt_session.get_settings()

        return RESTResponse({"hop": hop, "settings": lt_settings})

    @docs(
        tags=["Libtorrent"],
        summary="Return Libtorrent session information.",
        parameters=[{
            "in": "query",
            "name": "hop",
            "description": "The hop count of the session for which to return information",
            "type": "string",
            "required": False
        }],
        responses={
            200: {
                "description": "Return a dictonary with key-value pairs from the Libtorrent session information",
                "schema": schema(LibtorrentinfoResponse={"hop": Integer,
                                                         "settings": schema(LibtorrentInfo={})})
            }
        }
    )
    async def get_libtorrent_session_info(self, request: Request) -> RESTResponse:
        """
        Return Libtorrent session information.
        """
        session_stats: Future[dict[str, int]] = Future()

        def on_session_stats_alert_received(alert: libtorrent.session_stats_alert) -> None:
            if not session_stats.done():
                session_stats.set_result(alert.values)

        args = request.query
        hop = 0
        if args.get("hop"):
            hop = int(args["hop"])

        if hop not in self.download_manager.ltsessions or \
                not hasattr(self.download_manager.ltsessions[hop].result(), "post_session_stats"):
            return RESTResponse({"hop": hop, "session": {}})

        self.download_manager.session_stats_callback = on_session_stats_alert_received
        (await self.download_manager.ltsessions[hop]).post_session_stats()
        stats = await session_stats
        return RESTResponse({"hop": hop, "session": stats})
