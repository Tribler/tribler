from __future__ import absolute_import

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class WalletsEndpoint(resource.Resource):

    def render_GET(self, _request):
        wallets = {
            "DUM1": {
                "created": True,
                "unlocked": True,
                "name": "DUM1",
                "address": "DUMMYADDRESS1",
                "balance": {
                    "available": 50,
                    "pending": 0.0,
                },
                "precision": 0
            },
            "DUM2": {
                "created": True,
                "unlocked": True,
                "name": "DUM2",
                "address": "DUMMYADDRESS2",
                "balance": {
                    "available": 90,
                    "pending": 0.0,
                },
                "precision": 1
            }
        }
        return json.twisted_dumps({"wallets": wallets})
