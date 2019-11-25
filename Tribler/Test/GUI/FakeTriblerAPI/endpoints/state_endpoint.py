from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StateEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_state)])

    async def get_state(self, _):
        return RESTResponse({"state": "STARTED", "last_exception": None, "readable_state": "Starting..."})
