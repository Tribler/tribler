import json

from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from Tribler.Core.Utilities.unicode import hexlify


class TorrentInfoEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_info)])

    async def get_info(self, _request):
        metainfo = {
            "info": {
                "files": [{
                    "path": "/test1/file1.txt", "length": 1234
                }, {
                    "path": "/test1/file2.txt", "length": 2534
                }]
            }
        }
        metainfo_dict = {"metainfo": hexlify(json.dumps(metainfo, ensure_ascii=False))}
        return RESTResponse(metainfo_dict)
