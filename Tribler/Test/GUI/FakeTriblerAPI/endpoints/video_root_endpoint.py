import os

from aiohttp import web

import Tribler.Test.GUI.FakeTriblerAPI
from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint


class VideoRootEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.static('/{anything:.*}',
                                        os.path.join(os.path.dirname(Tribler.Test.GUI.FakeTriblerAPI.__file__),
                                                     "data", "video.avi"))])
