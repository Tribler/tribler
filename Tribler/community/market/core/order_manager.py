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
        self._logger.info("Market order manager initialized")

        self.order_repository = order_repository

    def create_ask_order(self, assets, timeout):
        """
        Create an ask order (sell order)

        :param assets: The assets to be exchanged
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        order = Order(self.order_repository.next_identity(), assets, timeout, Timestamp.now(), True)
        self.order_repository.add(order)

        self._logger.info("Ask order created with id: " + str(order.order_id))

        return order

    def create_bid_order(self, assets, timeout):
        """
        Create a bid order (buy order)

        :param assets: The assets to be exchanged
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        order = Order(self.order_repository.next_identity(), assets, timeout, Timestamp.now(), False)
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
