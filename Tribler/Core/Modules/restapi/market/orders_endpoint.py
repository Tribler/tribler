from __future__ import absolute_import

from twisted.web import http

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber


class OrdersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your orders in the market community.
    """

    def getChild(self, path, request):
        return OrderSpecificEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /market/orders

        A GET request to this endpoint will return all your orders in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/orders

            **Example response**:

            .. sourcecode:: javascript

                {
                    "orders": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "timestamp": 1493906434.627721,
                        "assets" {
                            "first": {
                                "amount": 3,
                                "type": "BTC",
                            },
                            "second": {
                                "amount": 3,
                                "type": "MB",
                            }
                        }
                        "reserved_quantity": 0,
                        "is_ask": False,
                        "timeout": 3600,
                        "traded": 0,
                        "order_number": 1,
                        "completed_timestamp": null,
                        "cancelled": False,
                        "status": "open"
                    }]
                }
        """
        orders = self.get_market_community().order_manager.order_repository.find_all()
        return json.twisted_dumps({"orders": [order.to_dictionary() for order in orders]})


class OrderSpecificEndpoint(BaseMarketEndpoint):

    def __init__(self, session, order_number):
        BaseMarketEndpoint.__init__(self, session)
        self.order_number = order_number

        child_handler_dict = {b"cancel": OrderCancelEndpoint}
        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(self.session, self.order_number))


class OrderCancelEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for cancelling a specific order.
    """

    def __init__(self, session, order_number):
        BaseMarketEndpoint.__init__(self, session)
        self.order_number = order_number

    def render_POST(self, request):
        """
        .. http:get:: /market/orders/(string:order_number)/cancel

        A POST request to this endpoint will cancel a specific order.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/orders/3/cancel

            **Example response**:

            .. sourcecode:: javascript

                {
                    "cancelled": True
                }
        """
        market_community = self.get_market_community()
        order_id = OrderId(TraderId(market_community.mid), OrderNumber(int(self.order_number)))
        order = market_community.order_manager.order_repository.find_by_id(order_id)

        if not order:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "order not found"})

        if order.status != "open" and order.status != "unverified":
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "only open and unverified orders can be cancelled"})

        market_community.cancel_order(order_id)

        return json.twisted_dumps({"cancelled": True})
