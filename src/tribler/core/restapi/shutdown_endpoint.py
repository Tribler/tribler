from typing import Callable

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shut down Tribler.
    """

    path = "/api/shutdown"

    def __init__(self, shutdown_callback: Callable[[], None]) -> None:
        """
        Create a new shutdown endpoint.
        """
        super().__init__()
        self.shutdown_callback = shutdown_callback
        self.app.add_routes([web.put("", self.shutdown_request)])

    @docs(
        tags=["General"],
        summary="Shutdown Tribler.",
        responses={
            200: {
                "schema": schema(TriblerShutdownResponse={
                    "shutdown": Boolean
                })
            }
        }
    )
    def shutdown_request(self, _: web.Request) -> RESTResponse:
        """
        Shutdown Tribler.
        """
        self._logger.info("Received a shutdown request from GUI")
        self.shutdown_callback()
        return RESTResponse({"shutdown": True})
