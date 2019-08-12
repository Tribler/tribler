from __future__ import absolute_import

from asyncio import get_event_loop

from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shutdown Tribler.
    """

    def setup_routes(self):
        self.app.add_routes([web.put('', self.shutdown)])

    async def shutdown(self, _):
        """
        Shuts down the fake API
        """
        loop = get_event_loop()
        loop.call_soon(loop.stop)
        return RESTResponse({"shutdown": True})
