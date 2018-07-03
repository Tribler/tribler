import logging

from Tribler.community.market.core.order import Order
from Tribler.community.market.core.order_repository import OrderRepository
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class OrderManager(object):
    """Provides an interface to the user to manage the users orders"""

    def __init__(self, order_repository):
        """
        :type order_repository: OrderRepository
        """
        super(OrderManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Market OrderManager initialized")

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
        order = Order(self.order_repository.next_identity(), price, quantity, timeout, Timestamp.now(), False)
        self.order_repository.add(order)

        self._logger.info("Bid order created with id: " + str(order.order_id))

        return order

    def cancel_order(self, order_id):
        """
        Cancel an order that was created by the user.
        :return: The order that is created
        :rtype: Order
        """
        order = self.order_repository.find_by_id(order_id)

        if order:
            order.cancel()
            self.order_repository.update(order)

        self._logger.info("Order cancelled with id: " + str(order_id))
