from __future__ import absolute_import

from twisted.web import http
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi import get_param, has_param
from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair


class BaseAsksBidsEndpoint(BaseMarketEndpoint):
    """
    This class acts as the base class for the asks/bids endpoint.
    """

    @staticmethod
    def create_ask_bid_from_params(parameters):
        """
        Create an ask/bid from the provided parameters in a request. This method returns a tuple with the price,
        quantity and timeout of the ask/bid.
        """
        timeout = 3600
        if has_param(parameters, 'timeout'):
            timeout = int(get_param(parameters, 'timeout'))

        first_asset_amount = int(get_param(parameters, 'first_asset_amount'))
        second_asset_amount = int(get_param(parameters, 'second_asset_amount'))

        first_asset_type = get_param(parameters, 'first_asset_type')
        second_asset_type = get_param(parameters, 'second_asset_type')

        return AssetPair(AssetAmount(first_asset_amount, first_asset_type),
                         AssetAmount(second_asset_amount, second_asset_type)), timeout


class AsksEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding asks in the market community.
    """

    def render_GET(self, request):
        """
        .. http:get:: /market/asks

        A GET request to this endpoint will return all ask ticks in the order book of the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/asks

            **Example response**:

            .. sourcecode:: javascript

                {
                    "asks": [{
                        "asset1": "BTC",
                        "asset2": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "assets": {
                                "first": {
                                    "amount": 10,
                                    "type": "BTC"
                                },
                                "second": {
                                    "amount": 10,
                                    "type": "MB"
                                }
                            },
                            "traded": 5,
                            "timestamp": 1493905920.68573,
                            "order_number": 1}, ...]
                    }, ...]
                }
        """
        return json.dumps({"asks": self.get_market_community().order_book.asks.get_list_representation()})

    def render_PUT(self, request):
        """
        .. http:put:: /market/asks

        A request to this endpoint will create a new ask order.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/market/asks --data
                "first_asset_amount=10&second_asset_amount=10&first_asset_type=BTC&second_asset_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                     "timestamp": 1547587907.887339,
                     "order_number": 12,
                     "assets": {
                        "second": {
                            "amount": 1000,
                            "type": "MB"
                        },
                        "first": {
                            "amount": 100000,
                            "type": "BTC"
                        }
                    },
                    "timeout": 3600,
                    "trader_id": "9695c9e15201d08586e4230f4a8524799ebcb2d7"
                }
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'first_asset_amount') or not has_param(parameters, 'second_asset_amount'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "asset amount parameter missing"})

        if not has_param(parameters, 'first_asset_type') or not has_param(parameters, 'second_asset_type'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "asset type parameter missing"})

        def on_ask_created(ask):
            if not request.finished:
                request.write(json.dumps({
                    'assets': ask.assets.to_dictionary(),
                    'timestamp': int(ask.timestamp),
                    'trader_id': ask.order_id.trader_id.as_hex(),
                    'order_number': int(ask.order_id.order_number),
                    'timeout': int(ask.timeout)
                }))
                request.finish()

        self.get_market_community().create_ask(*BaseAsksBidsEndpoint.create_ask_bid_from_params(parameters))\
            .addCallback(on_ask_created)

        return NOT_DONE_YET


class BidsEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding bids in the market community.
    """

    def render_GET(self, request):
        """
        .. http:get:: /market/bids

        A GET request to this endpoint will return all bid ticks in the order book of the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/bids

            **Example response**:

            .. sourcecode:: javascript

                {
                    "bids": [{
                        "asset1": "BTC",
                        "asset2": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "assets": {
                                "first": {
                                    "amount": 10,
                                    "type": "BTC"
                                },
                                "second": {
                                    "amount": 10,
                                    "type": "MB"
                                }
                            },
                            "traded": 5,
                            "timestamp": 1493905920.68573,
                            "order_number": 1}, ...]
                    }, ...]
                }
        """
        return json.dumps({"bids": self.get_market_community().order_book.bids.get_list_representation()})

    def render_PUT(self, request):
        """
        .. http:put:: /market/bids

        A request to this endpoint will create a new bid order.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/market/bids --data
                "first_asset_amount=10&second_asset_amount=10&first_asset_type=BTC&second_asset_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                     "timestamp": 1547587907.887339,
                     "order_number": 12,
                     "assets": {
                        "second": {
                            "amount": 1000,
                            "type": "MB"
                        },
                        "first": {
                            "amount": 100000,
                            "type": "BTC"
                        }
                    },
                    "timeout": 3600,
                    "trader_id": "9695c9e15201d08586e4230f4a8524799ebcb2d7"
                }
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'first_asset_amount') or not has_param(parameters, 'second_asset_amount'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "asset amount parameter missing"})

        if not has_param(parameters, 'first_asset_type') or not has_param(parameters, 'second_asset_type'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "asset type parameter missing"})

        def on_bid_created(bid):
            if not request.finished:
                request.write(json.dumps({
                    'assets': bid.assets.to_dictionary(),
                    'timestamp': int(bid.timestamp),
                    'trader_id': bid.order_id.trader_id.as_hex(),
                    'order_number': int(bid.order_id.order_number),
                    'timeout': int(bid.timeout)
                }))
                request.finish()

        self.get_market_community().create_bid(*BaseAsksBidsEndpoint.create_ask_bid_from_params(parameters))\
            .addCallback(on_bid_created)

        return NOT_DONE_YET
