import logging
import random
from abc import ABCMeta, abstractmethod
from time import time

from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.assetamount import Quantity
from Tribler.community.market.core.tickentry import TickEntry


class MatchingStrategy(object):
    """Matching strategy base class"""
    __metaclass__ = ABCMeta

    def __init__(self, order_book):
        """
        :param order_book: The order book to search in
        :type order_book: OrderBook
        """
        super(MatchingStrategy, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.order_book = order_book
        self.used_match_ids = set()

    def get_random_match_id(self):
        """
        Generate a random matching ID (20 hex characters).
        :return: A random matching ID
        :rtype: str
        """
        return ''.join(random.choice('0123456789abcdef') for _ in xrange(20))

    def get_unique_match_id(self):
        """
        Generate a random, unique matching ID that has not been used yet.
        :return: A random matching ID
        :rtype: str
        """
        random_match_id = self.get_random_match_id()
        while random_match_id in self.used_match_ids:
            random_match_id = self.get_random_match_id()
        self.used_match_ids.add(random_match_id)
        return random_match_id

    @abstractmethod
    def match(self, order_id, price, quantity, is_ask):
        """
        :param order_id: The order id of the tick to match
        :param price: The price to match against
        :param quantity: The quantity that should be matched
        :param is_ask: Whether the object we want to match is an ask
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type is_ask: Bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        return


class PriceTimeStrategy(MatchingStrategy):
    """Strategy that uses the price time method for picking ticks"""

    def match(self, order_id, price, quantity, is_ask):
        """
        :param order_id: The order id of the tick to match
        :param price: The price to match against
        :param quantity: The quantity that should be matched
        :param is_ask: Whether the object we want to match is an ask
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type is_ask: Bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        matched_ticks = []
        quantity_to_match = Quantity(quantity.amount, quantity.asset_id)

        # First check whether we can match our order at all in the order book
        if is_ask and price > self.order_book.get_bid_price(price.asset_id, quantity.asset_id):
            return []
        if not is_ask and price < self.order_book.get_ask_price(price.asset_id, quantity.asset_id):
            return []

        # Next, check whether we have a price level we can start our match search from
        if is_ask:
            price_level = self.order_book.get_bid_price_level(price.asset_id, quantity.asset_id)
        else:
            price_level = self.order_book.get_ask_price_level(price.asset_id, quantity.asset_id)

        if not price_level:
            return []

        cur_tick_entry = price_level.first_tick
        cur_price_level_price = price_level.price

        # We now start to iterate through price levels and tick entries and match on the fly
        while cur_tick_entry and quantity_to_match.amount > 0:
            if cur_tick_entry.is_blocked_for_matching(order_id):
                cur_tick_entry = cur_tick_entry.next_tick
                continue

            quantity_matched = Quantity(min(quantity_to_match.amount,
                                            cur_tick_entry.quantity.amount -
                                            cur_tick_entry.reserved_for_matching.amount),
                                        quantity.asset_id)
            if quantity_matched.amount > 0:
                matched_ticks.append((self.get_unique_match_id(), cur_tick_entry, quantity_matched))
                quantity_to_match -= quantity_matched

            cur_tick_entry = cur_tick_entry.next_tick
            if not cur_tick_entry:
                # We probably reached the end of a price level, check whether we have a next price level
                try:
                    # Get the next price level
                    if is_ask:
                        next_price, next_price_level = self.order_book.bids. \
                            get_price_level_list(price.asset_id, quantity.asset_id).prev_item(cur_price_level_price)
                        cur_price_level_price = next_price
                    else:
                        next_price, next_price_level = self.order_book.asks. \
                            get_price_level_list(price.asset_id, quantity.asset_id).succ_item(cur_price_level_price)
                        cur_price_level_price = next_price
                except IndexError:
                    break

                if (is_ask and price > cur_price_level_price) or (not is_ask and price < cur_price_level_price):
                    # The price of this price level is too high/low
                    break

                cur_tick_entry = next_price_level.first_tick

        return matched_ticks


class MatchingEngine(object):
    """Matches ticks and orders to the order book"""

    def __init__(self, matching_strategy):
        """
        :param matching_strategy: The strategy to use
        :type matching_strategy: MatchingStrategy
        """
        super(MatchingEngine, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.matching_strategy = matching_strategy
        self.matches = {}  # Keep track of all matches

    def match(self, tick_entry):
        """
        :param tick_entry: The TickEntry that should be matched
        :type tick_entry: TickEntry
        :return: A list of tuples containing a random match id, ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        now = time()

        matched_ticks = self.matching_strategy.match(tick_entry.order_id,
                                                     tick_entry.price,
                                                     tick_entry.quantity - tick_entry.reserved_for_matching,
                                                     tick_entry.tick.is_ask())

        for match_id, matched_tick_entry, quantity in matched_ticks:  # Store the matches
            self.matches[match_id] = (tick_entry.order_id, matched_tick_entry.order_id, quantity)

        diff = time() - now
        self._logger.debug("Matching engine completed in %.2f seconds", diff)
        return matched_ticks
