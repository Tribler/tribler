import json

from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi import has_param, get_param
from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


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
        timeout = 3600.0
        if has_param(parameters, 'timeout'):
            timeout = float(get_param(parameters, 'timeout'))

        price = int(get_param(parameters, 'price'))
        quantity = int(get_param(parameters, 'quantity'))

        price_type = get_param(parameters, 'price_type')
        quantity_type = get_param(parameters, 'quantity_type')

        return price, price_type, quantity, quantity_type, timeout


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
                        "price_type": "BTC",
                        "quantity_type": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "quantity_type": "MB",
                            "price_type": "BTC",
                            "timestamp": 1493905920.68573,
                            "price": 10.0,
                            "order_number": 1,
                            "quantity": 10.0}, ...]
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
                "price=10&quantity=10&price_type=BTC&quantity_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "created": True
                }
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'price') or not has_param(parameters, 'quantity'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price or quantity parameter missing"})

        if not has_param(parameters, 'price_type') or not has_param(parameters, 'quantity_type'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price_type or quantity_type parameter missing"})

        def on_ask_created(_):
            if not request.finished:
                request.write(json.dumps({"created": True}))
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
                        "price_type": "BTC",
                        "quantity_type": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "quantity_type": "MB",
                            "price_type": "BTC",
                            "timestamp": 1493905920.68573,
                            "price": 10.0,
                            "order_number": 1,
                            "quantity": 10.0}, ...]
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
                "price=10&quantity=10&price_type=BTC&quantity_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "created": True
                }
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'price') or not has_param(parameters, 'quantity'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price or quantity parameter missing"})

        if not has_param(parameters, 'price_type') or not has_param(parameters, 'quantity_type'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price_type or quantity_type parameter missing"})

        def on_bid_created(_):
            if not request.finished:
                request.write(json.dumps({"created": True}))
                request.finish()

        self.get_market_community().create_bid(*BaseAsksBidsEndpoint.create_ask_bid_from_params(parameters))\
            .addCallback(on_bid_created)

        return NOT_DONE_YET
