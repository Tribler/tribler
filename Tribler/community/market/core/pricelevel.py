from Tribler.community.market.core.tick import Quantity
from order import Order


class PriceLevel(object):
    """Class to represents a list of orders at a specific price level"""

    def __init__(self):
        """
        Initialise the price level
        """
        self._head_order = None
        self._tail_order = None
        self._length = 0
        self._depth = Quantity(0)
        self._last = None

    @property
    def first_order(self):
        """
        Return the first order in the price level

        :return: The first order
        :rtype: Order
        """
        return self._head_order

    @property
    def length(self):
        """
        Return the length of the amount of orders contained in the price level

        :return: The length
        :rtype: integer
        """
        return self._length

    @property
    def depth(self):
        """
        Return the depth of the price level

        The depth is equal to the total amount of volume contained in this price level

        :return: The depth
        :rtype: Quantity
        """
        return self._depth

    def __len__(self):
        """
        Return the length of the amount of orders contained in the price level

        :return: The length
        :rtype: integer
        """
        return self.length

    def __iter__(self):
        """
        Iterate over the orders in the price level

        :return: The price level
        :rtype: PriceLevel
        """
        self._last = self._head_order
        return self

    def next(self):
        """
        Return the next order in the price level for the iterator

        :return: The next order
        :rtype: Order
        """
        if self._last is None:
            raise StopIteration
        else:
            return_value = self._last
            self._last = self._last.next_order()
            return return_value

    def append_order(self, order):
        """
        Append an order to the price level

        :param order: The order to be added
        :type order: Order
        """
        assert isinstance(order, Order), type(order)

        if self._length == 0:  # Add the first order
            order._prev_order = None
            order._next_order = None
            self._head_order = order
            self._tail_order = order
        else:  # Add to the end of the existing orders
            order._prev_order = self._tail_order
            order._next_order = None
            self._tail_order._next_order = order
            self._tail_order = order

        # Update the counters
        self._length += 1
        self._depth += order.quantity

    def remove_order(self, order):
        """
        Remove an order from the price level

        :param order: The order to be removed
        :type order: Order
        """
        assert isinstance(order, Order), type(order)

        # Update the counters
        self._depth -= order.quantity
        self._length -= 1

        if self._length == 0:  # Was the only order in this price level
            return

        prev_order = order.prev_order()
        next_order = order.next_order()
        if prev_order is not None and next_order is not None:  # Order in between to other orders
            prev_order._next_order = next_order
            next_order._prev_order = prev_order
        elif next_order is not None:  # First order
            next_order._prev_order = None
            self._head_order = next_order
        elif prev_order is not None:  # Last order
            prev_order._next_order = None
            self._tail_order = prev_order

    def __str__(self):
        from cStringIO import StringIO

        temp_file = StringIO()
        for order in self:
            temp_file.write("%s\n" % str(order))
        return temp_file.getvalue()
