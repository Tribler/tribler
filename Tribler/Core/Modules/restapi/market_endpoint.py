from twisted.web import resource

from Tribler.Core.Modules.restapi.market.asks_bids_endpoint import AsksEndpoint, BidsEndpoint
from Tribler.Core.Modules.restapi.market.orders_endpoint import OrdersEndpoint
from Tribler.Core.Modules.restapi.market.transactions_endpoint import TransactionsEndpoint


class MarketEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the market community API where we trade reputation.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        child_handler_dict = {"asks": AsksEndpoint, "bids": BidsEndpoint, "transactions": TransactionsEndpoint,
                              "orders": OrdersEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))
