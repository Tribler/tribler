from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

import tribler_gui.tests.fake_tribler_api.tribler_utils as tribler_utils


class SettingsEndpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_settings), web.post('', self.save_settings)])

    # Only contains the most necessary settings needed for the GUI
    async def get_settings(self, _request):
        return RESTResponse(tribler_utils.tribler_data.settings)

    # Do nothing when we are saving the settings
    async def save_settings(self, _):
        return RESTResponse({"modified": True})
