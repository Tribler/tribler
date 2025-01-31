from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, String

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from tribler.core.restapi.rest_manager import TriblerRequest
    from tribler.core.rss.rss import RSSWatcherManager
    from tribler.tribler_config import TriblerConfigManager

    RequestType: TypeAlias = TriblerRequest[tuple[RSSWatcherManager, TriblerConfigManager]]


class RSSEndpoint(RESTEndpoint):
    """
    This endpoint allow.
    """

    path = "/api/rss"

    def __init__(self) -> None:
        """
        Create a new endpoint to update the registered RSS feeds.
        """
        super().__init__()

        self.manager: RSSWatcherManager | None = None
        self.config: TriblerConfigManager | None = None
        self.required_components = ("manager", "config")

        self.app.add_routes([web.put("", self.update_feeds)])

    @docs(
        tags=["RSS"],
        summary="Set the current RSS feeds.",
        parameters=[],
        responses={
            200: {
                "schema": schema(
                    RSSResponse={
                        "modified": Boolean,
                    }
                ),
                "examples": {"modified": True},
            }
        },
    )
    @json_schema(schema(RSSFeeds={
        "urls": ([String], "the RSS URLs to listen to")
    }))
    async def update_feeds(self, request: RequestType) -> RESTResponse:
        """
        Set the current RSS feeds.
        """
        urls = (await request.json())["urls"]

        request.context[0].update(urls)  # context[0] = self.manager
        request.context[1].set("rss/urls", urls)  # context[1] = self.config

        return RESTResponse({"modified": True})
