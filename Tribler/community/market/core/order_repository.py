import logging

from message import TraderId
from order import OrderNumber, OrderId, Order


class OrderRepository(object):
    """A repository interface for orders in the order manager"""

    def __init__(self):
        """
        Do not use this class directly

        Make a subclass of this class with a specific implementation for a storage backend
        """
        super(OrderRepository, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

    def find_all(self):
        return NotImplemented

    def find_by_id(self, order_id):
        return NotImplemented

    def add(self, order):
        return NotImplemented

    def update(self, order):
        return NotImplemented

    def delete_by_id(self, order_id):
        return NotImplemented

    def next_identity(self):
        return NotImplemented


class MemoryOrderRepository(OrderRepository):
    """A repository for orders in the order manager stored in memory"""

    def __init__(self, pubkey):
        """
        :param pubkey: Hex encoded version of the public key of this node
        :type pubkey: str
        """
        super(MemoryOrderRepository, self).__init__()

        self._logger.info("Memory order repository used")

        try:
            int(pubkey, 16)
        except ValueError:  # Not a hexadecimal
            raise ValueError("Encoded public key must be hexadecimal")

        self._pubkey = pubkey
        self._next_id = 0  # Counter to keep track of the number of messages created by this repository

        self._orders = {}

    def find_all(self):
        """
        :rtype: [Order]
        """
        return self._orders.values()

    def find_by_id(self, order_id):
        """
        :param order_id: The order id to look for
        :type order_id: OrderId
        :return: The order or null if it cannot be found
        :rtype: Order
        """
        assert isinstance(order_id, OrderId), type(order_id)

        self._logger.debug("Order with the id: " + str(order_id) + " was searched for in the order repository")

        return self._orders.get(order_id)

    def add(self, order):
        """
        :type order: Order
        """
        assert isinstance(order, Order), type(order)

        self._logger.debug("Order with the id: " + str(order.order_id) + " was added to the order repository")

        self._orders[order.order_id] = order

    def update(self, order):
        """
        :type order: Order
        """
        assert isinstance(order, Order), type(order)

        self._logger.debug("Order with the id: " + str(order.order_id) + " was updated to the order repository")

        self._orders[order.order_id] = order

    def delete_by_id(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        self._logger.debug("Order with the id: " + str(order_id) + " was deleted from the order repository")

        del self._orders[order_id]

    def next_identity(self):
        """
        :rtype: OrderId
        """
        self._next_id += 1
        return OrderId(TraderId(self._pubkey), OrderNumber(str(self._next_id)))
