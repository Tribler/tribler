import logging

from Tribler.community.market.core.order_repository import OrderRepository
from Tribler.community.market.core.tick import Price, Quantity, Timeout, Timestamp, OrderId, Order


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
        self._logger.info("Market Portfolio initialized")

        assert isinstance(order_repository, OrderRepository), type(order_repository)

        self.order_repository = order_repository

    def create_ask_order(self, price, quantity, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)

        order = Order(self.order_repository.next_identity(), price, quantity, timeout, Timestamp.now(), True)
        self.order_repository.add(order)

        self._logger.info("Ask order created with id: " + str(order.order_id))

        return order

    def create_bid_order(self, price, quantity, timeout):
        """
        Create a bid order (buy order)

        :param price: The price for the order
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)

        order = Order(self.order_repository.next_identity(), price, quantity, timeout, Timestamp.now(), False)
        self.order_repository.add(order)

        self._logger.info("Bid order created with id: " + str(order.order_id))

        return order

    def cancel_order(self, order_id):
        """
        Cancel an order that was created by the user

        It only marks it as timed out, because some quantity might already be sold or bought

        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(order_id, OrderId), type(order_id)

        self.order_repository.delete_by_id(order_id)

        self._logger.info("Order canceled with id: " + str(order_id))
