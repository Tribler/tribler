import logging
import random
from abc import ABCMeta, abstractmethod
from time import time

from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.quantity import Quantity
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

        assert isinstance(order_book, OrderBook), type(order_book)

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
        matched_ticks = self._match_ask(order_id, price, quantity, is_ask) if is_ask \
            else self._match_bid(order_id, price, quantity, is_ask)

        return matched_ticks

    def _match_ask(self, order_id, price, quantity, is_ask):
        matched_ticks = []

        if price <= self.order_book.get_bid_price(price.wallet_id, quantity.wallet_id) \
                and quantity > Quantity(0, quantity.wallet_id):
            # Scan the price levels in the order book
            matched_ticks = self._search_for_quantity_in_order_book(
                order_id,
                self.order_book.get_bid_price(price.wallet_id, quantity.wallet_id),
                self.order_book.get_bid_price_level(price.wallet_id, quantity.wallet_id),
                quantity, price, is_ask)
        return matched_ticks

    def _match_bid(self, order_id, price, quantity, is_ask):
        matched_ticks = []

        if price >= self.order_book.get_ask_price(price.wallet_id, quantity.wallet_id) \
                and quantity > Quantity(0, quantity.wallet_id):
            # Scan the price levels in the order book
            matched_ticks = self._search_for_quantity_in_order_book(
                order_id,
                self.order_book.get_ask_price(price.wallet_id, quantity.wallet_id),
                self.order_book.get_ask_price_level(price.wallet_id, quantity.wallet_id),
                quantity, price, is_ask)
        return matched_ticks

    def _search_for_quantity_in_order_book(self, order_id, price, price_level, quantity_to_trade, tick_price, is_ask):
        """
        Search through the price levels in the order book
        :param order_id: The order id of the tick to match
        :param price: The price of the price level
        :param price_level: The price level to search in
        :param quantity_to_trade: The quantity still to be matched
        :param tick_price: The price of the tick being matched
        :param is_ask: Whether our tick being matched is an ask
        :type order_id: OrderId
        :type price: Price
        :type price_level: PriceLevel
        :type quantity_to_trade: Quantity
        :type tick_price: Price
        :type is_ask: bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        if price_level is None:  # Last price level
            return []

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(price_level, PriceLevel), type(price_level)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick_price, Price), type(tick_price)
        assert isinstance(is_ask, bool), type(is_ask)

        self._logger.debug("Searching in price level: %f", float(price))

        if quantity_to_trade <= price_level.depth - price_level.reserved:
            # All the quantity can be matched in this price level
            return self._search_for_quantity_in_price_level(order_id, price_level.first_tick,
                                                            quantity_to_trade,
                                                            tick_price, is_ask)
        else:
            # Not all the quantity can be matched in this price level
            return self._search_for_quantity_in_order_book_partial(order_id, price, price_level, quantity_to_trade,
                                                                   tick_price, is_ask)

    def _search_for_quantity_in_order_book_partial(self, order_id, price, price_level, quantity_to_trade,
                                                   tick_price, is_ask):
        # Not all the quantity can be matched in this price level
        matching_ticks = self._search_for_quantity_in_price_level(order_id, price_level.first_tick, quantity_to_trade,
                                                                  tick_price, is_ask)
        if is_ask:
            return self._search_for_quantity_in_order_book_partial_ask(order_id, price, quantity_to_trade,
                                                                       matching_ticks, tick_price, is_ask)
        else:
            return self._search_for_quantity_in_order_book_partial_bid(order_id, price, quantity_to_trade,
                                                                       matching_ticks, tick_price, is_ask)

    def _search_for_quantity_in_order_book_partial_ask(self, order_id, price, quantity_to_trade, matching_ticks,
                                                       tick_price, is_ask):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.bids.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).prev_item(price)
        except IndexError:
            return matching_ticks

        if tick_price > next_price:  # Price is too low
            return matching_ticks

        matching_ticks += self._search_for_quantity_in_order_book(order_id, next_price, next_price_level,
                                                                  quantity_to_trade, tick_price, is_ask)

        return matching_ticks

    def _search_for_quantity_in_order_book_partial_bid(self, order_id, price, quantity_to_trade, matching_ticks,
                                                       tick_price, is_ask):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.asks.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).succ_item(price)
        except IndexError:
            return matching_ticks

        if tick_price < next_price:  # Price is too high
            return matching_ticks

        matching_ticks += self._search_for_quantity_in_order_book(order_id, next_price, next_price_level,
                                                                  quantity_to_trade, tick_price, is_ask)

        return matching_ticks

    def _search_for_quantity_in_price_level(self, order_id, tick_entry, quantity_to_trade, tick_price, is_ask):
        """
        Search through the tick entries in the price levels

        :param order_id: The order id to match
        :param tick_entry: The tick entry to match against
        :param quantity_to_trade: The quantity still to be matched
        :param tick_price: The price of the tick being matched
        :param is_ask: Whether our tick being matched is an ask
        :type tick_entry: TickEntry
        :type quantity_to_trade: Quantity
        :type tick_price: Price
        :type is_ask: bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        if tick_entry is None:  # Last tick
            return []

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick_price, Price), type(tick_price)
        assert isinstance(is_ask, bool), type(is_ask)

        if quantity_to_trade <= tick_entry.quantity - tick_entry.reserved_for_matching \
                and not tick_entry.is_blocked_for_matching(order_id):
            # All the quantity can be matched in this tick
            return self._search_for_quantity_in_price_level_total(tick_entry, quantity_to_trade)
        else:
            # Not all the quantity can be matched in this tick
            return self._search_for_quantity_in_price_level_partial(order_id, tick_entry, quantity_to_trade,
                                                                    tick_price, is_ask)

    def _search_for_quantity_in_price_level_total(self, tick_entry, quantity_to_trade):
        trading_quantity = quantity_to_trade

        self._logger.debug("Match with the id (%s) was found: price %f, quantity %f",
                           str(tick_entry.order_id), float(tick_entry.price), float(trading_quantity))

        return [(self.get_unique_match_id(), tick_entry, trading_quantity)]

    def _search_for_quantity_in_price_level_partial(self, order_id, tick_entry, quantity_to_trade, tick_price, is_ask):
        matched_quantity = tick_entry.quantity - tick_entry.reserved_for_matching
        matching_ticks = []

        if matched_quantity > Quantity(0, matched_quantity.wallet_id) and not \
                tick_entry.is_blocked_for_matching(order_id):
            quantity_to_trade -= matched_quantity

            self._logger.debug("Match with the id (%s) was found: price %f, quantity %f",
                               str(tick_entry.order_id), float(tick_entry.price), float(matched_quantity))

            matching_ticks = [(self.get_unique_match_id(), tick_entry, matched_quantity)]

        # Search the next tick
        matching_ticks += self._search_for_quantity_in_price_level(order_id, tick_entry.next_tick, quantity_to_trade,
                                                                   tick_price, is_ask)
        return matching_ticks


class MatchingEngine(object):
    """Matches ticks and orders to the order book"""

    def __init__(self, matching_strategy):
        """
        :param matching_strategy: The strategy to use
        :type matching_strategy: MatchingStrategy
        """
        super(MatchingEngine, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(matching_strategy, MatchingStrategy), type(matching_strategy)
        self.matching_strategy = matching_strategy
        self.matches = {}  # Keep track of all matches

    def match(self, tick_entry):
        """
        :param tick_entry: The TickEntry that should be matched
        :type tick_entry: TickEntry
        :return: A list of tuples containing a random match id, ticks and the matched quantity
        :rtype: [(str, TickEntry, Quantity)]
        """
        assert isinstance(tick_entry, TickEntry), type(tick_entry)
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
