from __future__ import absolute_import

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.unicode import hexlify


class TorrentInfoEndpoint(resource.Resource):

    def render_GET(self, _request):
        metainfo = {
            "info": {
                "files": [{
                    "path": "/test1/file1.txt", "length": 1234
                }, {
                    "path": "/test1/file2.txt", "length": 2534
                }]
            }
        }
        metainfo_dict = {"metainfo": hexlify(json.twisted_dumps(metainfo, ensure_ascii=False))}
        return json.twisted_dumps(metainfo_dict)
