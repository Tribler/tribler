import json

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify


class TorrentInfoEndpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_info)])

    async def get_info(self, _request):
        metainfo = {
            "info": {
                "files": [{"path": "/test1/file1.txt", "length": 1234}, {"path": "/test1/file2.txt", "length": 2534}]
            }
        }
        metainfo_dict = {"metainfo": hexlify(json.dumps(metainfo, ensure_ascii=False).encode())}
        return RESTResponse(metainfo_dict)
