
from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean

from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.utilities import froze_it


@froze_it
class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shutdown Tribler.
    """

    def __init__(self):
        super().__init__()
        self.shutdown_callback = None

    def connect_shutdown_callback(self, shutdown_callback):
        self.shutdown_callback = shutdown_callback

    def setup_routes(self):
        self.app.add_routes([web.put('', self.shutdown)])

    @docs(
        tags=["General"],
        summary="Shutdown Tribler.",
        responses={
            200: {
                "schema": schema(TriblerShutdownResponse={
                    'shutdown': Boolean
                })
            }
        }
    )
    async def shutdown(self, request):

        self.shutdown_callback()
        return RESTResponse({"shutdown": True})
