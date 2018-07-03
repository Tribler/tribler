import logging

from twisted.internet import reactor

from Tribler.community.market.core.assetamount import Quantity
from Tribler.community.market.core.tick import Tick
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class TickEntry(TaskManager):
    """Class for representing a tick in the order book"""

    def __init__(self, tick, price_level):
        """
        :param tick: A tick to represent in the order book
        :param price_level: A price level to place the tick in
        :type tick: Tick
        :type price_level: PriceLevel
        """
        super(TickEntry, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self._tick = tick
        self._price_level = price_level
        self._prev_tick = None
        self._next_tick = None
        self._reserved_for_matching = Quantity(0, tick.quantity.asset_id)
        self._blocked_for_matching = []

    @property
    def tick(self):
        """
        :rtype: Tick
        """
        return self._tick

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._tick.order_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._tick.price

    @property
    def quantity(self):
        """
        :rtype: Quantity
        """
        return self._tick.quantity

    @quantity.setter
    def quantity(self, new_quantity):
        """
        :param new_quantity: The new quantity
        :type new_quantity: Quantity
        """
        self._price_level.depth -= (self._tick.quantity - new_quantity)
        self._tick.quantity = new_quantity

    def block_for_matching(self, order_id):
        """
        Temporarily block an order id for matching
        """
        if order_id in self._blocked_for_matching:
            self._logger.debug("Not blocking %s for matching; already blocked", order_id)
            return

        def unblock_order_id(unblock_id):
            self._logger.debug("Unblocking order id %s", unblock_id)
            self._blocked_for_matching.remove(unblock_id)

        self._logger.debug("Blocking %s for tick %s", order_id, self.order_id)
        self._blocked_for_matching.append(order_id)
        self.register_task("unblock_%s" % order_id, reactor.callLater(10, unblock_order_id, order_id))

    def is_blocked_for_matching(self, order_id):
        """
        Return whether the order_id is blocked for matching
        """
        return order_id in self._blocked_for_matching

    def reserve_for_matching(self, reserve_quantity):
        """
        Reserve some quantity of this tick entry for matching.
        :param reserve_quantity: The quantity to reserve
        """
        self._logger.debug("Reserved %s quantity for matching (in tick %s)", reserve_quantity, self.tick)

        self._reserved_for_matching += reserve_quantity
        self._price_level.reserved += reserve_quantity

    def release_for_matching(self, release_quantity):
        """
        Release some quantity of this tick entry for matching.
        :param release_quantity: The quantity to release
        """
        self._logger.debug("Released %s quantity for matching (in tick %s)", release_quantity, self.tick)

        self._reserved_for_matching -= release_quantity
        self._price_level.reserved -= release_quantity

    def is_valid(self):
        """
        Return if the tick is still valid

        :return: True if valid, False otherwise
        :rtype: bool
        """
        return self._tick.is_valid()

    def price_level(self):
        """
        :return: The price level the tick was placed in
        :rtype: PriceLevel
        """
        return self._price_level

    @property
    def prev_tick(self):
        """
        :rtype: TickEntry
        """
        return self._prev_tick

    @prev_tick.setter
    def prev_tick(self, new_prev_tick):
        """
        :param new_prev_tick: The new previous tick
        :type new_prev_tick: TickEntry
        """
        self._prev_tick = new_prev_tick

    @property
    def next_tick(self):
        """
        :rtype: TickEntry
        """
        return self._next_tick

    @property
    def reserved_for_matching(self):
        """
        :rtype: Quantity
        """
        return self._reserved_for_matching

    @next_tick.setter
    def next_tick(self, new_next_tick):
        """
        :param new_next_tick: The new previous tick
        :type new_next_tick: TickEntry
        """
        self._next_tick = new_next_tick

    def __str__(self):
        """
        format: <quantity>\t@\t<price>
        :rtype: str
        """
        return "%s\t@\t%s (R: %s)" % (str(self._tick.quantity), str(self._tick.price), str(self.reserved_for_matching))
