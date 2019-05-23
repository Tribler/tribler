from __future__ import absolute_import

import json

from twisted.web import resource

from Tribler.Test.GUI.FakeTriblerAPI import tribler_utils


class MarketEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the market community API where we trade reputation.
    """

    def __init__(self):
        resource.Resource.__init__(self)

        child_handler_dict = {"asks": AsksEndpoint, "bids": BidsEndpoint,
                              "transactions": TransactionsEndpoint, "orders": OrdersEndpoint}
        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls())


class AsksEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.dumps({
            "asks": [{
                "asset1": "DUM1",
                "asset2": "DUM2",
                "ticks": [tick.get_json() for tick in tribler_utils.tribler_data.order_book['asks']]
            }]
        })


class BidsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.dumps({
            "bids": [{
                "asset1": "DUM1",
                "asset2": "DUM2",
                "ticks": [tick.get_json() for tick in tribler_utils.tribler_data.order_book['bids']]
            }]
        })


class TransactionsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.dumps({"transactions": [transaction.get_json() for
                                            transaction in tribler_utils.tribler_data.transactions]})

    def getChild(self, path, request):
        return TransactionSpecificTraderEndpoint(path)


class TransactionSpecificTraderEndpoint(resource.Resource):

    def __init__(self, path):
        resource.Resource.__init__(self)
        self.transaction_trader_id = path

    def getChild(self, path, request):
        return TransactionSpecificNumberEndpoint(self.transaction_trader_id, path)


class TransactionSpecificNumberEndpoint(resource.Resource):

    def __init__(self, transaction_trader_id, path):
        resource.Resource.__init__(self)
        self.transaction_trader_id = transaction_trader_id
        self.transaction_number = int(path)

        child_handler_dict = {"payments": TransactionPaymentsEndpoint}
        for child_path, child_cls in child_handler_dict.items():
            self.putChild(child_path, child_cls(self.transaction_trader_id, self.transaction_number))


class TransactionPaymentsEndpoint(resource.Resource):

    def __init__(self, transaction_trader_id, transaction_number):
        resource.Resource.__init__(self)
        self.transaction_trader_id = transaction_trader_id
        self.transaction_number = transaction_number

    def render_GET(self, _request):
        tx = tribler_utils.tribler_data.get_transaction(self.transaction_trader_id, self.transaction_number)
        return json.dumps({"payments": [payment.get_json() for payment in tx.payments]})


class OrdersEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.dumps({"orders": [order.get_json() for order in tribler_utils.tribler_data.orders]})
