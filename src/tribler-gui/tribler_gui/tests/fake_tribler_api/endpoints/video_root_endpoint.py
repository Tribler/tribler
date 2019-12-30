import os

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint

import tribler_gui


class VideoRootEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.static('/{anything:.*}',
                                        os.path.join(os.path.dirname(tribler_gui.tests.fake_tribler_api.__file__),
                                                     "data", "video.avi"))])
