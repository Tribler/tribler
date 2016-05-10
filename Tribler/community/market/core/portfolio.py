import logging

from Tribler.community.market.core.order_repository import OrderRepository
from Tribler.community.market.core.tick import Order, Timestamp, OrderId


class Portfolio(object):
    """Provides an interface to the user to manage the users orders"""

    def __init__(self, order_repository):
        """
        Initialise the portfolio

        :param order_repository: The order repository to use for this portfolio
        :type order_repository: OrderRepository
        """
        super(Portfolio, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(order_repository, OrderRepository), type(order_repository)
        self.order_repository = order_repository

    def create_ask_order(self, price, quantity, timeout):
        order = Order(self.order_repository.next_identity(), price, quantity, timeout, Timestamp.now(), True)
        self.order_repository.add(order)

    def create_bid_order(self, price, quantity, timeout):
        order = Order(self.order_repository.next_identity(), price, quantity, timeout, Timestamp.now(), False)
        self.order_repository.add(order)

    def delete_order(self, order_id):
        assert isinstance(order_id, OrderId), type(order_id)
        self.order_repository.delete_by_id(order_id)
