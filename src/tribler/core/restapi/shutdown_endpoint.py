from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from tribler.core.session import Session


class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shut down Tribler.
    """

    path = "/api/shutdown"

    def __init__(self, session: Session) -> None:
        """
        Create a new shutdown endpoint.
        """
        super().__init__()
        self.session = session
        self.app.add_routes([web.put("", self.shutdown_request)])

    @docs(
        tags=["General"],
        summary="Shutdown Tribler.",
        responses={
            200: {
                "schema": schema(TriblerShutdownResponse={
                    "restart": Boolean
                })
            }
        }
    )
    def shutdown_request(self, request: web.Request) -> RESTResponse:
        """
        Shutdown Tribler.
        """
        self._logger.info("Received a shutdown request from GUI")

        self.session.restart_requested = bool(int(request.query.get("restart", "0")))
        self.session.shutdown_event.set()

        return RESTResponse({"shutdown": True})
