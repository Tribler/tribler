from __future__ import absolute_import

from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class WalletsEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_wallets)])

    async def get_wallets(self, _):
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
        return RESTResponse({"wallets": wallets})
